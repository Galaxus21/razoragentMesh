// negotiate_price -- runs the buyer's side of an x402-INR alternating-offer negotiation.
//
// Why this exists: the x402-INR gateway has spoken this protocol from the start -- proof-of-work
// per turn, a micro-escrow debited ₹0.50 a turn, monotonic concessions, and an immutable contract
// AST compiled on convergence -- but it was reachable only over raw HTTP. An MCP agent could buy at
// list price and nothing else, which is the one thing agentic commerce is supposed to improve on.
//
// The whole negotiation is ONE tool call. An MCP agent cannot hold a multi-turn side-channel
// open, and making it drive five turns by hand would mean five PoW solves it has no library for,
// plus an escrow it would leak if it stopped early. So the loop, the proof-of-work and the escrow
// lifecycle all live here, and the agent supplies only what a buyer actually decides: what to open
// at, and what it refuses to go above.

import {
  basisPointsDivisor,
  buyerConcessionRateBps,
  errorUnknownSku,
  initialEscrowPoolPaise,
  microFeePerTurnPaise,
  minConcessionPaise,
  powSolveBudgetMs,
  sellerConcessionRateBps
} from "../constants/negotiationConstants.js";
import { currencyInr } from "../constants/protocolConstants.js";
import { defaultCatalogStore, CatalogStore } from "../catalog/catalogStore.js";
import {
  negotiatePriceRequestSchema,
  negotiatePriceResponseSchema,
  type NegotiatePriceResponse,
  type NegotiationTurn
} from "../schemas/negotiatePriceSchema.js";
import {
  createEscrowSession,
  fetchPowChallenge,
  releaseEscrowSession,
  submitNegotiationTurn
} from "../negotiation/negotiationClient.js";
import { solvePowChallengeAsync } from "@razorpay/agent-buyer-sdk";

/**
 * How far one side moves this turn: a share of what is still open, but never less than the
 * gateway's documented minimum step. Floored at the minimum so a nearly-closed spread still
 * moves; see negotiationConstants for why a flat minimum alone never converges.
 */
export function concessionStepPaise(openPaise: number, rateBps: number): number {
  if (openPaise <= 0) {
    return 0;
  }
  const proportional = Math.floor((openPaise * rateBps) / basisPointsDivisor);
  return Math.max(minConcessionPaise, proportional);
}

/**
 * The seller's next ask. Never below the buyer's standing bid -- mirroring the gateway's own
 * computeSellerCounterAsk (negotiation/marginEvaluator.py), which clamps the same way. That clamp
 * is what makes a converged price fair rather than a giveaway: the seller closes at the buyer's
 * number, not under it.
 */
export function nextSellerAskPaise(
  previousAskPaise: number,
  previousBidPaise: number
): number {
  const step = concessionStepPaise(previousAskPaise - previousBidPaise, sellerConcessionRateBps);
  return Math.max(previousAskPaise - step, previousBidPaise);
}

/**
 * The buyer's next bid, clamped at the reservation price. The clamp is the tool's core safety
 * property: no sequence of turns can bid above the ceiling the agent declared, so a CONVERGED
 * result is always affordable and the caller does not have to re-check it.
 */
export function nextBuyerBidPaise(previousBidPaise: number, ceilingPaise: number): number {
  const step = concessionStepPaise(ceilingPaise - previousBidPaise, buyerConcessionRateBps);
  return Math.min(previousBidPaise + step, ceilingPaise);
}

interface NegotiationLoopState {
  readonly turns: NegotiationTurn[];
  agreedUnitPricePaise: number | null;
  contractAstHash: string | null;
  cumulativeFeesPaise: number;
}

/**
 * Negotiates a unit price and reports what it cost to get there.
 *
 * Escrow is released in a `finally`: a hold that outlives the call is real money parked on a
 * session nobody will resume, and the tool is just as likely to end on a refusal from the gateway
 * as on convergence.
 */
export async function negotiatePrice(
  rawArguments: unknown,
  catalogStore: CatalogStore = defaultCatalogStore
): Promise<NegotiatePriceResponse> {
  const request = negotiatePriceRequestSchema.parse(rawArguments);

  const sku = catalogStore.getSku(request.sku_id);
  if (!sku) {
    throw new Error(errorUnknownSku);
  }
  const listUnitPricePaise = sku.baseUnitPricePaise;

  const escrow = await createEscrowSession(request.buyer_agent_id, initialEscrowPoolPaise);
  const state: NegotiationLoopState = {
    turns: [],
    agreedUnitPricePaise: null,
    contractAstHash: null,
    cumulativeFeesPaise: 0
  };

  let refundedPaise = 0;
  try {
    await _runNegotiationLoop(request, listUnitPricePaise, escrow.sessionToken, state);
  } finally {
    refundedPaise = await _releaseQuietly(escrow.sessionToken);
  }

  return _buildResponse(request, listUnitPricePaise, state, refundedPaise);
}

