// The compiled fixtures are quotable from the in-process store but were never indexed, so
// search_catalog could not find SKU-CHAIR-001 by searching for an office chair. These tests pin
// the wire mapping -- UniversalProductListing is extra="forbid", so a stray field is a 422, not
// a warning -- and the contract that indexing can never block or fail boot.

import { describe, it } from "node:test";
import assert from "node:assert/strict";
import {
  fixtureMerchantDid,
  indexCompiledFixtures,
  toUniversalListing
} from "../src/catalog/fixtureIndexer.js";
import { initialCatalogFixtures } from "../src/catalog/catalogFixtures.js";

const allowedListingKeys = new Set([
  "skuId", "merchantDid", "title", "description", "category", "hsnCode", "gstRatePercent",
  "baseUnitPricePaise", "availableStock", "originPincode", "currency", "volumeTiers",
  "minimumOrderQuantity", "promotions", "jewelryFacet", "apparelFacet", "pharmaFacet", "fmcgFacet"
]);

describe("compiled fixture indexing", () => {
  it("maps every fixture onto fields UniversalProductListing accepts", () => {
    // extra="forbid" on the parent model, so brand, weightGrams and dimensionsCm must be dropped
    // rather than passed through: sending them is a 422 and the SKU never gets indexed at all.
    for (const sku of initialCatalogFixtures) {
      const listing = toUniversalListing(sku);
      for (const key of Object.keys(listing)) {
        assert.ok(allowedListingKeys.has(key), `${sku.skuId} would be rejected for '${key}'`);
      }
      assert.equal(listing.title, sku.name, "name is 'title' on the wire");
      assert.equal(listing.merchantDid, fixtureMerchantDid);
      assert.ok(typeof listing.originPincode === "string" && listing.originPincode.length === 6);
      assert.equal(listing.skuId, sku.skuId);
    }
  });

  it("carries the chair that search could not previously find", () => {
    const chair = initialCatalogFixtures.find((sku) => sku.skuId === "SKU-CHAIR-001");
    assert.ok(chair);
    const listing = toUniversalListing(chair);
    assert.match(String(listing.title), /Office Chair/);
    assert.deepEqual(listing.volumeTiers, chair.volumeTiers.map((t) => ({
      minQuantity: t.minQuantity,
      discountBps: t.discountBps
    })));
  });

  it("never rejects when merchant-api is unreachable, because boot must not depend on it", async () => {
    // compose gates mcp-server on the seeder completing, NOT on merchant-api being healthy, so a
    // cold start racing merchant-api is expected rather than exceptional.
    const realFetch = globalThis.fetch;
    globalThis.fetch = (async () => {
      throw new Error("ECONNREFUSED");
    }) as unknown as typeof globalThis.fetch;
    try {
      const summary = await indexCompiledFixtures(initialCatalogFixtures.slice(0, 2));
      assert.equal(summary.published, 0);
      assert.equal(summary.failed, 2);
    } finally {
      globalThis.fetch = realFetch;
    }
  });

  it("posts each fixture to the merchant catalog route", async () => {
    const posted: Array<{ url: string; body: Record<string, unknown> }> = [];
    const realFetch = globalThis.fetch;
    globalThis.fetch = (async (url: string, init: { body: string }) => {
      posted.push({ url: String(url), body: JSON.parse(init.body) as Record<string, unknown> });
      return { ok: true, status: 201 } as Response;
    }) as unknown as typeof globalThis.fetch;
    try {
      const summary = await indexCompiledFixtures(initialCatalogFixtures.slice(0, 3));
      assert.equal(summary.published, 3);
      assert.equal(summary.failed, 0);
    } finally {
      globalThis.fetch = realFetch;
    }
    assert.equal(posted.length, 3);
    assert.ok(posted[0].url.includes("/api/v1/merchant/"));
    assert.ok(posted[0].url.endsWith("/catalog"));
  });
});
