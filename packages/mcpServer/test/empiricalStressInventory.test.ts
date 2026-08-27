import { describe, it } from "node:test";
import assert from "node:assert/strict";

import {
  computeAutoDiscountStack,
  calculateVolumePricing
} from "../src/catalog/pricingEngine.js";
import { executeSkuQuote } from "../src/tools/skuQuoter.js";
import { CatalogStore } from "../src/catalog/catalogStore.js";
import { ArithmeticDriftException, CatalogSkuItem } from "../src/types/mcpToolTypes.js";

function buildDualPromoStore(currentUnix: number): CatalogStore {
  const store = new CatalogStore();
  store.addSku({
    skuId: "SKU-PROMO-DUAL",
    name: "Dual Promo Test Product",
    category: "Test",
    description: "Product with both active and upcoming promos",
    hsnCode: "94031000",
    gstRatePercent: 18,
    baseUnitPricePaise: 100000,
    availableStock: 50,
    volumeTiers: [],
    promotions: [
      { campaignId: "CAMP-ACTIVE-NOW", name: "Active 20% Sale", startsAtUnix: currentUnix - 3600, endsAtUnix: currentUnix + 3600, discountBps: 2000 },
      { campaignId: "CAMP-UPCOMING-NEXT", name: "Upcoming 50% Flash Deal", startsAtUnix: currentUnix + 7200, endsAtUnix: currentUnix + 14400, discountBps: 5000, limitedStockAllocated: 25 }
    ]
  });
  return store;
}

function buildExpiredPromoStore(currentUnix: number): CatalogStore {
  const store = new CatalogStore();
  store.addSku({
    skuId: "SKU-PROMO-EXPIRED",
    name: "Expired Promo Product",
    category: "Test",
    description: "Product with only expired promos",
    hsnCode: "94031000",
    gstRatePercent: 18,
    baseUnitPricePaise: 100000,
    availableStock: 50,
    volumeTiers: [],
    promotions: [
      { campaignId: "CAMP-EXPIRED", name: "Yesterday Sale", startsAtUnix: currentUnix - 7200, endsAtUnix: currentUnix - 3600, discountBps: 2000 }
    ]
  });
  return store;
}

describe("Adversarial Empirical Stress — Inventory & Promotion Invariants", () => {
  describe("Interaction of Q=1 with Upcoming vs Active Promotions in SkuQuoter", () => {
    it("Active promo vs Upcoming promo segregation in catalog items during live quote execution", () => {
      const currentUnix = Math.floor(Date.now() / 1000);
      const store = buildDualPromoStore(currentUnix);

      const quote = executeSkuQuote(
        { sku_id: "SKU-PROMO-DUAL", quantity: 1, buyer_agent_id: "did:agent:test-buyer-001", delivery_pincode: "560001" },
        store
      );

      assert.ok(quote.upcoming_promotions);
      assert.equal(quote.upcoming_promotions.length, 1);
      assert.equal(quote.upcoming_promotions[0].campaign_id, "CAMP-UPCOMING-NEXT");
      assert.equal(quote.upcoming_promotions[0].expected_unit_price_paise, 50000);
      assert.equal(quote.upcoming_promotions[0].expected_savings_paise, 50000);
      assert.equal(quote.upcoming_promotions[0].limited_stock_allocated, 25);
    });

    it("Expired promo is omitted completely from upcoming_promotions", () => {
      const currentUnix = Math.floor(Date.now() / 1000);
      const store = buildExpiredPromoStore(currentUnix);

      const quote = executeSkuQuote(
        { sku_id: "SKU-PROMO-EXPIRED", quantity: 1, buyer_agent_id: "did:agent:test-buyer-001", delivery_pincode: "560001" },
        store
      );

      assert.equal(quote.upcoming_promotions, undefined);
    });
  });

  describe("Boundary Conditions and Adversarial Invariants", () => {
    it("Zero quantity (quantity = 0) is rejected strictly", () => {
      assert.throws(() => computeAutoDiscountStack(420000, 0, []), (err: unknown) => err instanceof ArithmeticDriftException && err.message.includes("Invalid base price"));
      assert.throws(() => calculateVolumePricing(420000, 0, []), (err: unknown) => err instanceof ArithmeticDriftException && err.message.includes("Invalid base price"));
      assert.throws(() => executeSkuQuote({ sku_id: "SKU-CHAIR-001", quantity: 0, buyer_agent_id: "did:agent:buyer-01", delivery_pincode: "560001" }), (err: unknown) => err instanceof Error);
    });

    it("Negative quantity (quantity < 0) is rejected strictly", () => {
      assert.throws(() => computeAutoDiscountStack(420000, -5, []), (err: unknown) => err instanceof ArithmeticDriftException);
      assert.throws(() => calculateVolumePricing(420000, -1, []), (err: unknown) => err instanceof ArithmeticDriftException);
    });

    it("Zero base price (baseUnitPricePaise = 0) produces 0 offered price and 0 savings without error", () => {
      const stack = computeAutoDiscountStack(0, 1, []);
      assert.equal(stack.offeredUnitPricePaise, 0);
      assert.equal(stack.totalSavingsPaise, 0);
      assert.equal(stack.appliedDiscounts.length, 0);

      const vol = calculateVolumePricing(0, 1, []);
      assert.equal(vol.offeredUnitPricePaise, 0);
      assert.equal(vol.totalOfferedPaise, 0);
    });

    it("Negative base price (baseUnitPricePaise < 0) is rejected strictly", () => {
      assert.throws(() => computeAutoDiscountStack(-100, 1, []), (err: unknown) => err instanceof ArithmeticDriftException);
      assert.throws(() => calculateVolumePricing(-500, 1, []), (err: unknown) => err instanceof ArithmeticDriftException);
    });

    it("Floating point inputs are strictly rejected (TC-08 zero drift rule)", () => {
      assert.throws(() => computeAutoDiscountStack(4200.5, 1, []), (err: unknown) => err instanceof ArithmeticDriftException && err.message.includes("Float math drift"));
      assert.throws(() => computeAutoDiscountStack(420000, 1.5, []), (err: unknown) => err instanceof ArithmeticDriftException && err.message.includes("Float math drift"));
    });

    it("Floor division truncation invariant: penny conservation across all integers", () => {
      for (let price = 1; price <= 500; price++) {
        const stack = computeAutoDiscountStack(price, 1, [], "CORP_5PCT");
        assert.ok(Number.isInteger(stack.offeredUnitPricePaise));
        assert.ok(Number.isInteger(stack.totalSavingsPaise));
        assert.ok(stack.offeredUnitPricePaise >= 0);
        assert.ok(stack.totalSavingsPaise >= 0);
        assert.equal(stack.offeredUnitPricePaise + stack.totalSavingsPaise, price);
      }
    });

    it("Extreme stacked discounts cannot produce negative price", () => {
      const aggressiveTiers = [{ minQuantity: 1, discountBps: 9000 }];
      const stack = computeAutoDiscountStack(100, 1, aggressiveTiers, "CORP_5PCT");
      assert.equal(stack.offeredUnitPricePaise, 0);
      assert.equal(stack.totalSavingsPaise, 100);
      assert.ok(stack.offeredUnitPricePaise >= 0);
    });
  });
});
