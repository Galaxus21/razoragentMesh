// browse_catalog -- enumerates the catalog the mesh can actually quote.
//
// Discovery was semantic-search-only, so an agent that could not phrase a good query had no way
// to find out what exists at all: search_catalog needs Qdrant and returns a ranked guess, and a
// SKU absent from the index is invisible even though the quoting path can price it perfectly.
// This reads the same in-process CatalogStore singleton that get_live_sku_quote and
// reserve_inventory_lock read, so what it lists is exactly what the mesh can sell -- no HTTP
// hop, no vector index, and no way for the two to disagree.

import { defaultCatalogStore, CatalogStore } from "../catalog/catalogStore.js";
import { evaluateScheduledPromotions } from "../catalog/pricingEngine.js";
import { millisPerSecond } from "../constants/protocolConstants.js";
import type { CatalogSkuItem, UpcomingPromotion } from "../types/mcpToolTypes.js";
import {
  browseCatalogRequestSchema,
  browseCatalogResponseSchema,
  type BrowseCatalogResponse
} from "../schemas/catalogBrowseSchema.js";

export const browsePriceDisclaimer =
  "base_unit_price_paise is the list price before volume tiers, campaigns and promo codes, and " +
  "excludes GST and shipping. Call get_live_sku_quote for a binding price and a quote_hash. " +
  "next_promotion is a sale the merchant has scheduled for later, not a price you can take now.";

/**
 * The soonest sale scheduled for this SKU, or undefined when none is.
 *
 * Until this existed, a scheduled sale was reachable only one SKU at a time through
 * get_live_sku_quote's upcoming_promotions, so an agent could not ask what is on sale without
 * quoting the whole catalog. It reuses the quote's evaluator rather than reimplementing the
 * arithmetic, so the two surfaces cannot drift.
 *
 * Ties break on campaign_id: two sales starting the same second must order the same way on every
 * call, or a page boundary would show one of them twice.
 */
function _resolveNextPromotion(
  sku: CatalogSkuItem,
  currentTimeUnix: number
): UpcomingPromotion | undefined {
  if (!sku.promotions || sku.promotions.length === 0) {
    return undefined;
  }

  let upcoming: readonly UpcomingPromotion[];
  try {
    upcoming = evaluateScheduledPromotions(sku.baseUnitPricePaise, sku.promotions, currentTimeUnix)
      .upcomingPromotions;
  } catch {
    // evaluateScheduledPromotions throws on a promotion it cannot price -- an inverted window, or
    // a fixed price above the list price. The TypeScript schema does not reject either
    // (mcpToolTypes.ts scheduledPromotionSchema checks types, not the relationship between the
    // two timestamps); only merchantApi's Pydantic model does, so a listing that reached the store
    // by another route can carry one. In a quote that costs one SKU. Here it would cost the whole
    // catalog listing, and enumerating what the mesh can sell is the one thing this tool owes an
    // agent -- so the SKU stays listed and simply reports no scheduled sale.
    return undefined;
  }

  return [...upcoming].sort(
    (left, right) =>
      left.starts_at_unix - right.starts_at_unix || left.campaign_id.localeCompare(right.campaign_id)
  )[0];
}

export function browseCatalog(
  rawRequest: unknown,
  catalogStore: CatalogStore = defaultCatalogStore,
  currentTimeUnix: number = Math.floor(Date.now() / millisPerSecond)
): BrowseCatalogResponse {
  const request = browseCatalogRequestSchema.parse(rawRequest);

  const matches = catalogStore.filterSkus({
    category: request.category,
    hsnCode: request.hsn_code,
    brand: request.brand,
    minStock: request.min_stock
  });

  // Resolved across every match rather than on the page, because has_upcoming_promotion filters
  // and total_matching has to count what the filter matched -- not what survived into a page.
  const evaluated = matches.map((sku) => ({ sku, nextPromotion: _resolveNextPromotion(sku, currentTimeUnix) }));
  const selected =
    request.has_upcoming_promotion === undefined
      ? evaluated
      : evaluated.filter((entry) => (entry.nextPromotion !== undefined) === request.has_upcoming_promotion);

  // Stable ordering. filterSkus preserves the store's insertion order, which changes as live
  // catalog updates arrive over pub/sub -- so paging with offset would otherwise skip or repeat
  // items whenever a merchant published mid-browse.
  const ordered = [...selected].sort((left, right) => left.sku.skuId.localeCompare(right.sku.skuId));
  const page = ordered.slice(request.offset, request.offset + request.limit);

  // Drawn from the whole catalog, not from this page, so an agent that filtered itself into an
  // empty result can see what it could have asked for instead.
  const categoriesAvailable = [
    ...new Set(catalogStore.getAllSkus().map((sku) => sku.category))
  ].sort();

  return browseCatalogResponseSchema.parse({
    items: page.map(({ sku, nextPromotion }) => ({
      sku_id: sku.skuId,
      name: sku.name,
      category: sku.category,
      ...(sku.brand === undefined ? {} : { brand: sku.brand }),
      hsn_code: sku.hsnCode,
      gst_rate_percent: sku.gstRatePercent,
      base_unit_price_paise: sku.baseUnitPricePaise,
      available_stock: sku.availableStock,
      ...(nextPromotion === undefined ? {} : { next_promotion: nextPromotion })
    })),
    total_matching: ordered.length,
    returned: page.length,
    offset: request.offset,
    categories_available: categoriesAvailable,
    price_disclaimer: browsePriceDisclaimer
  });
}
