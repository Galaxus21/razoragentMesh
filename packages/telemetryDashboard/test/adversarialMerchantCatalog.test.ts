import { describe, it } from "node:test";
import assert from "node:assert/strict";
import {
  categoryOptions,
  defaultCatalogFormState,
  defaultGstRatePercent,
  hsnGstLookupTable,
  maxDiscountBps,
  maxQuoteTtlSeconds,
  minQuoteTtlSeconds,
  minVolumeQuantity,
} from "../src/constants/merchantCatalogConstants.js";
import {
  buildUniversalProductPayload,
  convertInrToPaise,
  formatPaiseToInr,
  resolveGstFromHsn,
  validateMerchantCatalogForm,
} from "../src/lib/merchantCatalogValidator.js";
import { MerchantCatalogFormData, VolumeTierInput } from "../src/types/merchantCatalogTypes.js";

const baseValidTestForm: MerchantCatalogFormData = {
  ...defaultCatalogFormState,
  skuId: "SKU-ADV-001",
  merchantDid: "did:razoragent:merchant:test01",
  title: "Adversarial Test Gold Ring",
  description: "A valid test description meeting all length and format constraints.",
  category: "Jewelry",
  hsnCode: "71131910",
  gstRatePercent: 3,
  basePriceInr: "42000.00",
  availableStock: 25,
  originPincode: "560001",
  selectedFacet: "none",
  bullionPricing: {
    ...defaultCatalogFormState.bullionPricing,
    enabled: true,
    netWeightGrams: 5.5,
    maxQuoteTtlSeconds: 60,
  },
  jewelryFacet: {
    purityCarat: 22,
    grossWeightGrams: 5.8,
    hallmarkNumber: "BIS-HM-KA-2026-001",
  },
};

describe("Adversarial Stress Suite 1: Float Precision & Currency Invariants", () => {
  it("should accurately convert micro-rupee boundaries and extreme scales without floating drift", () => {
    // 0.01 INR = 1 paise
    assert.equal(convertInrToPaise(0.01), 1);
    assert.equal(convertInrToPaise("0.01"), 1);

    // 9,999,999.99 INR = 999,999,999 paise
    assert.equal(convertInrToPaise(9999999.99), 999999999);
    assert.equal(convertInrToPaise("9999999.99"), 999999999);

    // Whitespace handling
    assert.equal(convertInrToPaise(" 12.34 "), 1234);
    assert.equal(convertInrToPaise("\t99.50\n"), 9950);

    // Known floating point precision edge cases in IEEE 754
    assert.equal(convertInrToPaise(0.07), 7);
    assert.equal(convertInrToPaise(0.29), 29);
    assert.equal(convertInrToPaise(0.58), 58);
    assert.equal(convertInrToPaise(1.14), 114);
    assert.equal(convertInrToPaise(1.29), 129);
    assert.equal(convertInrToPaise(19.99), 1999);
    assert.equal(convertInrToPaise(35.10), 3510);
    assert.equal(convertInrToPaise(59.99), 5999);
    assert.equal(convertInrToPaise(79.99), 7999);
    assert.equal(convertInrToPaise(99.99), 9999);
    assert.equal(convertInrToPaise(99999999.99), 9999999999);
  });

  it("should strictly clamp sub-paise fractions and reject negative or non-numeric values", () => {
    // Sub-paise half-rounding
    assert.equal(convertInrToPaise(0.004), 0); // 0.4 paise rounds down to 0
    assert.equal(convertInrToPaise(0.005), 1); // 0.5 paise rounds up to 1
    assert.equal(convertInrToPaise(0.006), 1); // 0.6 paise rounds up to 1

    // Zero and negative inputs
    assert.equal(convertInrToPaise(0), 0);
    assert.equal(convertInrToPaise("0"), 0);
    assert.equal(convertInrToPaise("0.00"), 0);
    assert.equal(convertInrToPaise(-0.01), 0);
    assert.equal(convertInrToPaise("-0.01"), 0);
    assert.equal(convertInrToPaise(-9999), 0);
    assert.equal(convertInrToPaise("-9999.99"), 0);

    // Non-finite and malformed values
    assert.equal(convertInrToPaise(NaN), 0);
    assert.equal(convertInrToPaise(null), 0);
    assert.equal(convertInrToPaise(undefined), 0);
    assert.equal(convertInrToPaise(""), 0);
    assert.equal(convertInrToPaise("    "), 0);
    assert.equal(convertInrToPaise("abc"), 0);
    assert.equal(convertInrToPaise("₹42.00"), 0);
  });
});

