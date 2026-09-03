// Wire schema for create_cart_mandate. See establishDelegationSchema.ts for why the mandate
// tools' schemas live here rather than inline beside their tools.

import { z } from "zod";
import {
  defaultMerchantAccount,
  defaultPackageWeightGrams,
  stateCodeRegex
} from "../constants/mandateToolConstants.js";
import { maxQuantity, minQuantity } from "../constants/protocolConstants.js";

export const createCartMandateRequestSchema = z.object({
  delegation_id: z.string().min(1),
  sku_id: z.string().regex(/^SKU-[A-Z0-9_-]{3,32}$/),
  quantity: z.number().int().min(minQuantity).max(maxQuantity),
  delivery_pincode: z.string().regex(/^[1-9][0-9]{5}$/),
  // Length alone is not enough: merchantStateCode and this value decide intra- vs inter-state
  // GST by raw string equality, so a non-numeric code would silently route down the IGST branch.
  delivery_state_code: z.string().regex(stateCodeRegex),
  promo_code: z.string().optional(),
  package_weight_grams: z.number().int().min(1).default(defaultPackageWeightGrams),
  quote_hash: z.string().min(1),
  lock_token: z.string().min(1),
  fencing_token: z.number().int().min(1),
  lock_expires_at_unix_ms: z.number().int().min(1),
  lock_signature: z.string().min(1),
  merchant_account: z.string().min(1).default(defaultMerchantAccount)
});

export type CreateCartMandateRequest = z.infer<typeof createCartMandateRequestSchema>;

export const createCartMandateResponseSchema = z.object({
  // The complete merchant-signed CartMandate. Shape owned by the buyer SDK.
  cart_mandate: z.record(z.unknown()),
  cart_mandate_hash: z.string().min(1),
  total_paise: z.number().int().min(0),
  taxable_subtotal_paise: z.number().int().min(0),
  tax_breakdown: z.object({
    cgst_paise: z.number().int().min(0),
    sgst_paise: z.number().int().min(0),
    igst_paise: z.number().int().min(0),
    total_tax_paise: z.number().int().min(0)
  }),
  shipping_fee_paise: z.number().int().min(0),
  // Always 0. The enclave recomputes the subtotal from already-post-discount unit prices, so a
  // non-zero value here would be deducted twice and the cart would be rejected.
  discount_paise: z.number().int().min(0),
  discount_rationale: z.string().min(1),
  // SECONDS, converted from the lock tool's milliseconds so the settlement enclave's
  // `evaluatedAt > inventoryLockExpiresAt` comparison can actually fire.
  inventory_lock_expires_at: z.number().int().positive(),
  inventory_lock_expires_at_unit: z.literal("unix_seconds"),
  merchant_did: z.string().min(1),
  price_reconciled: z.boolean()
});

export type CreateCartMandateResponse = z.infer<typeof createCartMandateResponseSchema>;
