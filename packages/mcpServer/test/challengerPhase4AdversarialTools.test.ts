import { describe, it } from "node:test";
import assert from "node:assert/strict";
import { executeSkuQuote } from "../src/tools/skuQuoter.js";
import { CatalogStore } from "../src/catalog/catalogStore.js";
import { verifyQuoteHash } from "../src/crypto/quoteHashSigner.js";
import { CatalogSkuItem } from "../src/types/mcpToolTypes.js";

function buildPromoChallengerSku(nowUnix: number): CatalogSkuItem {
  return {
    skuId: "SKU-PROMO-CHALLENGER",
    name: "Challenger Promo Item",
    category: "Electronics",
    description: "Multiple promotion windows",
    hsnCode: "85044090",
    gstRatePercent: 18,
    baseUnitPricePaise: 100000,
    availableStock: 20,
    volumeTiers: [],
    promotions: [
      { campaignId: "PROMO-EXPIRED", name: "Expired Flash Deal", startsAtUnix: nowUnix - 3600, endsAtUnix: nowUnix - 60, discountBps: 2500 },
      { campaignId: "PROMO-ACTIVE", name: "Current Active Sale", startsAtUnix: nowUnix - 60, endsAtUnix: nowUnix + 3600, discountBps: 1500 },
      { campaignId: "PROMO-UPCOMING-1", name: "Tomorrow Midnight Deal", startsAtUnix: nowUnix + 86400, endsAtUnix: nowUnix + 90000, discountBps: 3000, limitedStockAllocated: 5 }
    ]
  };
}

describe("Challenger 1 — Phase 4 Adversarial Tools & Quoter (mcpServer)", () => {
  describe("SkuQuoter Quote Execution & Multi-State GST Breakdown", () => {
    it("should compute exact intra-state GST (50/50 CGST and SGST, 0 IGST) for Karnataka buyer", () => {
      const store = new CatalogStore();
      const quote = executeSkuQuote(
        { sku_id: "SKU-CHAIR-001", quantity: 1, buyer_agent_id: "did:agent:buyer-intra", delivery_pincode: "560001" },
        store
      );

      assert.equal(quote.tax_breakdown.igst_paise, 0);
      assert.ok(quote.tax_breakdown.cgst_paise > 0);
      assert.ok(quote.tax_breakdown.sgst_paise > 0);
      assert.equal(quote.tax_breakdown.cgst_paise, quote.tax_breakdown.sgst_paise);
      assert.equal(quote.tax_breakdown.cgst_paise + quote.tax_breakdown.sgst_paise, quote.tax_breakdown.total_tax_paise);
    });

    it("should compute exact inter-state GST (100% IGST, 0 CGST, 0 SGST) for Maharashtra buyer", () => {
      const store = new CatalogStore();
      const quote = executeSkuQuote(
        { sku_id: "SKU-CHAIR-001", quantity: 1, buyer_agent_id: "did:agent:buyer-inter", delivery_pincode: "400001" },
        store
      );

      assert.equal(quote.tax_breakdown.cgst_paise, 0);
      assert.equal(quote.tax_breakdown.sgst_paise, 0);
      assert.ok(quote.tax_breakdown.igst_paise > 0);
      assert.equal(quote.tax_breakdown.igst_paise, quote.tax_breakdown.total_tax_paise);
    });

    it("should verify HMAC-SHA256 quote hash validity and reject tampering", () => {
      const store = new CatalogStore();
      const secret = "test_custom_secret_key_1234567890";
      const quote = executeSkuQuote(
        { sku_id: "SKU-CHAIR-001", quantity: 2, buyer_agent_id: "did:agent:buyer-hash-test", delivery_pincode: "560001" },
        store,
        secret
      );

      const baseParams = {
        skuId: quote.sku_id,
        quantity: 2,
        offeredUnitPricePaise: quote.offered_unit_price_paise,
        totalTaxPaise: quote.tax_breakdown.total_tax_paise,
        quoteExpiryTimestamp: quote.quote_expiry_timestamp,
        buyerAgentId: "did:agent:buyer-hash-test"
      };

      assert.equal(verifyQuoteHash(baseParams, quote.quote_hash, secret), true);
      assert.equal(verifyQuoteHash({ ...baseParams, buyerAgentId: "did:agent:buyer-attacker" }, quote.quote_hash, secret), false);
    });

    it("should stack volume discount and promo code correctly without float drift", () => {
      const store = new CatalogStore();
      const quote = executeSkuQuote(
        { sku_id: "SKU-CHAIR-001", quantity: 5, buyer_agent_id: "did:agent:buyer-stacked", delivery_pincode: "560001", promo_code: "CORP_5PCT" },
        store
      );

      assert.ok(quote.applied_discounts.length >= 2);
      assert.ok(quote.offered_unit_price_paise < quote.base_unit_price_paise);
      assert.equal(quote.offered_unit_price_paise + Math.floor(quote.total_savings_paise / 5), quote.base_unit_price_paise);
      assert.ok(Number.isInteger(quote.offered_unit_price_paise));
      assert.ok(Number.isInteger(quote.total_savings_paise));
    });
  });

  describe("Scheduled Promotions Window Evaluation", () => {
    it("should accurately segregate active, upcoming, and expired promotions in quote packaging", () => {
      const nowUnix = Math.floor(Date.now() / 1000);
      const store = new CatalogStore();
      store.addSku(buildPromoChallengerSku(nowUnix));

      const quote = executeSkuQuote(
        { sku_id: "SKU-PROMO-CHALLENGER", quantity: 1, buyer_agent_id: "did:agent:buyer-promo", delivery_pincode: "560001" },
        store
      );

      assert.ok(quote.upcoming_promotions);
      assert.equal(quote.upcoming_promotions.length, 1);
      assert.equal(quote.upcoming_promotions[0].campaign_id, "PROMO-UPCOMING-1");
      assert.equal(quote.upcoming_promotions[0].expected_unit_price_paise, 70000);
      assert.equal(quote.upcoming_promotions[0].expected_savings_paise, 30000);
      assert.equal(quote.upcoming_promotions[0].limited_stock_allocated, 5);
    });
  });
});
