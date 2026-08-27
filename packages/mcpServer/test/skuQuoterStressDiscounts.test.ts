import { describe, it } from "node:test";
import assert from "node:assert/strict";
import { executeSkuQuote } from "../src/tools/skuQuoter.js";
import { skuQuoteResponseSchema } from "../src/schemas/skuQuoteSchema.js";
import { defaultCatalogStore, CatalogStore } from "../src/catalog/catalogStore.js";
import { currencyInr } from "../src/constants/protocolConstants.js";
import { CatalogSkuItem } from "../src/types/mcpToolTypes.js";
import { verifyQuoteHash } from "../src/crypto/quoteHashSigner.js";

const testBuyerId = "did:agent:challenger2-tester";
const intraStatePincode = "560001";

function buildMicroCheapSku(): CatalogSkuItem {
  return {
    skuId: "SKU-CHEAP-MICRO",
    name: "Micro Resistor Component",
    category: "Electronics",
    description: "Small electronic component priced under UPI cashback threshold",
    hsnCode: "85331000",
    gstRatePercent: 18,
    baseUnitPricePaise: 100,
    availableStock: 500,
    volumeTiers: []
  };
}

function buildEnterpriseSku(): CatalogSkuItem {
  return {
    skuId: "SKU-SERVER-ENTERPRISE",
    name: "Enterprise Rack Server",
    category: "Hardware",
    description: "Enterprise multi-node compute server",
    hsnCode: "84715000",
    gstRatePercent: 18,
    baseUnitPricePaise: 100000000,
    availableStock: 5,
    volumeTiers: []
  };
}

