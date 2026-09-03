// browse_catalog reads the same in-process CatalogStore the quoting tools read, so the thing it
// has to guarantee is that what it lists is what the mesh can actually sell -- and that paging
// stays stable while live catalog updates arrive over pub/sub.

import { describe, it } from "node:test";
import assert from "node:assert/strict";
import { browseCatalog } from "../src/tools/catalogBrowser.js";
import { executeTool } from "../src/tools/toolRegistry.js";
import { defaultCatalogStore } from "../src/catalog/catalogStore.js";
import { toolBrowseCatalog } from "../src/constants/protocolConstants.js";
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
