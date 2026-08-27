import { describe, it } from "node:test";
import assert from "node:assert/strict";
import { executeSkuQuote } from "../src/tools/skuQuoter.js";
import {
  verifyQuoteHash,
  QuoteSignParams
} from "../src/crypto/quoteHashSigner.js";
import { defaultCatalogStore } from "../src/catalog/catalogStore.js";
import { defaultMerchantSecretKey } from "../src/constants/protocolConstants.js";

const testBuyerId = "did:agent:challenger2-tester";
const intraStatePincode = "560001";

function buildQuoteParams(quote: ReturnType<typeof executeSkuQuote>, quantity = 1, buyerId = testBuyerId): QuoteSignParams {
  return {
    skuId: quote.sku_id,
    quantity,
    offeredUnitPricePaise: quote.offered_unit_price_paise,
    totalTaxPaise: quote.tax_breakdown.total_tax_paise,
    quoteExpiryTimestamp: quote.quote_expiry_timestamp,
    buyerAgentId: buyerId
  };
}

describe("SkuQuoter Stress - Concurrency & Signature Tamper Resistance", () => {
  describe("HMAC-SHA256 Signature Verification & Tamper Resistance", () => {
    it("should generate cryptographically verifiable HMAC-SHA256 signatures for all catalog items on Q=1", () => {
      const allSkus = defaultCatalogStore.getAllSkus();

      for (const sku of allSkus) {
        const quote = executeSkuQuote({
          sku_id: sku.skuId,
          quantity: 1,
          buyer_agent_id: testBuyerId,
          delivery_pincode: intraStatePincode
        });

        const signParams = buildQuoteParams(quote, 1, testBuyerId);
        const isValid = verifyQuoteHash(signParams, quote.quote_hash, defaultMerchantSecretKey);
        assert.equal(isValid, true, `HMAC verification failed for SKU ${sku.skuId}`);
      }
    });

    it("should verify HMAC-SHA256 signature with custom merchant secret key", () => {
      const customSecret = "custom_super_secure_key_1234567890!@#$";
      const quote = executeSkuQuote(
        {
          sku_id: "SKU-CHAIR-001",
          quantity: 1,
          buyer_agent_id: testBuyerId,
          delivery_pincode: intraStatePincode
        },
        defaultCatalogStore,
        customSecret
      );

      const signParams = buildQuoteParams(quote, 1, testBuyerId);
      assert.equal(verifyQuoteHash(signParams, quote.quote_hash, customSecret), true);
      assert.equal(verifyQuoteHash(signParams, quote.quote_hash, defaultMerchantSecretKey), false);
    });

    it("should reject tampered quantity in HMAC signature verification (Q=1 vs Q=2)", () => {
      const quote = executeSkuQuote({
        sku_id: "SKU-CHAIR-001",
        quantity: 1,
        buyer_agent_id: testBuyerId,
        delivery_pincode: intraStatePincode
      });

      const tamperedParams = buildQuoteParams(quote, 2, testBuyerId);
      assert.equal(verifyQuoteHash(tamperedParams, quote.quote_hash, defaultMerchantSecretKey), false);
    });

    it("should reject tampered unit price or tax in quote hash verification", () => {
      const quote = executeSkuQuote({
        sku_id: "SKU-CHAIR-001",
        quantity: 1,
        buyer_agent_id: testBuyerId,
        delivery_pincode: intraStatePincode
      });
      const baseParams = buildQuoteParams(quote, 1, testBuyerId);

      const plusPrice = { ...baseParams, offeredUnitPricePaise: baseParams.offeredUnitPricePaise + 1 };
      const minusPrice = { ...baseParams, offeredUnitPricePaise: baseParams.offeredUnitPricePaise - 1 };
      const plusTax = { ...baseParams, totalTaxPaise: baseParams.totalTaxPaise + 1 };

      assert.equal(verifyQuoteHash(plusPrice, quote.quote_hash), false);
      assert.equal(verifyQuoteHash(minusPrice, quote.quote_hash), false);
      assert.equal(verifyQuoteHash(plusTax, quote.quote_hash), false);
    });

    it("should reject tampered timestamp, buyer DID, or SKU ID in quote hash verification", () => {
      const quote = executeSkuQuote({
        sku_id: "SKU-CHAIR-001",
        quantity: 1,
        buyer_agent_id: testBuyerId,
        delivery_pincode: intraStatePincode
      });
      const baseParams = buildQuoteParams(quote, 1, testBuyerId);

      const modTimestamp = { ...baseParams, quoteExpiryTimestamp: baseParams.quoteExpiryTimestamp + 1 };
      const modBuyer = { ...baseParams, buyerAgentId: "did:agent:attacker-impersonator" };
      const modSku = { ...baseParams, skuId: "SKU-CHAIR-002" };

      assert.equal(verifyQuoteHash(modTimestamp, quote.quote_hash), false);
      assert.equal(verifyQuoteHash(modBuyer, quote.quote_hash), false);
      assert.equal(verifyQuoteHash(modSku, quote.quote_hash), false);
    });

    it("should safely handle malformed, truncated, or invalid length hash without crash", () => {
      const signParams: QuoteSignParams = {
        skuId: "SKU-CHAIR-001",
        quantity: 1,
        offeredUnitPricePaise: 417850,
        totalTaxPaise: 75212,
        quoteExpiryTimestamp: 1800000000,
        buyerAgentId: testBuyerId
      };

      assert.equal(verifyQuoteHash(signParams, ""), false);
      assert.equal(verifyQuoteHash(signParams, "short_hash"), false);
      assert.equal(verifyQuoteHash(signParams, "a".repeat(63)), false);
      assert.equal(verifyQuoteHash(signParams, "a".repeat(65)), false);
    });
  });
});