describe("SkuQuoter Stress - Discounts & Schema Integrity", () => {
  describe("Schema Integrity & Q=1 Auto-Stacking Validation", () => {
    it("should pass skuQuoteResponseSchema validation on Q=1 quotes across all catalog SKUs", () => {
      const allSkus = defaultCatalogStore.getAllSkus();
      assert.ok(allSkus.length >= 20, "Catalog should have at least 20 pre-seeded SKUs");

      for (const sku of allSkus) {
        const quote = executeSkuQuote({
          sku_id: sku.skuId,
          quantity: 1,
          buyer_agent_id: testBuyerId,
          delivery_pincode: intraStatePincode
        });

        const parsed = skuQuoteResponseSchema.parse(quote);
        assert.equal(parsed.sku_id, sku.skuId);
        assert.equal(parsed.currency, currencyInr);
        assert.ok(Array.isArray(parsed.applied_discounts));
        assert.ok(typeof parsed.total_savings_paise === "number");
        assert.ok(parsed.total_savings_paise >= 0);
        assert.ok(parsed.offered_unit_price_paise <= parsed.base_unit_price_paise);
        assert.equal(
          parsed.base_unit_price_paise - parsed.offered_unit_price_paise,
          parsed.total_savings_paise
        );
      }
    });

    it("should validate all applied discount items have valid enum types and integer discounts", () => {
      const quote = executeSkuQuote({
        sku_id: "SKU-CHAIR-001",
        quantity: 1,
        buyer_agent_id: testBuyerId,
        delivery_pincode: intraStatePincode,
        promo_code: "CORP_5PCT"
      });

      assert.ok(quote.applied_discounts && quote.applied_discounts.length >= 3);
      const validTypes = new Set(["VOLUME_TIER", "CAMPAIGN", "PAYMENT_RAIL", "PROMO_CODE"]);

      for (const item of quote.applied_discounts) {
        assert.ok(validTypes.has(item.type), `Invalid discount type: ${item.type}`);
        assert.ok(typeof item.label === "string" && item.label.length > 0);
        if (item.discountBps !== undefined) {
          assert.ok(Number.isInteger(item.discountBps));
          assert.ok(item.discountBps >= 0);
        }
        if (item.discountPaise !== undefined) {
          assert.ok(Number.isInteger(item.discountPaise));
          assert.ok(item.discountPaise >= 0);
        }
      }
    });

    it("should reject skuQuoteResponse with invalid discount enum type", () => {
      const invalidResponse = {
        sku_id: "SKU-CHAIR-001",
        available_stock: 10,
        base_unit_price_paise: 420000,
        offered_unit_price_paise: 417850,
        currency: "INR",
        hsn_code: "94013000",
        gst_rate_percent: 18,
        tax_breakdown: { cgst_paise: 37606, sgst_paise: 37606, igst_paise: 0, total_tax_paise: 75212 },
        quote_expiry_timestamp: 1800000000,
        quote_hash: "a".repeat(64),
        applied_discounts: [{ type: "INVALID_DISCOUNT_TYPE", label: "Fraudulent Coupon", discountPaise: 1000 }],
        total_savings_paise: 1000
      };

      assert.throws(() => skuQuoteResponseSchema.parse(invalidResponse));
    });

    it("should reject skuQuoteResponse with float or negative total_savings_paise", () => {
      const baseObj = {
        sku_id: "SKU-CHAIR-001",
        available_stock: 10,
        base_unit_price_paise: 420000,
        offered_unit_price_paise: 417850,
        currency: "INR",
        hsn_code: "94013000",
        gst_rate_percent: 18,
        tax_breakdown: { cgst_paise: 37606, sgst_paise: 37606, igst_paise: 0, total_tax_paise: 75212 },
        quote_expiry_timestamp: 1800000000,
        quote_hash: "a".repeat(64)
      };

      assert.throws(() => skuQuoteResponseSchema.parse({ ...baseObj, total_savings_paise: -100 }));
      assert.throws(() => skuQuoteResponseSchema.parse({ ...baseObj, total_savings_paise: 12.34 }));
    });

    it("should reject skuQuoteResponse with non-INR currency or missing tax breakdown", () => {
      const validQuote = executeSkuQuote({
        sku_id: "SKU-CHAIR-001",
        quantity: 1,
        buyer_agent_id: testBuyerId,
        delivery_pincode: intraStatePincode
      });

      assert.throws(() => skuQuoteResponseSchema.parse({ ...validQuote, currency: "USD" }));

      const missingTax = { ...validQuote };
      delete (missingTax as Record<string, unknown>).tax_breakdown;
      assert.throws(() => skuQuoteResponseSchema.parse(missingTax));
    });
  });

  describe("Extreme Price Boundary & Discount Clamping Stress Tests", () => {
    it("should handle sub-cashback pricing (base price < UPI ₹1.50) with non-negative clamping", () => {
      const customStore = new CatalogStore([buildMicroCheapSku()]);
      const quote = executeSkuQuote(
        { sku_id: "SKU-CHEAP-MICRO", quantity: 1, buyer_agent_id: testBuyerId, delivery_pincode: intraStatePincode },
        customStore
      );

      assert.equal(quote.base_unit_price_paise, 100);
      assert.equal(quote.offered_unit_price_paise, 0);
      assert.equal(quote.total_savings_paise, 100);
      assert.equal(quote.tax_breakdown.total_tax_paise, 0);
      assert.equal(quote.tax_breakdown.cgst_paise, 0);
      assert.equal(quote.tax_breakdown.sgst_paise, 0);
      assert.equal(quote.base_unit_price_paise - quote.offered_unit_price_paise, quote.total_savings_paise);

      const isValid = verifyQuoteHash(
        {
          skuId: "SKU-CHEAP-MICRO",
          quantity: 1,
          offeredUnitPricePaise: quote.offered_unit_price_paise,
          totalTaxPaise: quote.tax_breakdown.total_tax_paise,
          quoteExpiryTimestamp: quote.quote_expiry_timestamp,
          buyerAgentId: testBuyerId
        },
        quote.quote_hash
      );
      assert.equal(isValid, true);
    });

    it("should handle large enterprise SKU (₹1,000,000 base price) with cap enforcement", () => {
      const customStore = new CatalogStore([buildEnterpriseSku()]);
      const quote = executeSkuQuote(
        { sku_id: "SKU-SERVER-ENTERPRISE", quantity: 1, buyer_agent_id: testBuyerId, delivery_pincode: intraStatePincode },
        customStore
      );

      assert.equal(quote.base_unit_price_paise, 100000000);
      assert.equal(quote.offered_unit_price_paise, 99997850);
      assert.equal(quote.total_savings_paise, 2150);

      const parsed = skuQuoteResponseSchema.parse(quote);
      assert.equal(parsed.offered_unit_price_paise, 99997850);
    });
  });
});
