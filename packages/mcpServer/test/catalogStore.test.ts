import { describe, it } from "node:test";
import assert from "node:assert/strict";
import { defaultCatalogStore, CatalogStore } from "../src/catalog/catalogStore.js";
import { SkuNotFoundException } from "../src/types/mcpToolTypes.js";

describe("CatalogStore", () => {
  it("should initialize with at least 20 pre-seeded SKUs", () => {
    const allSkus = defaultCatalogStore.getAllSkus();
    assert.ok(allSkus.length >= 20);
  });

  it("should find SKU-CHAIR-001 with correct details and HSN code", () => {
    const chair = defaultCatalogStore.getRequiredSku("SKU-CHAIR-001");
    assert.equal(chair.skuId, "SKU-CHAIR-001");
    assert.equal(chair.hsnCode, "94013000");
    assert.equal(chair.gstRatePercent, 18);
    assert.equal(chair.baseUnitPricePaise, 420000);
    assert.equal(chair.availableStock, 50);
  });

  it("should find allergen-free substitute SKU-OIL-205 for OOS SKU-OIL-201", () => {
    const oosOil = defaultCatalogStore.getRequiredSku("SKU-OIL-201");
    const subOil = defaultCatalogStore.getRequiredSku("SKU-OIL-205");

    assert.equal(oosOil.availableStock, 0);
    assert.deepEqual(oosOil.allergens, ["peanut"]);

    assert.ok(subOil.availableStock > 0);
    assert.deepEqual(subOil.allergens, []);
  });

  it("should throw SkuNotFoundException for unknown SKU ID", () => {
    assert.throws(
      () => defaultCatalogStore.getRequiredSku("SKU-NON-EXISTENT"),
      (err: unknown) => err instanceof SkuNotFoundException
    );
  });

  it("should update stock and filter by category", () => {
    const testStore = new CatalogStore();
    const initialStock = testStore.getStock("SKU-CHAIR-001");
    testStore.updateStock("SKU-CHAIR-001", -5);
    assert.equal(testStore.getStock("SKU-CHAIR-001"), initialStock - 5);

    const furniture = testStore.filterSkus({ category: "Office Furniture" });
    assert.ok(furniture.length >= 2);
  });

  it("should add a new SKU to the store and retrieve it", () => {
    const testStore = new CatalogStore();
    const newSku = {
      skuId: "SKU-TEST-999",
      name: "Test Mechanical Keyboard",
      category: "Electronics",
      description: "Ergonomic tactile mechanical keyboard",
      hsnCode: "84716060",
      gstRatePercent: 18,
      baseUnitPricePaise: 850000,
      availableStock: 25,
      volumeTiers: [{ minQuantity: 5, discountBps: 500 }]
    };
    testStore.addSku(newSku);
    const retrieved = testStore.getSku("SKU-TEST-999");
    assert.ok(retrieved);
    assert.equal(retrieved.skuId, "SKU-TEST-999");
    assert.equal(retrieved.availableStock, 25);
  });

  it("should remove an existing SKU from the store", () => {
    const testStore = new CatalogStore();
    assert.ok(testStore.getSku("SKU-CHAIR-001"));
    const removed = testStore.removeSku("SKU-CHAIR-001");
    assert.equal(removed, true);
    assert.equal(testStore.getSku("SKU-CHAIR-001"), undefined);
  });

  it("should handle dynamic catalog sync channel updates", () => {
    const testStore = new CatalogStore();
    let messageListener: ((channel: string, message: string) => void) | undefined;
    const mockSubscriber = {
      subscribe: (_channel: string) => {},
      on: (event: string, listener: (...args: unknown[]) => void) => {
        if (event === "message") {
          messageListener = listener as (channel: string, message: string) => void;
        }
      }
    };

    testStore.subscribeToCatalogChannel(mockSubscriber);
    assert.ok(messageListener);

    // Add item via channel
    messageListener("mesh:catalog:updates", JSON.stringify({
      action: "CATALOG_ITEM_ADDED",
      item: {
        skuId: "SKU-SYNC-100",
        name: "Synced Monitor Stand",
        category: "Office Accessories",
        description: "Solid bamboo dual monitor stand",
        hsnCode: "94036000",
        gstRatePercent: 18,
        baseUnitPricePaise: 320000,
        availableStock: 40,
        volumeTiers: []
      }
    }));

    const syncedItem = testStore.getSku("SKU-SYNC-100");
    assert.ok(syncedItem);
    assert.equal(syncedItem.skuId, "SKU-SYNC-100");

    // Remove item via channel
    messageListener("mesh:catalog:updates", JSON.stringify({
      action: "CATALOG_ITEM_REMOVED",
      skuId: "SKU-SYNC-100"
    }));

    assert.equal(testStore.getSku("SKU-SYNC-100"), undefined);
  });
});
