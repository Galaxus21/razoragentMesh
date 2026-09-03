// browse_catalog reads the same in-process CatalogStore the quoting tools read, so the thing it
// has to guarantee is that what it lists is what the mesh can actually sell -- and that paging
// stays stable while live catalog updates arrive over pub/sub.

import { describe, it } from "node:test";
import assert from "node:assert/strict";
import { browseCatalog } from "../src/tools/catalogBrowser.js";
import { executeSkuQuote } from "../src/tools/skuQuoter.js";
import { executeTool } from "../src/tools/toolRegistry.js";
import { defaultCatalogStore, CatalogStore } from "../src/catalog/catalogStore.js";
import { toolBrowseCatalog, millisPerSecond } from "../src/constants/protocolConstants.js";
import type { CatalogSkuItem, ScheduledPromotion } from "../src/types/mcpToolTypes.js";
import type { BrowseCatalogResponse } from "../src/schemas/catalogBrowseSchema.js";

describe("browse_catalog", () => {
  it("enumerates the catalog an agent could not otherwise discover", () => {
    // Discovery was semantic-search-only: an agent that could not phrase a good query, or whose
    // target was missing from the vector index, had no way to learn what exists at all.
    const result = browseCatalog({});
    assert.ok(result.total_matching > 0);
    assert.ok(result.items.length > 0);
    assert.ok(result.categories_available.length > 0);
    assert.match(result.price_disclaimer, /get_live_sku_quote/);
  });

  it("lists SKUs the semantic index does not carry", () => {
    // SKU-CHAIR-001 is one of the compiled fixtures: quotable, but absent from Qdrant, so
    // search_catalog cannot find it. This is the gap browse_catalog closes.
    const found = browseCatalog({ limit: 100 }).items.some((item) => item.sku_id === "SKU-CHAIR-001");
    assert.ok(found, "the compiled fixtures must be browsable even when unindexed");
  });

  it("pages stably rather than in store insertion order", () => {
    // filterSkus returns insertion order, which changes as live catalog updates arrive -- so
    // paging on it would skip or repeat items whenever a merchant published mid-browse.
    const first = browseCatalog({ limit: 3, offset: 0 });
    const second = browseCatalog({ limit: 3, offset: 3 });
    const ids = [...first.items, ...second.items].map((item) => item.sku_id);
    assert.deepEqual(ids, [...ids].sort());
    assert.equal(new Set(ids).size, ids.length, "pages must not repeat a SKU");
    assert.equal(first.offset, 0);
    assert.equal(second.offset, 3);
  });

  it("reports total_matching before the page, so a short page is not read as the end", () => {
    const all = browseCatalog({ limit: 100 });
    const paged = browseCatalog({ limit: 2 });
    assert.equal(paged.returned, 2);
    assert.equal(paged.total_matching, all.total_matching);
    assert.ok(paged.total_matching > paged.returned);
  });

  it("filters by category case-insensitively and offers the categories it knows", () => {
    const anyCategory = browseCatalog({ limit: 100 }).items[0].category;
    const filtered = browseCatalog({ category: anyCategory.toUpperCase(), limit: 100 });
    assert.ok(filtered.items.length > 0);
    assert.ok(filtered.items.every((item) => item.category.toLowerCase() === anyCategory.toLowerCase()));
    assert.ok(filtered.categories_available.includes(anyCategory));
  });

  it("hides unorderable stock by default and includes it when asked", () => {
    const zeroStockSku = defaultCatalogStore.getAllSkus().find((sku) => sku.availableStock === 0);
    const defaulted = browseCatalog({ limit: 100 });
    assert.ok(defaulted.items.every((item) => item.available_stock >= 1));
    if (zeroStockSku) {
      const withOutOfStock = browseCatalog({ min_stock: 0, limit: 100 });
      assert.ok(withOutOfStock.total_matching >= defaulted.total_matching);
    }
  });

  it("is reachable through the tool registry under its manifest name", async () => {
    const result = (await executeTool(toolBrowseCatalog, { limit: 1 })) as BrowseCatalogResponse;
    assert.equal(result.returned, 1);
  });
});

