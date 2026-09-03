// Shapes what negotiate_price hands back, and tells the agent what to do with it.
//
// Split out of priceNegotiator.ts when a converged bargain became bindable: the tool file is the
// alternating-offer loop and the escrow lifecycle, and this is the answer an agent reads. Keeping
// them together pushed the file past the 300-line limit, and they change for different reasons --
// the loop follows the gateway's protocol, this follows what agents get wrong.
//
// What they get wrong is documented: in the 2026-09-03 matrix nine negotiations converged, all
// nine paid the ordinary list-based quote, and one agent told its user "Agreed Price: 41,338.50
// (Savings: 661.50)" before charging 49,584.62. The response now carries a realised saving that
// is computed, not implied, and a bindable flag that means exactly one thing: this figure is the
// one you will be charged.

import { currencyInr } from "../constants/protocolConstants.js";
import { agreedPriceValiditySeconds } from "../constants/negotiationConstants.js";
import {
  negotiatePriceResponseSchema,
  type NegotiatePriceRequest,
  type NegotiatePriceResponse,
  type NegotiationTurn
} from "../schemas/negotiatePriceSchema.js";
import type { AgreedPrice } from "./agreedPriceRegistry.js";

export interface NegotiationOutcome {
  readonly turns: readonly NegotiationTurn[];
  readonly agreedUnitPricePaise: number | null;
  readonly contractAstHash: string | null;
  readonly cumulativeFeesPaise: number;
  readonly declinedReason: string | null;
}

export interface BuildNegotiationResponseParams {
  readonly request: NegotiatePriceRequest;
  readonly listUnitPricePaise: number;
  /**
   * What get_live_sku_quote would offer this SKU at right now without any agreement -- the whole
   * automatic stack, sales included. The realised saving is measured against THIS, not against
   * the list price, because a discount the buyer would have received anyway is not something the
   * bargaining won.
   */
  readonly automaticUnitPricePaise: number;
  readonly outcome: NegotiationOutcome;
  readonly refundedPaise: number;
  readonly agreement: AgreedPrice | undefined;
}

interface NextStepFacts {
  readonly bindable: boolean;
  readonly converged: boolean;
  readonly declinedReason: string | null;
  readonly savingsRealisedPaise: number;
  readonly feesPaise: number;
  readonly automaticUnitPricePaise: number;
  readonly request: NegotiatePriceRequest;
}

const paisePerRupee = 100;

function rupees(paise: number): string {
  return (paise / paisePerRupee).toFixed(2);
}

export function buildNegotiationResponse(
  params: BuildNegotiationResponseParams
): NegotiatePriceResponse {
  const { request, listUnitPricePaise, automaticUnitPricePaise, outcome, agreement } = params;
  const converged = outcome.agreedUnitPricePaise !== null;
  const agreedPaise = outcome.agreedUnitPricePaise ?? 0;

  // Bindable means "this is the number you will be charged", so it is false when the automatic
  // stack already prices at or below the bargain. The agreement is still on record and the quoter
  // still takes the lower of the two -- but reporting a figure the buyer will not pay, in either
  // direction, is the failure this field exists to prevent.
  const bindable = agreement !== undefined && agreedPaise < automaticUnitPricePaise;
  const savingsRealisedPaise = bindable ? automaticUnitPricePaise - agreedPaise : 0;
  const status = outcome.declinedReason !== null ? "DECLINED" : converged ? "CONVERGED" : "EXHAUSTED";

  return negotiatePriceResponseSchema.parse({
    sku_id: request.sku_id,
    quantity: request.quantity,
    currency: currencyInr,
    status,
    list_unit_price_paise: listUnitPricePaise,
    agreed_unit_price_paise: outcome.agreedUnitPricePaise,
    savings_vs_list_paise: converged ? Math.max(0, listUnitPricePaise - agreedPaise) : 0,
    savings_realised_paise: savingsRealisedPaise,
    agreed_price_is_bindable: bindable,
    turns: [...outcome.turns],
    turns_used: outcome.turns.length,
    micro_fees_paid_paise: outcome.cumulativeFeesPaise,
    escrow_refunded_paise: params.refundedPaise,
    contract_ast_hash: outcome.contractAstHash,
    declined_reason: outcome.declinedReason,
    next_step: describeNextStep({
      bindable,
      converged,
      declinedReason: outcome.declinedReason,
      savingsRealisedPaise,
      feesPaise: outcome.cumulativeFeesPaise,
      automaticUnitPricePaise,
      request
    })
  });
}

/**
 * Said in the result rather than left to the agent to work out, because the useful next move
 * differs by outcome and the unhelpful one -- quoting anyway and misreporting what happened -- is
 * the default an agent falls into when a tool just returns a status code.
 */
export function describeNextStep(facts: NextStepFacts): string {
  if (facts.declinedReason !== null) {
    return (
      `${facts.declinedReason} Nothing was charged for asking. Call get_live_sku_quote and buy at ` +
      "the listed price; negotiating this SKU again will get the same answer until the merchant " +
      "enables it."
    );
  }
  if (!facts.converged) {
    return (
      "No agreement: the turn budget ran out with a spread still open. Either raise " +
      "max_unit_price_paise and negotiate again, or call get_live_sku_quote to buy at list price."
    );
  }
  if (!facts.bindable) {
    return (
      "Agreed, and on record -- but it changes nothing: this SKU already prices at " +
      `₹${rupees(facts.automaticUnitPricePaise)} through discounts you would have received ` +
      "anyway, at or below the agreed figure. get_live_sku_quote will charge the lower of the " +
      "two. Report the saving from bargaining as ₹0."
    );
  }
  return _describeBindableNextStep(facts);
}

function _describeBindableNextStep(facts: NextStepFacts): string {
  const binding =
    "Agreed and BINDABLE. Call get_live_sku_quote for this SKU with the same buyer_agent_id " +
    `(${facts.request.buyer_agent_id}) and quantity ${facts.request.quantity} within ` +
    `${agreedPriceValiditySeconds}s: the quote will carry the agreed price as a NEGOTIATED line ` +
    "in applied_discounts, and the cart and settlement follow it. A different buyer_agent_id or " +
    "quantity gets the ordinary price -- the agreement is scoped to the purchase it was struck for.";

  if (facts.savingsRealisedPaise <= facts.feesPaise) {
    return (
      `${binding} Note the ₹${rupees(facts.savingsRealisedPaise)} saved did not cover the ` +
      `₹${rupees(facts.feesPaise)} of negotiation fees, so this SKU was barely worth bargaining ` +
      "over. Report the saving as savings_realised_paise and the fees beside it."
    );
  }
  return (
    `${binding} Report the saving as ₹${rupees(facts.savingsRealisedPaise)} per unit -- that is ` +
    "savings_realised_paise, what the bargaining added beyond the discounts already on offer. Do " +
    "not report savings_vs_list_paise as money kept; it counts those discounts twice."
  );
}
