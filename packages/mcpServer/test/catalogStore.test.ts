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
});