// A scheduled sale used to be reachable one SKU at a time, through get_live_sku_quote's
// upcoming_promotions -- so an agent could only find out what was about to get cheaper by quoting
// all 47 listings. These cover the cross-catalog answer and the ways a merchant's own data can
// make it awkward.
describe("browse_catalog scheduled sales", () => {
  const nowUnix = Math.floor(Date.now() / millisPerSecond);
  const oneHour = 3600;

  function listing(skuId: string, promotions: readonly ScheduledPromotion[]): CatalogSkuItem {
    return {
      skuId,
      name: `Bench listing ${skuId}`,
      category: "Test Bench",
      description: "A listing published for the scheduled-sale tests.",
      hsnCode: "94013000",
      gstRatePercent: 18,
      baseUnitPricePaise: 100000,
      availableStock: 10,
      volumeTiers: [],
      promotions
    };
  }

  function promotion(
    campaignId: string,
    startsAtUnix: number,
    endsAtUnix: number
  ): ScheduledPromotion {
    return { campaignId, name: `Sale ${campaignId}`, startsAtUnix, endsAtUnix, discountBps: 2000 };
  }

  const benchStore = new CatalogStore([
    listing("SKU-BENCH-SALE", [promotion("CAMP-SOLO", nowUnix + oneHour, nowUnix + 2 * oneHour)]),
    listing("SKU-BENCH-PLAIN", []),
    listing("SKU-BENCH-PAST", [promotion("CAMP-DONE", nowUnix - 2 * oneHour, nowUnix - oneHour)]),
    listing("SKU-BENCH-ACTIVE", [promotion("CAMP-LIVE", nowUnix - oneHour, nowUnix + oneHour)]),
    listing("SKU-BENCH-MULTI", [
      promotion("CAMP-LATE", nowUnix + 2 * oneHour, nowUnix + 3 * oneHour),
      promotion("CAMP-SOON", nowUnix + oneHour, nowUnix + 2 * oneHour)
    ]),
    listing("SKU-BENCH-TIE", [
      promotion("CAMP-ZULU", nowUnix + oneHour, nowUnix + 2 * oneHour),
      promotion("CAMP-ALPHA", nowUnix + oneHour, nowUnix + 2 * oneHour)
    ]),
    // Inverted window: endsAtUnix <= startsAtUnix. merchantApi's Pydantic model rejects this, but
    // the TypeScript schema checks types and not the relationship between the two timestamps, so a
    // listing that reached the store by another route can carry one.
    listing("SKU-BENCH-BADWINDOW", [promotion("CAMP-BROKEN", nowUnix + 2 * oneHour, nowUnix + oneHour)])
  ]);

  function itemFor(response: BrowseCatalogResponse, skuId: string) {
    const item = response.items.find((candidate) => candidate.sku_id === skuId);
    assert.ok(item, `${skuId} must be listed`);
    return item;
  }

  it("reports the scheduled sale the quote reports, with the same numbers", () => {
    // Parity is the point: browse_catalog must not become a second opinion about the same sale.
    const browsed = itemFor(browseCatalog({ limit: 100 }, benchStore), "SKU-BENCH-SALE");
    const quoted = executeSkuQuote(
      {
        sku_id: "SKU-BENCH-SALE",
        quantity: 1,
        buyer_agent_id: "did:agent:bench_buyer",
        delivery_pincode: "560001"
      },
      benchStore
    );

    assert.ok(browsed.next_promotion);
    assert.deepEqual(browsed.next_promotion, quoted.upcoming_promotions?.[0]);
    assert.equal(browsed.next_promotion.campaign_id, "CAMP-SOLO");
    assert.equal(browsed.next_promotion.expected_savings_paise, 20000);
  });

  it("omits the field entirely when no sale is scheduled, rather than sending null", () => {
    const page = browseCatalog({ limit: 100 }, benchStore);
    assert.equal(itemFor(page, "SKU-BENCH-PLAIN").next_promotion, undefined);
    assert.ok(!("next_promotion" in itemFor(page, "SKU-BENCH-PLAIN")));
  });

  it("treats a finished sale and a running one alike: neither is a future saving", () => {
    // A promotion running right now is not something to wait for, and get_live_sku_quote does not
    // report it either. Parity matters more here than completeness.
    const page = browseCatalog({ limit: 100 }, benchStore);
    assert.equal(itemFor(page, "SKU-BENCH-PAST").next_promotion, undefined);
    assert.equal(itemFor(page, "SKU-BENCH-ACTIVE").next_promotion, undefined);
  });

  it("reports the soonest of several sales, breaking ties the same way every call", () => {
    const page = browseCatalog({ limit: 100 }, benchStore);
    assert.equal(itemFor(page, "SKU-BENCH-MULTI").next_promotion?.campaign_id, "CAMP-SOON");
    // Same start second: ordering has to be deterministic or a page boundary could repeat a SKU.
    assert.equal(itemFor(page, "SKU-BENCH-TIE").next_promotion?.campaign_id, "CAMP-ALPHA");
  });

  it("keeps listing a SKU whose promotion cannot be priced at all", () => {
    // The regression that matters: one merchant's inverted window used to be one SKU's problem in
    // a quote. Evaluating during enumeration would have made it the whole catalog's problem.
    const page = browseCatalog({ limit: 100 }, benchStore);
    assert.equal(page.total_matching, 7);
    assert.equal(itemFor(page, "SKU-BENCH-BADWINDOW").next_promotion, undefined);
  });

  it("filters to what is about to get cheaper, and counts the filter not the page", () => {
    const onSale = browseCatalog({ has_upcoming_promotion: true, limit: 100 }, benchStore);
    assert.deepEqual(
      onSale.items.map((item) => item.sku_id),
      ["SKU-BENCH-MULTI", "SKU-BENCH-SALE", "SKU-BENCH-TIE"]
    );
    assert.equal(onSale.total_matching, 3);
    assert.ok(onSale.items.every((item) => item.next_promotion !== undefined));

    // total_matching counts everything the filter matched, so a first page is not read as the end.
    const firstPage = browseCatalog({ has_upcoming_promotion: true, limit: 1 }, benchStore);
    assert.equal(firstPage.returned, 1);
    assert.equal(firstPage.total_matching, 3);
  });

  it("answers the opposite question too: what can I buy without waiting", () => {
    const notOnSale = browseCatalog({ has_upcoming_promotion: false, limit: 100 }, benchStore);
    assert.deepEqual(
      notOnSale.items.map((item) => item.sku_id),
      ["SKU-BENCH-ACTIVE", "SKU-BENCH-BADWINDOW", "SKU-BENCH-PAST", "SKU-BENCH-PLAIN"]
    );
    assert.ok(notOnSale.items.every((item) => item.next_promotion === undefined));
  });

  it("does not filter on promotions at all when the flag is omitted", () => {
    assert.equal(browseCatalog({ limit: 100 }, benchStore).total_matching, 7);
  });

  it("combines the promotion filter with the other filters", () => {
    const filtered = browseCatalog(
      { category: "test bench", has_upcoming_promotion: true, limit: 100 },
      benchStore
    );
    assert.equal(filtered.total_matching, 3);
    assert.equal(browseCatalog({ category: "Nothing Here", has_upcoming_promotion: true }, benchStore).total_matching, 0);
  });

  it("evaluates against the clock it is given, so a sale opens and closes on time", () => {
    const beforeStart = browseCatalog({ limit: 100 }, benchStore, nowUnix);
    assert.ok(itemFor(beforeStart, "SKU-BENCH-SALE").next_promotion);

    // Once the sale is running it stops being upcoming -- the same rule the quote applies.
    const afterStart = browseCatalog({ limit: 100 }, benchStore, nowUnix + oneHour + 1);
    assert.equal(itemFor(afterStart, "SKU-BENCH-SALE").next_promotion, undefined);
    assert.equal(browseCatalog({ has_upcoming_promotion: true, limit: 100 }, benchStore, nowUnix + oneHour + 1).total_matching, 1);
  });
});
