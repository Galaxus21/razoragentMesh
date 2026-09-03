// Wire schema for browse_catalog.
//
// Lives here rather than beside the tool for the same reason the mandate schemas do: the
// dashboard's generateSdkReference.ts reads the schemas barrel and pairs each `<Name>Request`
// with its `<Name>Response`, so a schema declared inline is invisible to doc verification.

import { z } from "zod";
import { upcomingPromotionSchema } from "./skuQuoteSchema.js";

export const minBrowseLimit = 1;
export const maxBrowseLimit = 100;
export const defaultBrowseLimit = 25;

export const browseCatalogRequestSchema = z.object({
  category: z.string().min(1).optional(),
  hsn_code: z.string().min(1).optional(),
  brand: z.string().min(1).optional(),
  // Defaults to 1 rather than 0: an agent browsing for something to buy is asking what it can
  // actually order, and a listing it cannot lock is noise. Pass 0 explicitly to include those.
  min_stock: z.number().int().min(0).default(1),
  // Tri-state on purpose. Absent is "do not filter on promotions"; true is "only SKUs with a sale
  // scheduled"; false is "only SKUs with none", which is how an agent asks what it can buy now
  // without waiting for a better price.
  has_upcoming_promotion: z.boolean().optional(),
  limit: z.number().int().min(minBrowseLimit).max(maxBrowseLimit).default(defaultBrowseLimit),
  offset: z.number().int().min(0).default(0)
});

export type BrowseCatalogRequest = z.infer<typeof browseCatalogRequestSchema>;

const browseCatalogItemSchema = z.object({
  sku_id: z.string().min(1),
  name: z.string().min(1),
  category: z.string().min(1),
  brand: z.string().optional(),
  hsn_code: z.string().min(1),
  gst_rate_percent: z.number(),
  // The list price before any volume tier, campaign or promo code. get_live_sku_quote is the
  // only thing that produces a bindable number, so this is deliberately named as a base price.
  base_unit_price_paise: z.number().int().min(0),
  available_stock: z.number().int().min(0),
  // The soonest sale this merchant has SCHEDULED for the SKU, in the same shape and from the same
  // evaluator get_live_sku_quote reports as upcoming_promotions -- so the two surfaces cannot
  // disagree about what is coming. Absent means no future sale is on the books, which is a
  // different statement from "there is no discount": campaigns, tiers and promo codes all price
  // at quote time and are not promotions. Only FUTURE windows appear, matching the quote.
  next_promotion: upcomingPromotionSchema.optional()
});

export const browseCatalogResponseSchema = z.object({
  items: z.array(browseCatalogItemSchema),
  /** Matches BEFORE limit and offset, so an agent can tell a short page from the last page. */
  total_matching: z.number().int().min(0),
  returned: z.number().int().min(0),
  offset: z.number().int().min(0),
  categories_available: z.array(z.string()),
  price_disclaimer: z.string().min(1)
});

export type BrowseCatalogResponse = z.infer<typeof browseCatalogResponseSchema>;
