import { z } from "zod";
import {
  minQuantity,
  maxQuantity,
  currencyInr
} from "../constants/protocolConstants.js";

export const skuQuoteRequestSchema = z.object({
  sku_id: z.string().regex(/^SKU-[A-Z0-9_-]{3,32}$/),
  quantity: z.number().int().min(minQuantity).max(maxQuantity),
  buyer_agent_id: z.string().regex(/^did:agent:[a-z0-9_\-\.:]+$/),
  delivery_pincode: z.string().regex(/^[1-9][0-9]{5}$/),
  promo_code: z.string().optional()
});

export type SkuQuoteRequest = z.infer<typeof skuQuoteRequestSchema>;

export const appliedDiscountItemSchema = z.object({
  type: z.enum([
    "VOLUME_TIER",
    "SCHEDULED_PROMOTION",
    "CAMPAIGN",
    "PAYMENT_RAIL",
    "PROMO_CODE",
    "NEGOTIATED"
  ]),
  label: z.string(),
  discountBps: z.number().int().optional(),
  discountPaise: z.number().int().min(0).optional()
});

export type AppliedDiscountItemSchema = z.infer<typeof appliedDiscountItemSchema>;

export const upcomingPromotionSchema = z.object({
  campaign_id: z.string().min(1),
  name: z.string().min(1),
  starts_at_unix: z.number().int().positive(),
  ends_at_unix: z.number().int().positive(),
  expected_unit_price_paise: z.number().int().min(0),
  expected_savings_paise: z.number().int().min(0),
  limited_stock_allocated: z.number().int().min(0).optional()
});

export type UpcomingPromotionSchema = z.infer<typeof upcomingPromotionSchema>;

export const skuQuoteResponseSchema = z.object({
  sku_id: z.string(),
  available_stock: z.number().int().min(0),
  base_unit_price_paise: z.number().int().min(0),
  offered_unit_price_paise: z.number().int().min(0),
  currency: z.literal(currencyInr),
  hsn_code: z.string(),
  // The catalog's category for this SKU. It travels on the quote so create_cart_mandate can
  // put it in the merchant-signed cart, where the settlement budget gate checks it against the
  // delegation's authorized_categories. Sourced from the mesh's own catalog on every quote --
  // an agent-supplied category would let the agent name whichever one it was authorized for.
  category: z.string().min(1),
  gst_rate_percent: z.number(),
  tax_breakdown: z.object({
    cgst_paise: z.number().int().min(0),
    sgst_paise: z.number().int().min(0),
    igst_paise: z.number().int().min(0),
    total_tax_paise: z.number().int().min(0)
  }),
  quote_expiry_timestamp: z.number().int().positive(),
  quote_hash: z.string().min(1),
  applied_discounts: z.array(appliedDiscountItemSchema).optional(),
  total_savings_paise: z.number().int().min(0).optional(),
  upcoming_promotions: z.array(upcomingPromotionSchema).optional()
});

export type SkuQuoteResponse = z.infer<typeof skuQuoteResponseSchema>;