describe("Adversarial Stress Suite 2: Extreme HSN Code Resolution & Fallbacks", () => {
  it("should resolve statutory GST for hierarchical prefix matches (8, 6, 4, 2 digits)", () => {
    // 8-digit input matching 4-digit prefix: 71131910 -> 3%
    assert.equal(resolveGstFromHsn("71131910"), 3);

    // 6-digit input matching 4-digit prefix: 610910 -> 5%
    assert.equal(resolveGstFromHsn("610910"), 5);

    // 4-digit exact match: 8471 -> 18%
    assert.equal(resolveGstFromHsn("8471"), 18);

    // 2-digit input (below statutory 4-digit minimum) defaults to 18%
    assert.equal(resolveGstFromHsn("71"), 18);
  });

  it("should gracefully handle malformed, non-numeric, or extreme-length HSN strings", () => {
    // Non-numeric characters stripped to find digits
    assert.equal(resolveGstFromHsn(" 71131910 "), 3);
    assert.equal(resolveGstFromHsn("HSN-7113-1910"), 3);
    assert.equal(resolveGstFromHsn("6109.10.00"), 5);

    // Purely non-numeric strings
    assert.equal(resolveGstFromHsn("INVALID_HSN"), 18);
    assert.equal(resolveGstFromHsn("!@#$%^&*()"), 18);
    assert.equal(resolveGstFromHsn(""), 18);

    // Unknown numeric codes defaulting to statutory 18%
    assert.equal(resolveGstFromHsn("99999999"), 18);
    assert.equal(resolveGstFromHsn("00000000"), 18);
    assert.equal(resolveGstFromHsn("12345678"), 18);

    // Under-length single digit
    assert.equal(resolveGstFromHsn("9"), 18);

    // Extreme length 20-digit string
    assert.equal(resolveGstFromHsn("71131910999999999999"), 3);
  });
});

describe("Adversarial Stress Suite 3: Volume Tier Boundary Invariants", () => {
  it("should accept valid 0 BPS (0%) and 10000 BPS (100%) discount boundaries", () => {
    const boundaryTiersForm: MerchantCatalogFormData = {
      ...baseValidTestForm,
      volumeTiers: [
        { minQuantity: 1, discountBps: 0 },
        { minQuantity: 100, discountBps: 10000 },
      ],
    };

    const validation = validateMerchantCatalogForm(boundaryTiersForm);
    assert.equal(validation.isValid, true);

    const payload = buildUniversalProductPayload(boundaryTiersForm);
    assert.equal(payload.volumeTiers[0].minQuantity, 1);
    assert.equal(payload.volumeTiers[0].discountBps, 0);
    assert.equal(payload.volumeTiers[1].minQuantity, 100);
    assert.equal(payload.volumeTiers[1].discountBps, 10000);
  });

  it("should reject negative BPS, excess BPS (>10000), and zero/negative minQuantity", () => {
    const invalidTiersForm: MerchantCatalogFormData = {
      ...baseValidTestForm,
      volumeTiers: [
        { minQuantity: -5, discountBps: -100 },
        { minQuantity: 0, discountBps: 10001 },
        { minQuantity: 10, discountBps: 50000 },
      ],
    };

    const validation = validateMerchantCatalogForm(invalidTiersForm);
    assert.equal(validation.isValid, false);
    assert.ok(validation.errors.volumeTier_0_qty);
    assert.ok(validation.errors.volumeTier_0_bps);
    assert.ok(validation.errors.volumeTier_1_qty);
    assert.ok(validation.errors.volumeTier_1_bps);
    assert.ok(validation.errors.volumeTier_2_bps);
  });
});

describe("Adversarial Stress Suite 4: Bullion Dynamic Pricing Boundary Invariants", () => {
  it("should accept zero making charges and extreme gold weights", () => {
    const zeroMakingChargesForm: MerchantCatalogFormData = {
      ...baseValidTestForm,
      selectedFacet: "jewelry",
      jewelryFacet: {
        purityCarat: 24,
        grossWeightGrams: 1000.0,
        hallmarkNumber: "BIS-HM-KA-2026-001",
      },
      bullionPricing: {
        enabled: true,
        oracleFeedSymbol: "MCX_GOLD_24K_INR_PER_GRAM",
        purityMultiplier: 1.0,
        netWeightGrams: 1000.0, // 1 kg gold bar
        makingChargesInr: "0.00", // 0 making charges
        makingChargesType: "FIXED_PAISE",
        stoneChargesInr: "0",
        maxQuoteTtlSeconds: 300, // Maximum allowed TTL
      },
    };

    const validation = validateMerchantCatalogForm(zeroMakingChargesForm);
    assert.equal(validation.isValid, true);

    const payload = buildUniversalProductPayload(zeroMakingChargesForm);
    assert.ok(payload.jewelryFacet?.dynamicPricingRule);
    assert.equal(payload.jewelryFacet.dynamicPricingRule.makingChargesPaise, 0);
    assert.equal(payload.jewelryFacet.dynamicPricingRule.stoneChargesPaise, 0);
    assert.equal(payload.jewelryFacet.dynamicPricingRule.netWeightGrams, "1000");
    assert.equal(payload.jewelryFacet.dynamicPricingRule.maxQuoteTtlSeconds, 300);
  });

  it("should reject negative/zero net weight and out-of-bounds quote TTLs", () => {
    const invalidBullionForm: MerchantCatalogFormData = {
      ...baseValidTestForm,
      bullionPricing: {
        enabled: true,
        oracleFeedSymbol: "MCX_SILVER_INR_PER_KG",
        purityMultiplier: 0.999,
        netWeightGrams: -10.5,
        makingChargesInr: "100.00",
        makingChargesType: "FIXED_PAISE",
        stoneChargesInr: "0",
        maxQuoteTtlSeconds: 5, // Below minQuoteTtlSeconds (10s)
      },
    };

    const validation = validateMerchantCatalogForm(invalidBullionForm);
    assert.equal(validation.isValid, false);
    assert.ok(validation.errors.bullionNetWeight);
    assert.ok(validation.errors.bullionTtl);

    const excessTtlForm: MerchantCatalogFormData = {
      ...invalidBullionForm,
      bullionPricing: {
        ...invalidBullionForm.bullionPricing,
        netWeightGrams: 5.0,
        maxQuoteTtlSeconds: 301, // Above maxQuoteTtlSeconds (300s)
      },
    };

    const excessValidation = validateMerchantCatalogForm(excessTtlForm);
    assert.equal(excessValidation.isValid, false);
    assert.ok(excessValidation.errors.bullionTtl);
  });
});

