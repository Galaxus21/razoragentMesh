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
  delivery_pincode: z.string().regex(/^[1-9][0-9]{5}$/)
});

export type SkuQuoteRequest = z.infer<typeof skuQuoteRequestSchema>;

export const skuQuoteResponseSchema = z.object({
  sku_id: z.string(),
  available_stock: z.number().int().min(0),
  base_unit_price_paise: z.number().int().min(0),
  offered_unit_price_paise: z.number().int().min(0),
  currency: z.literal(currencyInr),
  hsn_code: z.string(),
  gst_rate_percent: z.number(),
  tax_breakdown: z.object({
    cgst_paise: z.number().int().min(0),
    sgst_paise: z.number().int().min(0),
    igst_paise: z.number().int().min(0),
    total_tax_paise: z.number().int().min(0)
  }),
  quote_expiry_timestamp: z.number().int().positive(),
  quote_hash: z.string().min(1)
});

export type SkuQuoteResponse = z.infer<typeof skuQuoteResponseSchema>;
