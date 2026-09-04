// The soonest scheduled sale on a SKU, shared by every surface that has to mention one.
//
// browse_catalog and search_catalog both answer "what could I buy", and an agent that sees a
// sale on one and not the other has been told two different things about the same catalog. The
// resolution lives here so neither tool owns it: get_live_sku_quote's evaluator does the
// arithmetic, and both discovery surfaces read the same answer out of it.

import { evaluateScheduledPromotions } from "./pricingEngine.js";
import type { CatalogSkuItem, UpcomingPromotion } from "../types/mcpToolTypes.js";

/**
 * The soonest sale scheduled for this SKU, or undefined when none is.
 *
 * Ties break on campaign_id: two sales starting the same second must order the same way on every
 * call, or a page boundary would show one of them twice.
 */
export function resolveNextPromotion(
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
    // by another route can carry one. In a quote that costs one SKU. On a discovery surface it
    // would cost the whole listing, and enumerating what the mesh can sell is the one thing those
    // tools owe an agent -- so the SKU stays listed and simply reports no scheduled sale.
    return undefined;
  }

  return [...upcoming].sort(
    (left, right) =>
      left.starts_at_unix - right.starts_at_unix || left.campaign_id.localeCompare(right.campaign_id)
  )[0];
}
