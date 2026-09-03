// HTTP client for the x402-INR gateway's negotiation surface.
//
// Kept apart from the tool so priceNegotiator.ts is about the bidding strategy and this file is
// about the wire: four endpoints, the proof-of-work handshake, and the micro-escrow lifecycle.
// Follows catalogSearcher.ts, the other mcpServer-to-service client -- plain fetch, an explicit
// timeout, and a thrown error carrying the URL, because "the gateway is down" and "the gateway
// refused" are different answers and an agent told the wrong one draws the wrong conclusion.

import {
  escrowCreatePath,
  escrowReleasePath,
  headerEscrowToken,
  headerPowChallenge,
  headerPowSolution,
  httpStatusForbidden,
  negotiateTurnPath,
  negotiationHttpTimeoutMs,
  powChallengePath,
  resolveX402GatewayUrl
} from "../constants/negotiationConstants.js";

/**
 * The merchant declined, rather than the request being wrong. Negotiation is opt-in per merchant
 * (x402Gateway/src/negotiation/merchantTerms.py), so a 403 here is a legitimate commercial answer
 * -- "this seller's price is firm" -- and the tool turns it into a result the agent can act on
 * instead of an error it has to interpret. Distinguished by type rather than by matching on the
 * message, so a reworded refusal upstream does not silently become a crash.
 */
export class NegotiationRefusedError extends Error {
  readonly reason: string;

  constructor(reason: string) {
    super(reason);
    this.name = "NegotiationRefusedError";
    this.reason = reason;
  }
}

export interface PowChallenge {
  readonly challengeToken: string;
  readonly powDifficultyZeros: number;
}

export interface EscrowSession {
  readonly sessionToken: string;
  readonly remainingBalancePaise: number;
  readonly initialHoldPaise: number;
}

export interface EscrowRefund {
  readonly totalDebitedPaise: number;
  readonly refundedBalancePaise: number;
}

export interface NegotiationStep {
  readonly turnNumber: number;
  readonly buyerBidPaise: number;
  readonly sellerAskPaise: number;
  readonly spreadPaise: number;
  readonly isConverged: boolean;
  readonly cumulativeMicroFeesPaise: number;
}

export interface NegotiationTurnResult {
  readonly stepResult: NegotiationStep;
  readonly debitReceipt?: { readonly remainingBalancePaise?: number } | null;
  readonly contractAstHash?: string | null;
}

export interface NegotiationTurnInput {
  readonly skuId: string;
  readonly quantity: number;
  readonly turnNumber: number;
  readonly buyerBidPaise: number;
  readonly sellerAskPaise: number;
  readonly buyerAgentDid: string;
  readonly merchantDid?: string;
  readonly challengeToken: string;
  readonly solutionNonce: number;
  readonly escrowToken: string;
}

/**
 * One request against the gateway. `expectedStatuses` is a list rather than a single code
 * because POST /escrow answers 201 Created while the other three answer 200 -- treating a 201 as
 * a failure is exactly the bug that makes the Python SDK's escrow client unable to talk to this
 * route at all (packages/buyerSdkPy/razoragent_buyer_sdk/razorAgentClient.py).
 */
async function requestGateway(
  path: string,
  init: RequestInit,
  expectedStatuses: ReadonlyArray<number>
): Promise<unknown> {
  const url = `${resolveX402GatewayUrl()}${path}`;
  let response: Response;
  try {
    response = await fetch(url, {
      ...init,
      signal: AbortSignal.timeout(negotiationHttpTimeoutMs)
    });
  } catch (error: unknown) {
    const detail = error instanceof Error ? error.message : String(error);
    throw new Error(`The x402 negotiation gateway is unreachable at ${url}: ${detail}`);
  }

  if (!expectedStatuses.includes(response.status)) {
    // The gateway puts its reason in `detail` -- an exhausted escrow, a replayed nonce, a bid
    // that moved the wrong way. Relaying it is what lets an agent correct itself instead of
    // retrying the same losing turn.
    const detail = await _readErrorDetail(response);
    if (response.status === httpStatusForbidden) {
      throw new NegotiationRefusedError(detail);
    }
    throw new Error(`Negotiation gateway refused with HTTP ${response.status}: ${detail}`);
  }
  return await response.json();
}

async function _readErrorDetail(response: Response): Promise<string> {
  try {
    const body = (await response.json()) as { detail?: unknown };
    return typeof body.detail === "string" ? body.detail : JSON.stringify(body);
  } catch {
    return response.statusText;
  }
}

export async function fetchPowChallenge(): Promise<PowChallenge> {
  const body = (await requestGateway(powChallengePath, { method: "GET" }, [200])) as PowChallenge;
  return {
    challengeToken: body.challengeToken,
    powDifficultyZeros: body.powDifficultyZeros
  };
}

export async function createEscrowSession(
  buyerAgentDid: string,
  initialHoldPaise: number
): Promise<EscrowSession> {
  // EscrowCreateRequest is extra="forbid" and declares exactly these two fields. Sending a third
  // -- the Python SDK sends `currency` -- makes the route answer 422.
  const body = (await requestGateway(
    escrowCreatePath,
    {
      method: "POST",
      headers: { "Content-Type": "application/json" },
      body: JSON.stringify({ buyerAgentDid, initialHoldPaise })
    },
    [200, 201]
  )) as EscrowSession;
  return body;
}

export async function submitNegotiationTurn(
  input: NegotiationTurnInput
): Promise<NegotiationTurnResult> {
  const body = (await requestGateway(
    negotiateTurnPath,
    {
      method: "POST",
      headers: {
        "Content-Type": "application/json",
        [headerPowChallenge]: input.challengeToken,
        [headerPowSolution]: String(input.solutionNonce),
        [headerEscrowToken]: input.escrowToken
      },
      body: JSON.stringify({
        skuId: input.skuId,
        quantity: input.quantity,
        turnNumber: input.turnNumber,
        buyerBidPaise: input.buyerBidPaise,
        sellerAskPaise: input.sellerAskPaise,
        buyerAgentDid: input.buyerAgentDid,
        // NegotiateTurnRequest is extra="forbid", so the key is omitted rather than sent as null.
        ...(input.merchantDid === undefined ? {} : { merchantDid: input.merchantDid })
      })
    },
    [200]
  )) as NegotiationTurnResult;
  return body;
}

/**
 * Releases the unspent hold. The token travels as the X-Mesh-Escrow-Token HEADER, not in the
 * body -- see escrowRoute.releaseEscrow, whose only parameter is `Header(..., alias=...)`.
 */
export async function releaseEscrowSession(sessionToken: string): Promise<EscrowRefund> {
  const body = (await requestGateway(
    escrowReleasePath,
    {
      method: "POST",
      headers: { [headerEscrowToken]: sessionToken }
    },
    [200]
  )) as EscrowRefund;
  return body;
}
