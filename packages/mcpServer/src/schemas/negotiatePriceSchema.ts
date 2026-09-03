// Wire schema for negotiate_price.
//
// Lives here rather than beside the tool for the same reason the mandate schemas do: the
// dashboard's generateSdkReference.ts reads the schemas barrel and pairs each `<Name>Request`
// with its `<Name>Response`, so a schema declared inline is invisible to doc verification.

import { z } from "zod";
import { minQuantity, maxQuantity, currencyInr } from "../constants/protocolConstants.js";
import { maxNegotiationTurns } from "../constants/negotiationConstants.js";

export const negotiatePriceRequestSchema = z
  .object({
    sku_id: z.string().regex(/^SKU-[A-Z0-9_-]{3,32}$/),
    quantity: z.number().int().min(minQuantity).max(maxQuantity),
    buyer_agent_id: z.string().regex(/^did:agent:[a-z0-9_\-\.:]+$/),
    // The buyer's opening offer. Below the list price or the negotiation is pointless.
    opening_bid_paise: z.number().int().positive(),
    // The reservation price -- the most this agent will pay per unit. This is a hard ceiling,
    // not a target: the bid ladder approaches it and never crosses it, so a converged result is
    // always at or below this number and the caller can commit to it without re-checking.
    max_unit_price_paise: z.number().int().positive(),
    merchant_did: z.string().min(1).optional(),
    // Capped at the gateway's own limit. Asking for more would be refused turn by turn after the
    // escrow had already been charged for the turns that did run.
    max_turns: z.number().int().min(1).max(maxNegotiationTurns).default(maxNegotiationTurns)
  })
  .refine((value) => value.max_unit_price_paise >= value.opening_bid_paise, {
    // Checked here rather than in the tool so it costs nothing: no escrow session is opened and
    // no micro-fee is charged for a request that could never converge.
    message: "max_unit_price_paise must be greater than or equal to opening_bid_paise",
    path: ["max_unit_price_paise"]
  });

export type NegotiatePriceRequest = z.infer<typeof negotiatePriceRequestSchema>;

/** One completed alternating-offer turn, as the gateway recorded it. */
export const negotiationTurnSchema = z.object({
  turn_number: z.number().int().positive(),
  buyer_bid_paise: z.number().int().min(0),
  seller_ask_paise: z.number().int().min(0),
  spread_paise: z.number().int().min(0),
  converged: z.boolean(),
  micro_fee_paise: z.number().int().min(0),
  cumulative_micro_fees_paise: z.number().int().min(0)
});

export type NegotiationTurn = z.infer<typeof negotiationTurnSchema>;

export const negotiatePriceResponseSchema = z.object({
  sku_id: z.string().min(1),
  quantity: z.number().int().positive(),
  currency: z.literal(currencyInr),
  /**
   * CONVERGED -- the two sides met on agreed_unit_price_paise. get_live_sku_quote will price the
   *              purchase with it, for the same buyer_agent_id and quantity, until the agreement
   *              lapses. Read agreed_price_is_bindable before reporting it: the quoter always
   *              charges the LOWER of the agreed price and the automatic discounts, so an
   *              agreement that loses to a live sale changes nothing.
   * EXHAUSTED -- the turn budget ran out with a spread still open; nothing was agreed.
   * DECLINED  -- this merchant does not negotiate. Not a failure: their listed price is the
   *              price, and no micro-fee was charged for asking.
   */
  status: z.enum(["CONVERGED", "EXHAUSTED", "DECLINED"]),
  list_unit_price_paise: z.number().int().min(0),
  // Null unless status is CONVERGED. A number here is the seller's final ask, which is at or
  // below the buyer's final bid -- so the buyer never pays more than it offered.
  agreed_unit_price_paise: z.number().int().min(0).nullable(),
  // The agreed price against the LIST price. Not what the bargaining won: the mesh's automatic
  // discounts would have come off anyway, so this figure counts them a second time. Reported
  // because it is what the negotiation achieved on paper against the sticker.
  savings_vs_list_paise: z.number().int().min(0),
  /**
   * What the buyer actually keeps: the agreed price measured against what get_live_sku_quote
   * would have charged anyway, per unit. Zero when the automatic stack already wins.
   *
   * Added after a 2026-09-03 run in which nine negotiations converged, all nine paid the ordinary
   * list-based quote, and one agent told its user "Agreed Price: ₹41,338.50 (Savings: ₹661.50)"
   * before charging ₹49,584.62. It read zero then, because a bargain bound nothing. Now that one
   * does, this is the only figure in the response that is money the buyer keeps -- report it, and
   * not savings_vs_list_paise.
   */
  savings_realised_paise: z.number().int().min(0),
  /**
   * True when the agreed price is the one the buyer will be charged.
   *
   * False in two different situations, and the distinction matters: the negotiation did not
   * converge, or it converged and lost to the merchant's own automatic discounts. next_step says
   * which. Either way, quoting the agreed figure to a buyer when this is false names a price
   * nobody will pay.
   */
  agreed_price_is_bindable: z.boolean(),
  turns: z.array(negotiationTurnSchema),
  turns_used: z.number().int().min(0),
  // What the negotiation itself cost, debited from the micro-escrow one turn at a time. Reported
  // because it is real money and a saving smaller than the fees is not a saving.
  micro_fees_paid_paise: z.number().int().min(0),
  escrow_refunded_paise: z.number().int().min(0),
  // The gateway compiles an immutable contract AST on convergence. Null otherwise.
  contract_ast_hash: z.string().nullable(),
  // Set only when status is DECLINED, in the merchant's own terms -- whether they have switched
  // negotiation off, never configured it, or the gateway could not check. The last of those is
  // worth retrying and the others are not, so the distinction is preserved rather than flattened.
  declined_reason: z.string().nullable(),
  next_step: z.string().min(1)
});

export type NegotiatePriceResponse = z.infer<typeof negotiatePriceResponseSchema>;
