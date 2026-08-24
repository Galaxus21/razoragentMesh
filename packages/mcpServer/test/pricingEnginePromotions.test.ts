import { describe, it } from "node:test";
import assert from "node:assert/strict";
import {
  evaluateScheduledPromotions,
  evaluateSingleScheduledPromotion
} from "../src/catalog/pricingEngine.js";
import {
  ScheduledPromotion,
  ArithmeticDriftException
} from "../src/types/mcpToolTypes.js";

describe("PricingEngine Promotional Scheduling & Temporal Evaluation", () => {
  const baseChairPricePaise = 420000;
  const mockCurrentTimeUnix = 1724481000;

  const activePromo: ScheduledPromotion = {
    campaignId: "CAMP-FLASH-01",
    name: "Midnight Flash Sale",
    startsAtUnix: 1724480000,
    endsAtUnix: 1724483600,
    discountBps: 2000,
    limitedStockAllocated: 20
  };

  const upcomingPromo: ScheduledPromotion = {
    campaignId: "CAMP-DIWALI-30",
    name: "Diwali Mega Price Drop",
    startsAtUnix: 1724485000,
    endsAtUnix: 1724490000,
    discountBps: 3000,
    limitedStockAllocated: 50
  };

  const expiredPromo: ScheduledPromotion = {
    campaignId: "CAMP-EARLY-BIRD",
    name: "Early Bird Special",
    startsAtUnix: 1724470000,
    endsAtUnix: 1724475000,
    discountBps: 1000
  };

  it("should separate active vs upcoming promotions based on currentTimeUnix", () => {
    const result = evaluateScheduledPromotions(
      baseChairPricePaise,
      [activePromo, upcomingPromo, expiredPromo],
      mockCurrentTimeUnix
    );

    assert.equal(result.activePromotions.length, 1);
    assert.equal(result.activePromotions[0].campaign_id, "CAMP-FLASH-01");
    assert.equal(result.activePromotions[0].expected_unit_price_paise, 336000);
    assert.equal(result.activePromotions[0].expected_savings_paise, 84000);
    assert.equal(result.activePromotions[0].limited_stock_allocated, 20);

    assert.equal(result.upcomingPromotions.length, 1);
    assert.equal(result.upcomingPromotions[0].campaign_id, "CAMP-DIWALI-30");
    assert.equal(result.upcomingPromotions[0].expected_unit_price_paise, 294000);
    assert.equal(result.upcomingPromotions[0].expected_savings_paise, 126000);
    assert.equal(result.upcomingPromotions[0].limited_stock_allocated, 50);
  });

  it("should evaluate exact integer paise with BPS discount floor division and zero float drift", () => {
    const oddBaseUnitPricePaise = 100003;
    const promoWithOddBps: ScheduledPromotion = {
      campaignId: "CAMP-ODD-BPS",
      name: "Odd BPS Campaign",
      startsAtUnix: 1724485000,
      endsAtUnix: 1724490000,
      discountBps: 3333
    };

    const evaluated = evaluateSingleScheduledPromotion(oddBaseUnitPricePaise, promoWithOddBps);

    // floor(100003 * (10000 - 3333) / 10000) = floor(100003 * 6667 / 10000) = 66672
    assert.equal(evaluated.expected_unit_price_paise, 66672);
    assert.equal(evaluated.expected_savings_paise, 33331);
    assert.equal(
      evaluated.expected_unit_price_paise + evaluated.expected_savings_paise,
      oddBaseUnitPricePaise
    );
  });

  it("should evaluate fixedPricePaise promotion and correct expected savings", () => {
    const fixedPricePromo: ScheduledPromotion = {
      campaignId: "CAMP-FIXED-DROP",
      name: "Fixed ₹3500 Deal",
      startsAtUnix: 1724485000,
      endsAtUnix: 1724490000,
      fixedPricePaise: 350000
    };

    const evaluated = evaluateSingleScheduledPromotion(baseChairPricePaise, fixedPricePromo);

    assert.equal(evaluated.expected_unit_price_paise, 350000);
    assert.equal(evaluated.expected_savings_paise, 70000);
  });

  it("should evaluate discountPaise promotion and clamp unit price to zero paise", () => {
    const flatDiscountPromo: ScheduledPromotion = {
      campaignId: "CAMP-FLAT-500",
      name: "Flat ₹500 Off",
      startsAtUnix: 1724485000,
      endsAtUnix: 1724490000,
      discountPaise: 50000
    };

    const evaluated = evaluateSingleScheduledPromotion(baseChairPricePaise, flatDiscountPromo);
    assert.equal(evaluated.expected_unit_price_paise, 370000);
    assert.equal(evaluated.expected_savings_paise, 50000);

    const excessiveDiscountPromo: ScheduledPromotion = {
      campaignId: "CAMP-EXCESS-DISCOUNT",
      name: "Excessive Discount",
      startsAtUnix: 1724485000,
      endsAtUnix: 1724490000,
      discountPaise: 500000
    };

    const evaluatedExcess = evaluateSingleScheduledPromotion(baseChairPricePaise, excessiveDiscountPromo);
    assert.equal(evaluatedExcess.expected_unit_price_paise, 0);
    assert.equal(evaluatedExcess.expected_savings_paise, baseChairPricePaise);
  });

  it("should reject promotion with endsAtUnix <= startsAtUnix with ArithmeticDriftException", () => {
    const invertedWindowPromo: ScheduledPromotion = {
      campaignId: "CAMP-INVERTED",
      name: "Inverted Window Promo",
      startsAtUnix: 1724490000,
      endsAtUnix: 1724485000,
      discountBps: 2000
    };

    assert.throws(
      () => evaluateSingleScheduledPromotion(baseChairPricePaise, invertedWindowPromo),
      (err: unknown) => err instanceof ArithmeticDriftException && err.message.includes("Invalid temporal window")
    );

    const zeroDurationPromo: ScheduledPromotion = {
      campaignId: "CAMP-ZERO-DUR",
      name: "Zero Duration Promo",
      startsAtUnix: 1724485000,
      endsAtUnix: 1724485000,
      discountBps: 2000
    };

    assert.throws(
      () => evaluateSingleScheduledPromotion(baseChairPricePaise, zeroDurationPromo),
      (err: unknown) => err instanceof ArithmeticDriftException && err.message.includes("Invalid temporal window")
    );
  });

  it("should reject negative savings when fixed price exceeds base price", () => {
    const priceHikePromo: ScheduledPromotion = {
      campaignId: "CAMP-PRICE-HIKE",
      name: "Negative Savings Promo",
      startsAtUnix: 1724485000,
      endsAtUnix: 1724490000,
      fixedPricePaise: 500000
    };

    assert.throws(
      () => evaluateSingleScheduledPromotion(baseChairPricePaise, priceHikePromo),
      (err: unknown) => err instanceof ArithmeticDriftException && err.message.includes("Negative promotion savings")
    );
  });

  it("should reject floating-point baseUnitPricePaise or currentTimeUnix", () => {
    assert.throws(
      () => evaluateScheduledPromotions(4200.5, [upcomingPromo], mockCurrentTimeUnix),
      (err: unknown) => err instanceof ArithmeticDriftException && err.message.includes("Float math drift")
    );

    assert.throws(
      () => evaluateScheduledPromotions(baseChairPricePaise, [upcomingPromo], 1724481000.5),
      (err: unknown) => err instanceof ArithmeticDriftException && err.message.includes("Float math drift")
    );
  });

  it("should handle exact temporal boundaries strictly", () => {
    const boundaryPromo: ScheduledPromotion = {
      campaignId: "CAMP-BOUND",
      name: "Boundary Promo",
      startsAtUnix: 1000,
      endsAtUnix: 2000,
      discountBps: 1000
    };

    // Exactly at startsAtUnix -> active
    const atStart = evaluateScheduledPromotions(10000, [boundaryPromo], 1000);
    assert.equal(atStart.activePromotions.length, 1);
    assert.equal(atStart.upcomingPromotions.length, 0);

    // 1 second before startsAtUnix -> upcoming
    const beforeStart = evaluateScheduledPromotions(10000, [boundaryPromo], 999);
    assert.equal(beforeStart.activePromotions.length, 0);
    assert.equal(beforeStart.upcomingPromotions.length, 1);

    // 1 second before endsAtUnix -> active
    const beforeEnd = evaluateScheduledPromotions(10000, [boundaryPromo], 1999);
    assert.equal(beforeEnd.activePromotions.length, 1);
    assert.equal(beforeEnd.upcomingPromotions.length, 0);

    // Exactly at endsAtUnix -> expired (omitted from both)
    const atEnd = evaluateScheduledPromotions(10000, [boundaryPromo], 2000);
    assert.equal(atEnd.activePromotions.length, 0);
    assert.equal(atEnd.upcomingPromotions.length, 0);
  });

  it("should handle empty or undefined promotions array gracefully", () => {
    const emptyResult = evaluateScheduledPromotions(baseChairPricePaise, [], mockCurrentTimeUnix);
    assert.deepEqual(emptyResult, { activePromotions: [], upcomingPromotions: [] });

    const undefinedResult = evaluateScheduledPromotions(baseChairPricePaise, undefined, mockCurrentTimeUnix);
    assert.deepEqual(undefinedResult, { activePromotions: [], upcomingPromotions: [] });
  });
});
