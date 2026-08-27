import { describe, it } from "node:test";
import assert from "node:assert/strict";
import { computeAutoDiscountStack } from "../src/catalog/pricingEngine.js";

describe("PricingEngine — Auto Discount Stacking & Corporate Promos", () => {
  it("should compute auto discount stacking with volume, campaign, and UPI rails", () => {
    const tiers = [{ minQuantity: 5, discountBps: 1000 }];
    const stack = computeAutoDiscountStack(100000, 5, tiers);

    // 1. Volume 10%: 100000 -> 90000 (-10000)
    // 2. Festive Campaign 10% capped at 2000: 90000 -> 88000 (-2000)
    // 3. UPI Cashback flat 150: 88000 -> 87850 (-150)
    assert.equal(stack.offeredUnitPricePaise, 87850);
    assert.equal(stack.appliedDiscounts.length, 3);
    assert.equal(stack.totalSavingsPaise, 60750);
  });

  it("should stack corporate promo code CORP_5PCT when provided", () => {
    const tiers = [{ minQuantity: 5, discountBps: 1000 }];
    const stack = computeAutoDiscountStack(100000, 5, tiers, "CORP_5PCT");

    // 1-3. 87850
    // 4. CORP_5PCT 500 bps: floor(87850 * 500 / 10000) = 4392 -> 87850 - 4392 = 83458
    assert.equal(stack.offeredUnitPricePaise, 83458);
    assert.equal(stack.appliedDiscounts.length, 4);
    assert.equal(stack.totalSavingsPaise, 82710);
  });
});
