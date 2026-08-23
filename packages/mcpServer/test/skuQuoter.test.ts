import { describe, it } from "node:test";
import assert from "node:assert/strict";
import { executeSkuQuote } from "../src/tools/skuQuoter.js";
import { verifyQuoteHash } from "../src/crypto/quoteHashSigner.js";
import { defaultMerchantSecretKey } from "../src/constants/protocolConstants.js";

describe("SkuQuoter (Tool 1: get_live_sku_quote)", () => {
  it("should generate a valid quote for intra-state buyer with 18% GST (CGST + SGST)", () => {
    const quote = executeSkuQuote({
      sku_id: "SKU-CHAIR-001",
      quantity: 1,
      buyer_agent_id: "did:agent:enterprise-procure-01",
      delivery_pincode: "560001" // Bangalore, Karnataka (Intra-state)
    });

    assert.equal(quote.sku_id, "SKU-CHAIR-001");
    assert.equal(quote.base_unit_price_paise, 420000);
    assert.equal(quote.offered_unit_price_paise, 420000);
    assert.equal(quote.currency, "INR");
    assert.equal(quote.hsn_code, "94013000");
    assert.equal(quote.gst_rate_percent, 18);
    assert.equal(quote.tax_breakdown.cgst_paise, 37800);
    assert.equal(quote.tax_breakdown.sgst_paise, 37800);
    assert.equal(quote.tax_breakdown.igst_paise, 0);
    assert.equal(quote.tax_breakdown.total_tax_paise, 75600);
    assert.ok(quote.quote_expiry_timestamp > Math.floor(Date.now() / 1000));
    assert.ok(quote.quote_hash.length === 64);

    const isHashValid = verifyQuoteHash(
      {
        skuId: quote.sku_id,
        quantity: 1,
        offeredUnitPricePaise: quote.offered_unit_price_paise,
        totalTaxPaise: quote.tax_breakdown.total_tax_paise,
        quoteExpiryTimestamp: quote.quote_expiry_timestamp,
        buyerAgentId: "did:agent:enterprise-procure-01"
      },
      quote.quote_hash,
      defaultMerchantSecretKey
    );
    assert.equal(isHashValid, true);
  });

  it("should generate a valid quote for inter-state buyer with 100% IGST", () => {
    const quote = executeSkuQuote({
      sku_id: "SKU-CHAIR-001",
      quantity: 1,
      buyer_agent_id: "did:agent:enterprise-procure-02",
      delivery_pincode: "110001" // New Delhi (Inter-state)
    });

    assert.equal(quote.tax_breakdown.cgst_paise, 0);
    assert.equal(quote.tax_breakdown.sgst_paise, 0);
    assert.equal(quote.tax_breakdown.igst_paise, 75600);
    assert.equal(quote.tax_breakdown.total_tax_paise, 75600);
  });

  it("should apply auto discount stacking when quantity threshold is exceeded", () => {
    // 10 units of SKU-CHAIR-001 -> 500 bps discount (5%) + Festive 10% (capped 2000) + UPI 150
    // Base unit price: 420000 -> Offered unit price: 396850
    const quote = executeSkuQuote({
      sku_id: "SKU-CHAIR-001",
      quantity: 10,
      buyer_agent_id: "did:agent:enterprise-procure-01",
      delivery_pincode: "560001"
    });

    assert.equal(quote.base_unit_price_paise, 420000);
    assert.equal(quote.offered_unit_price_paise, 396850);
    assert.ok(quote.applied_discounts && quote.applied_discounts.length === 3);
    assert.equal(quote.total_savings_paise, 231500);
  });

  it("should stack promo code CORP_5PCT when promo_code is provided", () => {
    const quote = executeSkuQuote({
      sku_id: "SKU-CHAIR-001",
      quantity: 1,
      buyer_agent_id: "did:agent:enterprise-procure-01",
      delivery_pincode: "560001",
      promo_code: "CORP_5PCT"
    });

    // Qty 1 with promo code:
    // Base: 420000
    // Vol: 420000 (no vol tier for 1)
    // Festive 10% cap 2000: 418000 (-2000)
    // UPI 150: 417850 (-150)
    // CORP_5PCT 500 bps: floor(417850 * 0.05) = 20892 -> 417850 - 20892 = 396958
    assert.equal(quote.base_unit_price_paise, 420000);
    assert.equal(quote.offered_unit_price_paise, 396958);
    assert.ok(quote.applied_discounts && quote.applied_discounts.length === 3);
    assert.equal(quote.total_savings_paise, 23042);
  });
});
