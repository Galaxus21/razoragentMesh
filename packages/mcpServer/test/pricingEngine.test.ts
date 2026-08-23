import { describe, it } from "node:test";
import assert from "node:assert/strict";
import {
  calculateVolumePricing,
  calculateGstBreakdown,
  computeAutoDiscountStack
} from "../src/catalog/pricingEngine.js";
import { ArithmeticDriftException } from "../src/types/mcpToolTypes.js";

describe("PricingEngine", () => {
  it("should calculate volume pricing with no tiers as full price", () => {
    const result = calculateVolumePricing(420000, 2, []);
    assert.equal(result.baseUnitPricePaise, 420000);
    assert.equal(result.offeredUnitPricePaise, 420000);
    assert.equal(result.discountBps, 0);
    assert.equal(result.unitDiscountPaise, 0);
    assert.equal(result.totalBasePaise, 840000);
    assert.equal(result.totalOfferedPaise, 840000);
  });

  it("should apply correct volume discount tier when quantity threshold is met", () => {
    const tiers = [
      { minQuantity: 5, discountBps: 300 },
      { minQuantity: 10, discountBps: 500 },
      { minQuantity: 50, discountBps: 1000 }
    ];

    // Quantity 12 matches tier 10 (500 bps = 5%)
    const result = calculateVolumePricing(420000, 12, tiers);
    assert.equal(result.discountBps, 500);
    assert.equal(result.unitDiscountPaise, 21000); // 420000 * 0.05
    assert.equal(result.offeredUnitPricePaise, 399000);
    assert.equal(result.totalOfferedPaise, 4788000);
  });

  it("should reject float prices with ArithmeticDriftException (TC-08)", () => {
    assert.throws(
      () => calculateVolumePricing(4200.5, 10),
      (err: unknown) => err instanceof ArithmeticDriftException
    );
  });

  it("should reject float quantities with ArithmeticDriftException", () => {
    assert.throws(
      () => calculateVolumePricing(420000, 2.5),
      (err: unknown) => err instanceof ArithmeticDriftException
    );
  });

  it("should calculate intra-state GST with 50/50 CGST and SGST split", () => {
    const tax = calculateGstBreakdown(100000, 18, "KA", "KA");
    assert.equal(tax.cgstPaise, 9000);
    assert.equal(tax.sgstPaise, 9000);
    assert.equal(tax.igstPaise, 0);
    assert.equal(tax.totalTaxPaise, 18000);
  });

  it("should calculate inter-state GST with 100% IGST and 0 CGST/SGST", () => {
    const tax = calculateGstBreakdown(100000, 18, "KA", "DL");
    assert.equal(tax.cgstPaise, 0);
    assert.equal(tax.sgstPaise, 0);
    assert.equal(tax.igstPaise, 18000);
    assert.equal(tax.totalTaxPaise, 18000);
  });

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