async function _runNegotiationLoop(
  request: ReturnType<typeof negotiatePriceRequestSchema.parse>,
  listUnitPricePaise: number,
  escrowToken: string,
  state: NegotiationLoopState
): Promise<void> {
  // Turn 1 is the opening exchange, so both sides state their position before either concedes.
  // An opening bid at or above the list price converges immediately, which is correct: there is
  // nothing to negotiate and charging four more turns of fees for it would be theft.
  let sellerAskPaise = listUnitPricePaise;
  let buyerBidPaise = request.opening_bid_paise;
  const loopStartedAtMs = Date.now();

  for (let turnNumber = 1; turnNumber <= request.max_turns; turnNumber += 1) {
    if (turnNumber > 1) {
      const previousAsk = sellerAskPaise;
      const previousBid = buyerBidPaise;
      sellerAskPaise = nextSellerAskPaise(previousAsk, previousBid);
      buyerBidPaise = nextBuyerBidPaise(previousBid, request.max_unit_price_paise);
    }

    // Bounded rather than unbounded: PoW difficulty is per-IP dynamic in the gateway's anti-spam
    // shield, so a hostile or merely busy gateway could otherwise hold this tool call open past
    // any client's timeout. Stopping here returns the turns already completed, which is a real
    // partial result -- the escrow still gets released by the caller's finally.
    if (Date.now() - loopStartedAtMs > powSolveBudgetMs) {
      return;
    }

    const challenge = await fetchPowChallenge();
    const solution = await solvePowChallengeAsync(
      challenge.challengeToken,
      challenge.powDifficultyZeros
    );

    const outcome = await submitNegotiationTurn({
      skuId: request.sku_id,
      quantity: request.quantity,
      turnNumber,
      buyerBidPaise,
      sellerAskPaise,
      buyerAgentDid: request.buyer_agent_id,
      merchantDid: request.merchant_did,
      challengeToken: challenge.challengeToken,
      solutionNonce: solution.nonce,
      escrowToken
    });

    const step = outcome.stepResult;
    state.cumulativeFeesPaise = step.cumulativeMicroFeesPaise;
    state.turns.push({
      turn_number: step.turnNumber,
      buyer_bid_paise: step.buyerBidPaise,
      seller_ask_paise: step.sellerAskPaise,
      spread_paise: step.spreadPaise,
      converged: step.isConverged,
      micro_fee_paise: microFeePerTurnPaise,
      cumulative_micro_fees_paise: step.cumulativeMicroFeesPaise
    });

    if (step.isConverged) {
      // The seller's ask, not the buyer's bid. They may not be equal -- the buyer can cross above
      // the ask on its final move -- and the gateway compiles its contract AST at the ask, so
      // reporting anything else would name a price the signed contract does not contain.
      state.agreedUnitPricePaise = step.sellerAskPaise;
      state.contractAstHash = outcome.contractAstHash ?? null;
      return;
    }
  }
}

/** A failed release must not turn a completed negotiation into a tool error. */
async function _releaseQuietly(escrowToken: string): Promise<number> {
  try {
    const refund = await releaseEscrowSession(escrowToken);
    return refund.refundedBalancePaise ?? 0;
  } catch {
    return 0;
  }
}

function _buildResponse(
  request: ReturnType<typeof negotiatePriceRequestSchema.parse>,
  listUnitPricePaise: number,
  state: NegotiationLoopState,
  refundedPaise: number
): NegotiatePriceResponse {
  const converged = state.agreedUnitPricePaise !== null;
  const savings = converged
    ? Math.max(0, listUnitPricePaise - (state.agreedUnitPricePaise as number))
    : 0;

  return negotiatePriceResponseSchema.parse({
    sku_id: request.sku_id,
    quantity: request.quantity,
    currency: currencyInr,
    status: converged ? "CONVERGED" : "EXHAUSTED",
    list_unit_price_paise: listUnitPricePaise,
    agreed_unit_price_paise: state.agreedUnitPricePaise,
    savings_vs_list_paise: savings,
    turns: state.turns,
    turns_used: state.turns.length,
    micro_fees_paid_paise: state.cumulativeFeesPaise,
    escrow_refunded_paise: refundedPaise,
    contract_ast_hash: state.contractAstHash,
    next_step: _describeNextStep(converged, savings, state.cumulativeFeesPaise)
  });
}

/**
 * Said in the result rather than left to the agent to work out, because the useful next move
 * differs by outcome and the unhelpful one -- quoting anyway and paying list -- is the default an
 * agent falls into when a tool just reports a status code.
 */
function _describeNextStep(
  converged: boolean,
  savingsPaise: number,
  feesPaise: number
): string {
  if (!converged) {
    return (
      "No agreement: the turn budget ran out with a spread still open. Either raise " +
      "max_unit_price_paise and negotiate again, or call get_live_sku_quote to buy at list price."
    );
  }
  if (savingsPaise <= feesPaise) {
    return (
      `Converged, but the ${savingsPaise} paise saved did not cover the ${feesPaise} paise of ` +
      "negotiation fees. get_live_sku_quote still prices at list; this SKU was not worth " +
      "negotiating. Proceed only if you want the agreed price on record."
    );
  }
  return (
    "Agreed. get_live_sku_quote is still the only source of a bindable quote_hash, so call it " +
    "next to price the cart -- the negotiated price is recorded in the gateway's contract AST, " +
    "not applied to the quote automatically."
  );
}
