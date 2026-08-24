import { describe, it } from "node:test";
import assert from "node:assert/strict";

import {
  evaluateScheduledPromotions,
  evaluateSingleScheduledPromotion,
  assertIntegerPaise
} from "../src/catalog/pricingEngine.js";
import { executeSkuQuote } from "../src/tools/skuQuoter.js";
import { CatalogStore } from "../src/catalog/catalogStore.js";
import {
  ScheduledPromotion,
  UpcomingPromotion,
  CatalogSkuItem,
  ArithmeticDriftException
} from "../src/types/mcpToolTypes.js";

const zeroPaise = 0;
const zeroBps = 0;
const fullDiscountBps = 10000;
const mockBasePricePaise = 420000;
const testStartsAtUnix = 1724485000;
const testEndsAtUnix = 1724490000;
const validBuyerAgentId = "did:agent:test-buyer-001";
const validPincode = "560001";

const largePrimes = [
  2, 3, 5, 7, 11, 13, 17, 19, 23, 29, 31, 37, 41, 43, 47, 53, 59, 61, 67, 71,
  73, 79, 83, 89, 97, 101, 103, 107, 109, 113, 127, 131, 137, 139, 149, 151,
  157, 163, 167, 173, 179, 181, 191, 193, 197, 199, 997, 1009, 7919, 104729,
  1000003, 1000000007, 2147483647, 9999999967
];

const sampleBpsValues = [
  0, 1, 2, 5, 10, 33, 50, 100, 250, 333, 500, 777, 1000, 1234, 1428, 2000,
  2500, 3000, 3333, 4000, 5000, 6000, 6666, 7500, 8000, 9000, 9999, 10000
];

function buildScheduledPromo(
  campaignId: string,
  startsAtUnix: number,
  endsAtUnix: number,
  options: Partial<ScheduledPromotion> = {}
): ScheduledPromotion {
  return {
    campaignId,
    name: `Promo-${campaignId}`,
    startsAtUnix,
    endsAtUnix,
    ...options
  };
}

