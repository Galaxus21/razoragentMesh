import { describe, it } from "node:test";
import assert from "node:assert/strict";

import {
  evaluateScheduledPromotions,
  evaluateSingleScheduledPromotion
} from "../src/catalog/pricingEngine.js";
import { executeSkuQuote } from "../src/tools/skuQuoter.js";
import { CatalogStore } from "../src/catalog/catalogStore.js";
import {
  ScheduledPromotion,
  CatalogSkuItem,
  ArithmeticDriftException
} from "../src/types/mcpToolTypes.js";

const mockBasePricePaise = 420000;
const testStartsAtUnix = 1724485000;
const testEndsAtUnix = 1724490000;
const validBuyerAgentId = "did:agent:test-buyer-001";
const validPincode = "560001";

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

describe("PricingEngine Stress — Edge Cases & Exceptions", () => {
  describe("Adversarial Negative Cases & Exception Handling", () => {
    it("should reject temporal windows where endsAtUnix <= startsAtUnix", () => {
      const equalTimesPromo = buildScheduledPromo("CAMP-EQUAL", testStartsAtUnix, testStartsAtUnix, { discountBps: 1000 });
      assert.throws(
        () => evaluateSingleScheduledPromotion(mockBasePricePaise, equalTimesPromo),
        (err: unknown) => err instanceof ArithmeticDriftException && err.message.includes("Invalid temporal window")
      );

      const invertedTimesPromo = buildScheduledPromo("CAMP-INVERTED", testEndsAtUnix, testStartsAtUnix, { discountBps: 1000 });
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
      const validPromo = buildScheduledPromo("CAMP-VALID", testStartsAtUnix, testEndsAtUnix, { discountBps: 1000 });

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

      const floatFixedPromo = buildScheduledPromo("CAMP-FLOAT-FIXED", testStartsAtUnix, testEndsAtUnix, { fixedPricePaise: 3500.75 });
      assert.throws(
        () => evaluateSingleScheduledPromotion(mockBasePricePaise, floatFixedPromo),
        (err: unknown) => err instanceof ArithmeticDriftException && err.message.includes("Float math drift")
      );
    });
  });

  describe("Backward Compatibility & End-to-End Tool Execution", () => {
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
        { sku_id: "SKU-TEST-NOPROMO", quantity: 1, buyer_agent_id: validBuyerAgentId, delivery_pincode: validPincode },
        customStore
      );

      assert.equal(quote.sku_id, "SKU-TEST-NOPROMO");
      assert.equal(quote.offered_unit_price_paise, 497850);
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
        { sku_id: "SKU-TEST-EMPTYPROMO", quantity: 1, buyer_agent_id: validBuyerAgentId, delivery_pincode: validPincode },
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
        { sku_id: "SKU-TEST-PROMO", quantity: 1, buyer_agent_id: validBuyerAgentId, delivery_pincode: validPincode },
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
