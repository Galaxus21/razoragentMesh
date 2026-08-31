import { describe, it } from "node:test";
import assert from "node:assert/strict";

import { CatalogStore } from "../src/catalog/catalogStore.js";
import {
  hydrateCatalogFromRedis,
  normalizeCatalogRecord,
  type RedisCatalogReader
} from "../src/catalog/catalogHydrator.js";
import { meshCatalogKeyPrefix, meshCatalogUpdatesChannel } from "../src/constants/protocolConstants.js";

// The store used to learn about merchant SKUs only from the pub/sub channel, which carries
// changes rather than state. So a restarted server forgot every published SKU, and the seeder
// script -- which writes Redis directly and has no subscriber to announce to -- produced a
// catalog the protocol path could not quote. These tests pin the boot-time read that fixes both.

const seededSkuId = "SKU-001";
const scanCompleteCursor = "0";

function buildRecord(skuId: string, overrides: Record<string, unknown> = {}): Record<string, unknown> {
  return {
    skuId,
    name: `Item ${skuId}`,
    category: "apparel",
    description: "A catalogued item.",
    hsnCode: "6205",
    gstRatePercent: 12,
    baseUnitPricePaise: 159000,
    availableStock: 40,
    volumeTiers: [],
    ...overrides
  };
}

function buildReader(records: Readonly<Record<string, string>>): RedisCatalogReader {
  const keys = Object.keys(records);
  return {
    scan: async () => [scanCompleteCursor, keys],
    mget: async (...requested: string[]) => requested.map((key) => records[key] ?? null)
  };
}

describe("The catalog is read out of Redis at startup, not only listened for", () => {
  it("loads a SKU that only exists in Redis, which is what the seeder produces", async () => {
    const store = new CatalogStore([]);
    const reader = buildReader({
      [`${meshCatalogKeyPrefix}${seededSkuId}`]: JSON.stringify(buildRecord(seededSkuId))
    });

    const loaded = await hydrateCatalogFromRedis(store, reader);

    assert.equal(loaded, 1);
    assert.equal(store.getRequiredSku(seededSkuId).skuId, seededSkuId);
  });

  it("keeps the compiled fixtures and adds Redis on top, rather than replacing them", async () => {
    // The restart case: fixtures are the floor, published SKUs are merged in.
    const fixtureSku = buildRecord("SKU-FIXTURE-001");
    const store = new CatalogStore([fixtureSku as never]);
    const reader = buildReader({
      [`${meshCatalogKeyPrefix}${seededSkuId}`]: JSON.stringify(buildRecord(seededSkuId))
    });

    await hydrateCatalogFromRedis(store, reader);

    const identifiers = store.getAllSkus().map((sku) => sku.skuId).sort();
    assert.deepEqual(identifiers, ["SKU-001", "SKU-FIXTURE-001"]);
  });

  it("accepts `title` where the schema says `name`, since the merchant API writes title", async () => {
    const store = new CatalogStore([]);
    const record = buildRecord(seededSkuId);
    delete record.name;
    record.title = "Cotton Oxford Shirt";
    const reader = buildReader({
      [`${meshCatalogKeyPrefix}${seededSkuId}`]: JSON.stringify(record)
    });

    await hydrateCatalogFromRedis(store, reader);

    assert.equal(store.getRequiredSku(seededSkuId).name, "Cotton Oxford Shirt");
  });

  it("skips a malformed record instead of refusing to serve the rest of the catalog", async () => {
    const store = new CatalogStore([]);
    const reader = buildReader({
      [`${meshCatalogKeyPrefix}BROKEN`]: "{ this is not json",
      [`${meshCatalogKeyPrefix}NO-NAME`]: JSON.stringify({ skuId: "NO-NAME" }),
      [`${meshCatalogKeyPrefix}${seededSkuId}`]: JSON.stringify(buildRecord(seededSkuId))
    });

    const loaded = await hydrateCatalogFromRedis(store, reader);

    assert.equal(loaded, 1, "the one valid record should still load");
    assert.equal(store.getSku("BROKEN"), undefined);
  });

  it("does not treat the updates channel as a catalog key", async () => {
    const store = new CatalogStore([]);
    const reader = buildReader({ [meshCatalogUpdatesChannel]: JSON.stringify(buildRecord("X")) });

    assert.equal(await hydrateCatalogFromRedis(store, reader), 0);
  });

  it("does nothing when Redis holds no catalog at all", async () => {
    const store = new CatalogStore([]);
    assert.equal(await hydrateCatalogFromRedis(store, buildReader({})), 0);
  });
});

describe("normalizeCatalogRecord", () => {
  it("rejects a non-object and an object with no usable name", () => {
    assert.equal(normalizeCatalogRecord(null), null);
    assert.equal(normalizeCatalogRecord("a string"), null);
    assert.equal(normalizeCatalogRecord({ skuId: "X" }), null);
    assert.equal(normalizeCatalogRecord({ skuId: "X", name: "" }), null);
  });
});
