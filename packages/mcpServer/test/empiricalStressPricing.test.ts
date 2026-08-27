import { describe, it } from "node:test";
import assert from "node:assert/strict";

import { computeAutoDiscountStack } from "../src/catalog/pricingEngine.js";

describe("Adversarial Empirical Stress — Auto-Stacking & Promo Pricing", () => {
  describe("Single-Unit (Q=1) Auto-Stacking Across Base Price Ranges", () => {
    it("Micro-price INR 0.05 (5 paise): UPI cashback clamped to 5 paise, offered price = 0 paise", () => {
      const stack = computeAutoDiscountStack(5, 1, []);
      assert.equal(stack.offeredUnitPricePaise, 0);
      assert.equal(stack.totalSavingsPaise, 5);
      assert.equal(stack.appliedDiscounts.length, 1);
      assert.equal(stack.appliedDiscounts[0].type, "PAYMENT_RAIL");
      assert.equal(stack.appliedDiscounts[0].discountPaise, 5);
      assert.ok(stack.offeredUnitPricePaise >= 0, "Offered price must not be negative");
    });

    it("Micro-price INR 0.01 (1 paise): UPI cashback clamped to 1 paise, offered price = 0 paise", () => {
      const stack = computeAutoDiscountStack(1, 1, []);
      assert.equal(stack.offeredUnitPricePaise, 0);
      assert.equal(stack.totalSavingsPaise, 1);
      assert.equal(stack.appliedDiscounts.length, 1);
      assert.equal(stack.appliedDiscounts[0].discountPaise, 1);
    });

    it("Micro-price INR 1.00 (100 paise): Festive (10p) + UPI (90p clamped) -> offered price = 0 paise", () => {
      const stack = computeAutoDiscountStack(100, 1, []);
      assert.equal(stack.offeredUnitPricePaise, 0);
      assert.equal(stack.totalSavingsPaise, 100);
      assert.equal(stack.appliedDiscounts.length, 2);
      assert.equal(stack.appliedDiscounts[0].type, "CAMPAIGN");
      assert.equal(stack.appliedDiscounts[0].discountPaise, 10);
      assert.equal(stack.appliedDiscounts[1].type, "PAYMENT_RAIL");
      assert.equal(stack.appliedDiscounts[1].discountPaise, 90);
    });

    it("Micro-price INR 1.50 (150 paise): Festive (15p) + UPI (135p) -> offered price = 0 paise", () => {
      const stack = computeAutoDiscountStack(150, 1, []);
      assert.equal(stack.offeredUnitPricePaise, 0);
      assert.equal(stack.totalSavingsPaise, 150);
      assert.equal(stack.appliedDiscounts.length, 2);
    });

    it("Micro-price INR 2.00 (200 paise): Festive (20p) + UPI (150p) -> offered price = 30 paise", () => {
      const stack = computeAutoDiscountStack(200, 1, []);
      assert.equal(stack.offeredUnitPricePaise, 30);
      assert.equal(stack.totalSavingsPaise, 170);
      assert.equal(stack.appliedDiscounts.length, 2);
    });

    it("Standard price INR 4,200.00 (420,000 paise): Festive (capped 2000p) + UPI (150p) -> offered price = 417,850 paise", () => {
      const stack = computeAutoDiscountStack(420000, 1, []);
      assert.equal(stack.offeredUnitPricePaise, 417850);
      assert.equal(stack.totalSavingsPaise, 2150);
      assert.equal(stack.appliedDiscounts.length, 2);
      assert.equal(stack.appliedDiscounts[0].discountPaise, 2000);
      assert.equal(stack.appliedDiscounts[1].discountPaise, 150);
    });

    it("Large price INR 50,000.00 (5,000,000 paise): Festive (capped 2000p) + UPI (150p) -> offered price = 4,997,850 paise", () => {
      const stack = computeAutoDiscountStack(5000000, 1, []);
      assert.equal(stack.offeredUnitPricePaise, 4997850);
      assert.equal(stack.totalSavingsPaise, 2150);
      assert.equal(stack.appliedDiscounts.length, 2);
    });

    it("Ultra large price INR 1,000,000.00 (100,000,000 paise): Strict integer arithmetic without drift", () => {
      const stack = computeAutoDiscountStack(100000000, 1, []);
      assert.equal(stack.offeredUnitPricePaise, 99997850);
      assert.equal(stack.totalSavingsPaise, 2150);
      assert.ok(Number.isInteger(stack.offeredUnitPricePaise));
      assert.ok(Number.isInteger(stack.totalSavingsPaise));
    });
  });

  describe("Single-Unit (Q=1) Interaction with Promo Codes", () => {
    it("Stacking CORP_5PCT with Q=1 on standard price INR 4,200", () => {
      const stack = computeAutoDiscountStack(420000, 1, [], "CORP_5PCT");
      assert.equal(stack.offeredUnitPricePaise, 396958);
      assert.equal(stack.totalSavingsPaise, 23042);
      assert.equal(stack.appliedDiscounts.length, 3);
      assert.equal(stack.appliedDiscounts[2].type, "PROMO_CODE");
      assert.equal(stack.appliedDiscounts[2].discountBps, 500);
      assert.equal(stack.appliedDiscounts[2].discountPaise, 20892);
    });

    it("Case insensitive and trimmed promo code handling (e.g. ' corp_5pct ')", () => {
      const stack = computeAutoDiscountStack(420000, 1, [], "  corp_5pct  ");
      assert.equal(stack.offeredUnitPricePaise, 396958);
      assert.equal(stack.appliedDiscounts.length, 3);
    });

    it("Invalid promo codes are ignored gracefully", () => {
      const invalidCodes = ["INVALID_PROMO", "CORP_10PCT", "DISCOUNT50", "random_string", ""];
      for (const code of invalidCodes) {
        const stack = computeAutoDiscountStack(420000, 1, [], code);
        assert.equal(stack.offeredUnitPricePaise, 417850, `Failed for code ${code}`);
        assert.equal(stack.appliedDiscounts.length, 2);
        assert.equal(stack.totalSavingsPaise, 2150);
      }
    });

    it("CORP_5PCT on micro price INR 0.05: price remains 0 paise, no negative promo discount", () => {
      const stack = computeAutoDiscountStack(5, 1, [], "CORP_5PCT");
      assert.equal(stack.offeredUnitPricePaise, 0);
      assert.equal(stack.totalSavingsPaise, 5);
      assert.equal(stack.appliedDiscounts.length, 1);
    });
  });
});