describe("Adversarial Stress Suite 5: Domain Facet Edge Cases & Field Sanitization", () => {
  it("should properly sanitize FMCG facet with optional FSSAI and filter empty allergen strings", () => {
    // Valid FMCG with no FSSAI license (optional field)
    const fmcgNoFssaiForm: MerchantCatalogFormData = {
      ...baseValidTestForm,
      skuId: "SKU-FMCG-ORGANIC-01",
      category: "FMCG",
      selectedFacet: "fmcg",
      bullionPricing: { ...defaultCatalogFormState.bullionPricing, enabled: false },
      fmcgFacet: {
        allergens: ["Gluten", "  ", "", "Soy "],
        shelfLifeDays: 180,
        isVeg: true,
        fssaiNumber: "", // Empty optional string
      },
    };

    const validation = validateMerchantCatalogForm(fmcgNoFssaiForm);
    assert.equal(validation.isValid, true);

    const payload = buildUniversalProductPayload(fmcgNoFssaiForm);
    assert.ok(payload.fmcgFacet);
    // Allergens must have empty strings stripped
    assert.deepEqual(payload.fmcgFacet.allergens, ["Gluten", "Soy "]);
    assert.equal(payload.fmcgFacet.isVeg, true);
    assert.equal(payload.fmcgFacet.shelfLifeDays, 180);
  });

  it("should reject invalid FMCG FSSAI license numbers (must be exactly 14 digits)", () => {
    const invalidFssaiForm: MerchantCatalogFormData = {
      ...baseValidTestForm,
      selectedFacet: "fmcg",
      bullionPricing: { ...defaultCatalogFormState.bullionPricing, enabled: false },
      fmcgFacet: {
        allergens: [],
        shelfLifeDays: 30,
        isVeg: true,
        fssaiNumber: "1234567890123", // 13 digits (invalid)
      },
    };

    const validation = validateMerchantCatalogForm(invalidFssaiForm);
    assert.equal(validation.isValid, false);
    assert.ok(validation.errors.fmcgFssai);

    const alphaFssaiForm: MerchantCatalogFormData = {
      ...invalidFssaiForm,
      fmcgFacet: {
        ...invalidFssaiForm.fmcgFacet,
        fssaiNumber: "1001201100012A", // 14 chars but contains alphabet
      },
    };

    const alphaValidation = validateMerchantCatalogForm(alphaFssaiForm);
    assert.equal(alphaValidation.isValid, false);
    assert.ok(alphaValidation.errors.fmcgFssai);
  });

  it("should sanitize Apparel facet and filter empty fabric strings", () => {
    const apparelForm: MerchantCatalogFormData = {
      ...baseValidTestForm,
      skuId: "SKU-TSHIRT-001",
      category: "Apparel",
      selectedFacet: "apparel",
      bullionPricing: { ...defaultCatalogFormState.bullionPricing, enabled: false },
      apparelFacet: {
        size: "  M  ",
        color: "  Black  ",
        fabric: ["Cotton", "  ", "", "Polyester"],
        fitType: "Regular",
        gender: "UNISEX",
      },
    };

    const payload = buildUniversalProductPayload(apparelForm);
    assert.ok(payload.apparelFacet);
    assert.equal(payload.apparelFacet.size, "M");
    assert.equal(payload.apparelFacet.color, "Black");
    assert.deepEqual(payload.apparelFacet.fabric, ["Cotton", "Polyester"]);
    assert.equal(payload.apparelFacet.gender, "UNISEX");
  });
});
