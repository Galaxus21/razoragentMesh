// browse_catalog -- enumerates the catalog the mesh can actually quote.
//
// Discovery was semantic-search-only, so an agent that could not phrase a good query had no way
// to find out what exists at all: search_catalog needs Qdrant and returns a ranked guess, and a
// SKU absent from the index is invisible even though the quoting path can price it perfectly.
// This reads the same in-process CatalogStore singleton that get_live_sku_quote and
// reserve_inventory_lock read, so what it lists is exactly what the mesh can sell -- no HTTP
// hop, no vector index, and no way for the two to disagree.

import { defaultCatalogStore, CatalogStore } from "../catalog/catalogStore.js";
import { resolveNextPromotion } from "../catalog/promotionResolver.js";
import { millisPerSecond } from "../constants/protocolConstants.js";
import {
  browseCatalogRequestSchema,
  browseCatalogResponseSchema,
  type BrowseCatalogResponse
} from "../schemas/catalogBrowseSchema.js";

export const browsePriceDisclaimer =
  "base_unit_price_paise is the list price before volume tiers, campaigns and promo codes, and " +
  "excludes GST and shipping. Call get_live_sku_quote for a binding price and a quote_hash. " +
  "next_promotion is a sale the merchant has scheduled for later, not a price you can take now.";

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
  const evaluated = matches.map((sku) => ({ sku, nextPromotion: resolveNextPromotion(sku, currentTimeUnix) }));
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
