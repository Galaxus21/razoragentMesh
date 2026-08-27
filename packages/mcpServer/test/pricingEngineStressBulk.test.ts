import { describe, it } from "node:test";
import assert from "node:assert/strict";

import {
  evaluateScheduledPromotions,
  evaluateSingleScheduledPromotion
} from "../src/catalog/pricingEngine.js";
import { ScheduledPromotion } from "../src/types/mcpToolTypes.js";

const zeroPaise = 0;
const zeroBps = 0;
const fullDiscountBps = 10000;
const mockBasePricePaise = 420000;
const testStartsAtUnix = 1724485000;
const testEndsAtUnix = 1724490000;

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

describe("PricingEngine Stress — Bulk Arithmetic & Boundary Suites", () => {
  describe("Boundary Condition Stress Testing", () => {
    const boundaryPromo = buildScheduledPromo(
      "CAMP-BOUNDARY-01",
      testStartsAtUnix,
      testEndsAtUnix,
      { discountBps: 2000 }
    );

    it("should classify promotion as active at exact startsAtUnix", () => {
      const result = evaluateScheduledPromotions(mockBasePricePaise, [boundaryPromo], testStartsAtUnix);
      assert.equal(result.activePromotions.length, 1);
      assert.equal(result.upcomingPromotions.length, 0);
      assert.equal(result.activePromotions[0].campaign_id, "CAMP-BOUNDARY-01");
    });

    it("should classify promotion as upcoming at exact startsAtUnix - 1", () => {
      const result = evaluateScheduledPromotions(mockBasePricePaise, [boundaryPromo], testStartsAtUnix - 1);
      assert.equal(result.activePromotions.length, 0);
      assert.equal(result.upcomingPromotions.length, 1);
      assert.equal(result.upcomingPromotions[0].campaign_id, "CAMP-BOUNDARY-01");
    });

    it("should classify promotion as active at exact endsAtUnix - 1", () => {
      const result = evaluateScheduledPromotions(mockBasePricePaise, [boundaryPromo], testEndsAtUnix - 1);
      assert.equal(result.activePromotions.length, 1);
      assert.equal(result.upcomingPromotions.length, 0);
      assert.equal(result.activePromotions[0].campaign_id, "CAMP-BOUNDARY-01");
    });

    it("should omit promotion (expired) at exact endsAtUnix", () => {
      const result = evaluateScheduledPromotions(mockBasePricePaise, [boundaryPromo], testEndsAtUnix);
      assert.equal(result.activePromotions.length, 0);
      assert.equal(result.upcomingPromotions.length, 0);
    });

    it("should omit promotion (expired) at endsAtUnix + 1", () => {
      const result = evaluateScheduledPromotions(mockBasePricePaise, [boundaryPromo], testEndsAtUnix + 1);
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
      assert.deepEqual(result.activePromotions.map((p) => p.campaign_id), ["CAMP-ACTIVE-01", "CAMP-ACTIVE-02", "CAMP-ACTIVE-03"]);
      assert.equal(result.upcomingPromotions.length, 2);
      assert.deepEqual(result.upcomingPromotions.map((p) => p.campaign_id), ["CAMP-UPCOMING-01", "CAMP-UPCOMING-02"]);
    });
  });

  describe("Arithmetic Stress Testing & Zero-Drift Invariants", () => {
    it("should handle extreme BPS discounts (0 bps and 10000 bps) strictly", () => {
      const zeroBpsPromo = buildScheduledPromo("CAMP-0BPS", testStartsAtUnix, testEndsAtUnix, { discountBps: zeroBps });
      const resZero = evaluateSingleScheduledPromotion(mockBasePricePaise, zeroBpsPromo);
      assert.equal(resZero.expected_unit_price_paise, mockBasePricePaise);
      assert.equal(resZero.expected_savings_paise, zeroPaise);
      assert.equal(resZero.expected_unit_price_paise + resZero.expected_savings_paise, mockBasePricePaise);

      const maxBpsPromo = buildScheduledPromo("CAMP-MAXBPS", testStartsAtUnix, testEndsAtUnix, { discountBps: fullDiscountBps });
      const resMax = evaluateSingleScheduledPromotion(mockBasePricePaise, maxBpsPromo);
      assert.equal(resMax.expected_unit_price_paise, zeroPaise);
      assert.equal(resMax.expected_savings_paise, mockBasePricePaise);
      assert.equal(resMax.expected_unit_price_paise + resMax.expected_savings_paise, mockBasePricePaise);
    });

    it("should satisfy penny conservation and zero float drift across large prime base prices and varied BPS", () => {
      for (const primeBase of largePrimes) {
        for (const bps of sampleBpsValues) {
          const promo = buildScheduledPromo("CAMP-PRIME", testStartsAtUnix, testEndsAtUnix, { discountBps: bps });
          const evalResult = evaluateSingleScheduledPromotion(primeBase, promo);

          assert.ok(Number.isInteger(evalResult.expected_unit_price_paise), `Float in price: ${evalResult.expected_unit_price_paise}`);
          assert.ok(Number.isInteger(evalResult.expected_savings_paise), `Float in savings: ${evalResult.expected_savings_paise}`);
          assert.ok(evalResult.expected_unit_price_paise >= zeroPaise, `Negative price: ${evalResult.expected_unit_price_paise}`);
          assert.ok(evalResult.expected_savings_paise >= zeroPaise, `Negative savings: ${evalResult.expected_savings_paise}`);

          const expectedPrice = Math.floor((primeBase * (10000 - bps)) / 10000);
          assert.equal(evalResult.expected_unit_price_paise, expectedPrice);
          assert.equal(evalResult.expected_unit_price_paise + evalResult.expected_savings_paise, primeBase);
        }
      }
    });

    it("should handle discountPaise edge values (0, exact base, and excessive discount)", () => {
      const zeroPromo = buildScheduledPromo("CAMP-DPAISE-0", testStartsAtUnix, testEndsAtUnix, { discountPaise: zeroPaise });
      const res0 = evaluateSingleScheduledPromotion(mockBasePricePaise, zeroPromo);
      assert.equal(res0.expected_unit_price_paise, mockBasePricePaise);
      assert.equal(res0.expected_savings_paise, zeroPaise);

      const exactBasePromo = buildScheduledPromo("CAMP-DPAISE-EXACT", testStartsAtUnix, testEndsAtUnix, { discountPaise: mockBasePricePaise });
      const resExact = evaluateSingleScheduledPromotion(mockBasePricePaise, exactBasePromo);
      assert.equal(resExact.expected_unit_price_paise, zeroPaise);
      assert.equal(resExact.expected_savings_paise, mockBasePricePaise);

      const excessPromo = buildScheduledPromo("CAMP-DPAISE-EXCESS", testStartsAtUnix, testEndsAtUnix, { discountPaise: mockBasePricePaise + 999999 });
      const resExcess = evaluateSingleScheduledPromotion(mockBasePricePaise, excessPromo);
      assert.equal(resExcess.expected_unit_price_paise, zeroPaise);
      assert.equal(resExcess.expected_savings_paise, mockBasePricePaise);
    });

    it("should handle fixedPricePaise edge values (0, 1, exact base)", () => {
      const freePromo = buildScheduledPromo("CAMP-FIXED-0", testStartsAtUnix, testEndsAtUnix, { fixedPricePaise: zeroPaise });
      const resFree = evaluateSingleScheduledPromotion(mockBasePricePaise, freePromo);
      assert.equal(resFree.expected_unit_price_paise, zeroPaise);
      assert.equal(resFree.expected_savings_paise, mockBasePricePaise);

      const onePaisePromo = buildScheduledPromo("CAMP-FIXED-1", testStartsAtUnix, testEndsAtUnix, { fixedPricePaise: 1 });
      const res1 = evaluateSingleScheduledPromotion(mockBasePricePaise, onePaisePromo);
      assert.equal(res1.expected_unit_price_paise, 1);
      assert.equal(res1.expected_savings_paise, mockBasePricePaise - 1);

      const fullPricePromo = buildScheduledPromo("CAMP-FIXED-FULL", testStartsAtUnix, testEndsAtUnix, { fixedPricePaise: mockBasePricePaise });
      const resFull = evaluateSingleScheduledPromotion(mockBasePricePaise, fullPricePromo);
      assert.equal(resFull.expected_unit_price_paise, mockBasePricePaise);
      assert.equal(resFull.expected_savings_paise, zeroPaise);
    });
  });
});
