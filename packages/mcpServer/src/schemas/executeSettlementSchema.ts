// Wire schema for execute_settlement. See establishDelegationSchema.ts for why the mandate
// tools' schemas live here rather than inline beside their tools.

import { z } from "zod";
import { signatureHexLength } from "../constants/mandateToolConstants.js";
import { currencyInr } from "../constants/protocolConstants.js";

export const executeSettlementRequestSchema = z.object({
  delegation_id: z.string().min(1),
  execution_id: z.string().min(1),
  // Required in agent_held mode, rejected in mesh_demo_custodial mode, so the two custody
  // modes cannot be mixed into a chain whose signer is ambiguous.
  agent_signature: z.string().length(signatureHexLength).optional(),
  // Accepted but never authoritative. The payout destination is resolved from the SIGNED cart's
  // merchantDid (merchant/merchantPayoutRegistry.ts); a value here that differs from that
  // resolution is refused. It used to be the opposite -- this field overrode the account bound at
  // cart creation, and nothing checked it against anything the merchant had signed, so any
  // `acc_...` string redirected the merchant leg of the split.
  merchant_account: z.string().min(1).optional(),
  // Opt-in escape from the same-session duplicate guard. Buying the identical cart twice in one
  // session is nearly always an agent that lost track of a settlement it already made, so it is
  // refused by default and the agent has to say it meant it.
  allow_repeat_purchase: z.boolean().optional()
});

export type ExecuteSettlementRequest = z.infer<typeof executeSettlementRequestSchema>;

export const settlementTransferSchema = z.object({
  id: z.string().min(1),
  entity: z.string().min(1),
  account: z.string().min(1),
  amount: z.number().int().min(0),
  currency: z.literal(currencyInr),
  status: z.string().min(1),
  createdAt: z.number().int().positive()
});

export type SettlementTransferSchema = z.infer<typeof settlementTransferSchema>;

export const settlementInvoiceLineItemSchema = z.object({
  skuId: z.string().min(1),
  hsnCode: z.string().min(1),
  quantity: z.number().int().positive(),
  unitPricePaise: z.number().int().min(0),
  taxableAmountPaise: z.number().int().min(0),
  gstRatePercent: z.number(),
  cgstPaise: z.number().int().min(0),
  sgstPaise: z.number().int().min(0),
  igstPaise: z.number().int().min(0),
  totalLinePaise: z.number().int().min(0)
});

export type SettlementInvoiceLineItemSchema = z.infer<typeof settlementInvoiceLineItemSchema>;

export const settlementInvoiceSchema = z.object({
  invoiceNumber: z.string().min(1),
  invoiceDate: z.string().min(1),
  sellerGstin: z.string().min(1),
  merchantStateCode: z.string().min(1),
  placeOfSupplyStateCode: z.string().min(1),
  isIntraState: z.boolean(),
  lineItems: z.array(settlementInvoiceLineItemSchema),
  taxableAmountPaise: z.number().int().min(0),
  totalCgstPaise: z.number().int().min(0),
  totalSgstPaise: z.number().int().min(0),
  totalIgstPaise: z.number().int().min(0),
  totalTaxPaise: z.number().int().min(0),
  totalTcsPaise: z.number().int().min(0),
  shippingPaise: z.number().int().min(0),
  discountPaise: z.number().int().min(0),
  grandTotalPaise: z.number().int().min(0),
  cryptographicAuditHash: z.string().min(1)
});

export type SettlementInvoiceSchema = z.infer<typeof settlementInvoiceSchema>;

/**
 * The mandate engine's own SettlementResult, passed through verbatim.
 *
 * Note the casing: every other tool in this package speaks snake_case, but this document is
 * produced by the Python settlement engine and is NOT renamed on the way out. Renaming it here
 * would mean the field names in the guides no longer matched the bytes on the wire.
 */
export const executeSettlementResponseSchema = z.object({
  status: z.string().min(1),
  paymentId: z.string().min(1),
  amountPaise: z.number().int().min(0),
  transfers: z.array(settlementTransferSchema),
  invoice: settlementInvoiceSchema,
  settledAt: z.number().int().positive(),
  /**
   * The one field here the engine does NOT produce -- the mesh adds it, and only when the SKU
   * just bought has a sale opening soon. It sits on the receipt because that is the part of a
   * settlement agents reliably read back to their buyer; a sale stated in the quote is not.
   */
  buyerNotice: z.string().min(1).optional()
});

export type ExecuteSettlementResponse = z.infer<typeof executeSettlementResponseSchema>;