describe("PricingEngine Adversarial Challenger Stress Suite", () => {
  describe("1. Boundary Condition Stress Testing", () => {
    const boundaryPromo = buildScheduledPromo(
      "CAMP-BOUNDARY-01",
      testStartsAtUnix,
      testEndsAtUnix,
      { discountBps: 2000 }
    );

    it("should classify promotion as active at exact startsAtUnix", () => {
      const result = evaluateScheduledPromotions(
        mockBasePricePaise,
        [boundaryPromo],
        testStartsAtUnix
      );
      assert.equal(result.activePromotions.length, 1);
      assert.equal(result.upcomingPromotions.length, 0);
      assert.equal(result.activePromotions[0].campaign_id, "CAMP-BOUNDARY-01");
    });

    it("should classify promotion as upcoming at exact startsAtUnix - 1", () => {
      const result = evaluateScheduledPromotions(
        mockBasePricePaise,
        [boundaryPromo],
        testStartsAtUnix - 1
      );
      assert.equal(result.activePromotions.length, 0);
      assert.equal(result.upcomingPromotions.length, 1);
      assert.equal(result.upcomingPromotions[0].campaign_id, "CAMP-BOUNDARY-01");
    });

    it("should classify promotion as active at exact endsAtUnix - 1", () => {
      const result = evaluateScheduledPromotions(
        mockBasePricePaise,
        [boundaryPromo],
        testEndsAtUnix - 1
      );
      assert.equal(result.activePromotions.length, 1);
      assert.equal(result.upcomingPromotions.length, 0);
      assert.equal(result.activePromotions[0].campaign_id, "CAMP-BOUNDARY-01");
    });

    it("should omit promotion (expired) at exact endsAtUnix", () => {
      const result = evaluateScheduledPromotions(
        mockBasePricePaise,
        [boundaryPromo],
        testEndsAtUnix
      );
      assert.equal(result.activePromotions.length, 0);
      assert.equal(result.upcomingPromotions.length, 0);
    });

    it("should omit promotion (expired) at endsAtUnix + 1", () => {
      const result = evaluateScheduledPromotions(
        mockBasePricePaise,
        [boundaryPromo],
        testEndsAtUnix + 1
      );
      assert.equal(result.activePromotions.length, 0);
      assert.equal(result.upcomingPromotions.length, 0);
    });

    it("should correctly partition multiple simultaneous promotions across past, active, upcoming, and future windows", () => {
      const currentTime = 1724486000;
      const promos: ScheduledPromotion[] = [
        buildScheduledPromo("CAMP-PAST-01", 1724470000, 1724480000, { discountBps: 500 }),
        buildScheduledPromo("CAMP-PAST-02", 1724480000, currentTime, { discountBps: 600 }),
        buildScheduledPromo("CAMP-ACTIVE-01", currentTime, 1724490000, { discountBps: 1000 }),
        buildScheduledPromo("CAMP-ACTIVE-02", 1724485000, 1724495000, { discountBps: 1500 }),
        buildScheduledPromo("CAMP-ACTIVE-03", 1724480000, currentTime + 1, { discountBps: 2000 }),
        buildScheduledPromo("CAMP-UPCOMING-01", currentTime + 1, 1724500000, { discountBps: 2500 }),
        buildScheduledPromo("CAMP-UPCOMING-02", 1724490000, 1724500000, { discountBps: 3000 })
      ];

      const result = evaluateScheduledPromotions(mockBasePricePaise, promos, currentTime);

      assert.equal(result.activePromotions.length, 3);
      const activeIds = result.activePromotions.map((p) => p.campaign_id);
      assert.deepEqual(activeIds, ["CAMP-ACTIVE-01", "CAMP-ACTIVE-02", "CAMP-ACTIVE-03"]);

      assert.equal(result.upcomingPromotions.length, 2);
      const upcomingIds = result.upcomingPromotions.map((p) => p.campaign_id);
      assert.deepEqual(upcomingIds, ["CAMP-UPCOMING-01", "CAMP-UPCOMING-02"]);
    });
  });

  describe("2. Arithmetic Stress Testing & Zero-Drift Invariants", () => {
    it("should handle extreme BPS discounts (0 bps and 10000 bps) strictly", () => {
      const zeroBpsPromo = buildScheduledPromo("CAMP-0BPS", testStartsAtUnix, testEndsAtUnix, {
        discountBps: zeroBps
      });
      const resZero = evaluateSingleScheduledPromotion(mockBasePricePaise, zeroBpsPromo);
      assert.equal(resZero.expected_unit_price_paise, mockBasePricePaise);
      assert.equal(resZero.expected_savings_paise, zeroPaise);
      assert.equal(
        resZero.expected_unit_price_paise + resZero.expected_savings_paise,
        mockBasePricePaise
      );

      const maxBpsPromo = buildScheduledPromo("CAMP-MAXBPS", testStartsAtUnix, testEndsAtUnix, {
        discountBps: fullDiscountBps
      });
      const resMax = evaluateSingleScheduledPromotion(mockBasePricePaise, maxBpsPromo);
      assert.equal(resMax.expected_unit_price_paise, zeroPaise);
      assert.equal(resMax.expected_savings_paise, mockBasePricePaise);
      assert.equal(
        resMax.expected_unit_price_paise + resMax.expected_savings_paise,
        mockBasePricePaise
      );
    });

    it("should satisfy penny conservation and zero float drift across large prime base prices and varied BPS", () => {
      for (const primeBase of largePrimes) {
        for (const bps of sampleBpsValues) {
          const promo = buildScheduledPromo("CAMP-PRIME", testStartsAtUnix, testEndsAtUnix, {
            discountBps: bps
          });
          const evalResult = evaluateSingleScheduledPromotion(primeBase, promo);

          assert.ok(
            Number.isInteger(evalResult.expected_unit_price_paise),
            `Float detected in expected_unit_price_paise: ${evalResult.expected_unit_price_paise}`
          );
          assert.ok(
            Number.isInteger(evalResult.expected_savings_paise),
            `Float detected in expected_savings_paise: ${evalResult.expected_savings_paise}`
          );
          assert.ok(
            evalResult.expected_unit_price_paise >= zeroPaise,
            `Negative unit price: ${evalResult.expected_unit_price_paise}`
          );
          assert.ok(
            evalResult.expected_savings_paise >= zeroPaise,
            `Negative savings: ${evalResult.expected_savings_paise}`
          );

          const expectedPrice = Math.floor((primeBase * (10000 - bps)) / 10000);
          assert.equal(evalResult.expected_unit_price_paise, expectedPrice);
          assert.equal(
            evalResult.expected_unit_price_paise + evalResult.expected_savings_paise,
            primeBase,
            `Sum of price and savings does not equal base price for prime ${primeBase} with BPS ${bps}`
          );
        }
      }
    });

    it("should handle discountPaise edge values (0, exact base, and excessive discount)", () => {
      const zeroDiscountPromo = buildScheduledPromo("CAMP-DPAISE-0", testStartsAtUnix, testEndsAtUnix, {
        discountPaise: zeroPaise
      });
      const res0 = evaluateSingleScheduledPromotion(mockBasePricePaise, zeroDiscountPromo);
      assert.equal(res0.expected_unit_price_paise, mockBasePricePaise);
      assert.equal(res0.expected_savings_paise, zeroPaise);

      const exactBasePromo = buildScheduledPromo("CAMP-DPAISE-EXACT", testStartsAtUnix, testEndsAtUnix, {
        discountPaise: mockBasePricePaise
      });
      const resExact = evaluateSingleScheduledPromotion(mockBasePricePaise, exactBasePromo);
      assert.equal(resExact.expected_unit_price_paise, zeroPaise);
      assert.equal(resExact.expected_savings_paise, mockBasePricePaise);

      const excessPromo = buildScheduledPromo("CAMP-DPAISE-EXCESS", testStartsAtUnix, testEndsAtUnix, {
        discountPaise: mockBasePricePaise + 999999
      });
      const resExcess = evaluateSingleScheduledPromotion(mockBasePricePaise, excessPromo);
      assert.equal(resExcess.expected_unit_price_paise, zeroPaise);
      assert.equal(resExcess.expected_savings_paise, mockBasePricePaise);
    });

    it("should handle fixedPricePaise edge values (0, 1, exact base)", () => {
      const freePromo = buildScheduledPromo("CAMP-FIXED-0", testStartsAtUnix, testEndsAtUnix, {
        fixedPricePaise: zeroPaise
      });
      const resFree = evaluateSingleScheduledPromotion(mockBasePricePaise, freePromo);
      assert.equal(resFree.expected_unit_price_paise, zeroPaise);
      assert.equal(resFree.expected_savings_paise, mockBasePricePaise);

      const onePaisePromo = buildScheduledPromo("CAMP-FIXED-1", testStartsAtUnix, testEndsAtUnix, {
        fixedPricePaise: 1
      });
      const res1 = evaluateSingleScheduledPromotion(mockBasePricePaise, onePaisePromo);
      assert.equal(res1.expected_unit_price_paise, 1);
      assert.equal(res1.expected_savings_paise, mockBasePricePaise - 1);

      const fullPricePromo = buildScheduledPromo("CAMP-FIXED-FULL", testStartsAtUnix, testEndsAtUnix, {
        fixedPricePaise: mockBasePricePaise
      });
      const resFull = evaluateSingleScheduledPromotion(mockBasePricePaise, fullPricePromo);
      assert.equal(resFull.expected_unit_price_paise, mockBasePricePaise);
      assert.equal(resFull.expected_savings_paise, zeroPaise);
    });
  });

  describe("3. Adversarial Negative Cases & Exception Handling", () => {
    it("should reject temporal windows where endsAtUnix <= startsAtUnix", () => {
      const equalTimesPromo = buildScheduledPromo("CAMP-EQUAL", testStartsAtUnix, testStartsAtUnix, {
        discountBps: 1000
      });
      assert.throws(
        () => evaluateSingleScheduledPromotion(mockBasePricePaise, equalTimesPromo),
        (err: unknown) => err instanceof ArithmeticDriftException && err.message.includes("Invalid temporal window")
      );

      const invertedTimesPromo = buildScheduledPromo("CAMP-INVERTED", testEndsAtUnix, testStartsAtUnix, {
        discountBps: 1000
      });
      assert.throws(
        () => evaluateSingleScheduledPromotion(mockBasePricePaise, invertedTimesPromo),
        (err: unknown) => err instanceof ArithmeticDriftException && err.message.includes("Invalid temporal window")
      );
    });

    it("should reject fixedPricePaise strictly greater than baseUnitPricePaise", () => {
      const priceHikePromo = buildScheduledPromo("CAMP-HIKE", testStartsAtUnix, testEndsAtUnix, {
        fixedPricePaise: mockBasePricePaise + 1
      });
      assert.throws(
        () => evaluateSingleScheduledPromotion(mockBasePricePaise, priceHikePromo),
        (err: unknown) =>
          err instanceof ArithmeticDriftException &&
          err.message.includes("Negative promotion savings detected")
      );
    });

    it("should reject non-integer / floating-point inputs in pricing engine", () => {
      const floatBasePrices = [4200.5, 4200.0001, NaN, Infinity, -Infinity, 1.0000000000000002];
      const validPromo = buildScheduledPromo("CAMP-VALID", testStartsAtUnix, testEndsAtUnix, {
        discountBps: 1000
      });

      for (const floatBase of floatBasePrices) {
        assert.throws(
          () => evaluateScheduledPromotions(floatBase, [validPromo], testStartsAtUnix - 10),
          (err: unknown) => err instanceof ArithmeticDriftException && err.message.includes("Float math drift")
        );
      }

      const floatCurrentTimes = [1724485000.5, NaN, Infinity, -Infinity];
      for (const floatTime of floatCurrentTimes) {
        assert.throws(
          () => evaluateScheduledPromotions(mockBasePricePaise, [validPromo], floatTime),
          (err: unknown) => err instanceof ArithmeticDriftException && err.message.includes("Float math drift")
        );
      }

      const floatFixedPricePromo = buildScheduledPromo("CAMP-FLOAT-FIXED", testStartsAtUnix, testEndsAtUnix, {
        fixedPricePaise: 3500.75
      });
      assert.throws(
        () => evaluateSingleScheduledPromotion(mockBasePricePaise, floatFixedPricePromo),
        (err: unknown) => err instanceof ArithmeticDriftException && err.message.includes("Float math drift")
      );
    });
  });

  describe("4. Backward Compatibility & End-to-End Tool Execution", () => {
    it("should omit upcoming_promotions when SKU has no promotions configured", () => {
      const skuWithoutPromos: CatalogSkuItem = {
        skuId: "SKU-TEST-NOPROMO",
        name: "Test Desk without Promos",
        category: "furniture",
        description: "Standard desk with no promotional campaigns",
        hsnCode: "94033000",
        gstRatePercent: 18,
        baseUnitPricePaise: 500000,
        availableStock: 50,
        volumeTiers: []
      };

      const customStore = new CatalogStore([skuWithoutPromos]);
      const quote = executeSkuQuote(
        {
          sku_id: "SKU-TEST-NOPROMO",
          quantity: 1,
          buyer_agent_id: validBuyerAgentId,
          delivery_pincode: validPincode
        },
        customStore
      );

      assert.equal(quote.sku_id, "SKU-TEST-NOPROMO");
      assert.equal(quote.offered_unit_price_paise, 500000);
      assert.equal(quote.upcoming_promotions, undefined);
      assert.equal("upcoming_promotions" in quote, false);
    });

    it("should omit upcoming_promotions when SKU has empty promotions array", () => {
      const skuWithEmptyPromos: CatalogSkuItem = {
        skuId: "SKU-TEST-EMPTYPROMO",
        name: "Test Desk with Empty Promos",
        category: "furniture",
        description: "Desk with empty promotional list",
        hsnCode: "94033000",
        gstRatePercent: 18,
        baseUnitPricePaise: 500000,
        availableStock: 50,
        volumeTiers: [],
        promotions: []
      };

      const customStore = new CatalogStore([skuWithEmptyPromos]);
      const quote = executeSkuQuote(
        {
          sku_id: "SKU-TEST-EMPTYPROMO",
          quantity: 1,
          buyer_agent_id: validBuyerAgentId,
          delivery_pincode: validPincode
        },
        customStore
      );

      assert.equal(quote.sku_id, "SKU-TEST-EMPTYPROMO");
      assert.equal(quote.upcoming_promotions, undefined);
      assert.equal("upcoming_promotions" in quote, false);
    });

    it("should attach upcoming_promotions in quote when SKU has valid upcoming promotions", () => {
      const futurePromo = buildScheduledPromo("CAMP-FUTURE-40", 2500000000, 2600000000, {
        discountBps: 4000,
        limitedStockAllocated: 15
      });
      const skuWithPromo: CatalogSkuItem = {
        skuId: "SKU-TEST-PROMO",
        name: "Test Desk with Future Promo",
        category: "furniture",
        description: "Desk with upcoming promo campaign",
        hsnCode: "94033000",
        gstRatePercent: 18,
        baseUnitPricePaise: 500000,
        availableStock: 50,
        volumeTiers: [],
        promotions: [futurePromo]
      };

      const customStore = new CatalogStore([skuWithPromo]);
      const quote = executeSkuQuote(
        {
          sku_id: "SKU-TEST-PROMO",
          quantity: 1,
          buyer_agent_id: validBuyerAgentId,
          delivery_pincode: validPincode
        },
        customStore
      );

      assert.ok(quote.upcoming_promotions);
      assert.equal(quote.upcoming_promotions.length, 1);
      assert.equal(quote.upcoming_promotions[0].campaign_id, "CAMP-FUTURE-40");
      assert.equal(quote.upcoming_promotions[0].expected_unit_price_paise, 300000);
      assert.equal(quote.upcoming_promotions[0].expected_savings_paise, 200000);
      assert.equal(quote.upcoming_promotions[0].limited_stock_allocated, 15);
    });
  });
});
