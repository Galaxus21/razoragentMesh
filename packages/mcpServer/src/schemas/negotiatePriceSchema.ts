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
   * CONVERGED -- the two sides met; agreed_unit_price_paise is bindable.
   * EXHAUSTED -- the turn budget ran out with a spread still open; nothing was agreed.
   */
  status: z.enum(["CONVERGED", "EXHAUSTED"]),
  list_unit_price_paise: z.number().int().min(0),
  // Null unless status is CONVERGED. A number here is the seller's final ask, which is at or
  // below the buyer's final bid -- so the buyer never pays more than it offered.
  agreed_unit_price_paise: z.number().int().min(0).nullable(),
  savings_vs_list_paise: z.number().int().min(0),
  turns: z.array(negotiationTurnSchema),
  turns_used: z.number().int().min(0),
  // What the negotiation itself cost, debited from the micro-escrow one turn at a time. Reported
  // because it is real money and a saving smaller than the fees is not a saving.
  micro_fees_paid_paise: z.number().int().min(0),
  escrow_refunded_paise: z.number().int().min(0),
  // The gateway compiles an immutable contract AST on convergence. Null when EXHAUSTED.
  contract_ast_hash: z.string().nullable(),
  next_step: z.string().min(1)
});

export type NegotiatePriceResponse = z.infer<typeof negotiatePriceResponseSchema>;
