import { describe, it } from "node:test";
import assert from "node:assert/strict";

import {
  assertIntegerPaise,
  calculateGstBreakdown,
  calculateVolumePricing,
  findMatchingVolumeTier
} from "../src/pricingEngine.js";
import { ArithmeticDriftException, VolumeTier } from "../src/mcpTypes.js";

describe("PricingEngine Adversarial Stress Suite", () => {
  it("should strictly reject any floating-point or non-integer input", () => {
    const maliciousInputs = [
      0.1,
      -0.1,
      1.5,
      1976.501,
      NaN,
      Infinity,
      -Infinity,
      "100",
      "100.5",
      true,
      false,
      null,
      undefined,
      {},
      [],
      1.0000000000000002
    ];

    for (const input of maliciousInputs) {
      assert.throws(
        () => assertIntegerPaise(input, "maliciousField"),
        ArithmeticDriftException,
        `Expected ${String(input)} to throw ArithmeticDriftException`
      );
    }
  });

  it("should reject negative prices and non-positive quantities in calculateVolumePricing", () => {
    assert.throws(
      () => calculateVolumePricing(-100, 5),
      ArithmeticDriftException
    );

    assert.throws(
      () => calculateVolumePricing(100, 0),
      ArithmeticDriftException
    );

    assert.throws(
      () => calculateVolumePricing(100, -10),
      ArithmeticDriftException
    );

    assert.throws(
      () => calculateVolumePricing(100.5 as any, 2),
      ArithmeticDriftException
    );

    assert.throws(
      () => calculateVolumePricing(100, 2.5 as any),
      ArithmeticDriftException
    );
  });

  it("should calculate exact volume pricing with multi-tier boundaries", () => {
    const tiers: readonly VolumeTier[] = [
      { minQuantity: 10, discountBps: 500 },  // 5% discount
      { minQuantity: 50, discountBps: 1000 }, // 10% discount
      { minQuantity: 100, discountBps: 1500 } // 15% discount
    ];

    // Below tier 1: qty = 9
    const res9 = calculateVolumePricing(100000, 9, tiers);
    assert.equal(res9.discountBps, 0);
    assert.equal(res9.offeredUnitPricePaise, 100000);
    assert.equal(res9.totalOfferedPaise, 900000);

    // Exact tier 1: qty = 10
    const res10 = calculateVolumePricing(100000, 10, tiers);
    assert.equal(res10.discountBps, 500);
    assert.equal(res10.unitDiscountPaise, 5000);
    assert.equal(res10.offeredUnitPricePaise, 95000);
    assert.equal(res10.totalOfferedPaise, 950000);

    // Exact tier 2: qty = 50
    const res50 = calculateVolumePricing(100000, 50, tiers);
    assert.equal(res50.discountBps, 1000);
    assert.equal(res50.unitDiscountPaise, 10000);
    assert.equal(res50.offeredUnitPricePaise, 90000);
    assert.equal(res50.totalOfferedPaise, 4500000);

    // Exact tier 3: qty = 100
    const res100 = calculateVolumePricing(100000, 100, tiers);
    assert.equal(res100.discountBps, 1500);
    assert.equal(res100.unitDiscountPaise, 15000);
    assert.equal(res100.offeredUnitPricePaise, 85000);
    assert.equal(res100.totalOfferedPaise, 8500000);
  });

  it("should calculate GST with 0% math drift on odd taxable amounts", () => {
    const oddAmounts = [1, 2, 3, 7, 13, 99, 101, 103, 333, 999, 1976501, 10000000007];
    const rates = [0, 5, 12, 18, 28];

    for (const amt of oddAmounts) {
      for (const rate of rates) {
        // Intra-state
        const intra = calculateGstBreakdown(amt, rate, "KA", "KA");
        assert.equal(intra.igstPaise, 0);
        assert.equal(intra.cgstPaise + intra.sgstPaise, intra.totalTaxPaise);

        // Inter-state
        const inter = calculateGstBreakdown(amt, rate, "KA", "MH");
        assert.equal(inter.cgstPaise, 0);
        assert.equal(inter.sgstPaise, 0);
        assert.equal(inter.igstPaise, inter.totalTaxPaise);
      }
    }
  });

  it("should reject negative taxable amount in calculateGstBreakdown", () => {
    assert.throws(
      () => calculateGstBreakdown(-500, 18, "KA", "KA"),
      ArithmeticDriftException
    );
  });
});