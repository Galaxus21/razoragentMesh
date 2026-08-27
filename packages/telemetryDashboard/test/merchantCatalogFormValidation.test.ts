import { describe, it } from "node:test";
import assert from "node:assert/strict";

import {
  categoryOptions,
  defaultCatalogFormState,
  defaultGstRatePercent,
  defaultMinOrderQuantity,
  gstRateOptions,
  hsnPresetOptions,
  metalPurityChoices,
  oracleFeedOptions,
} from "../src/constants/merchantCatalogConstants.js";
import {
  convertInrToPaise,
  formatPaiseToInr,
  resolveGstFromHsn,
  validateMerchantCatalogForm,
} from "../src/lib/merchantCatalogValidator.js";
import { MerchantCatalogFormData } from "../src/types/merchantCatalogTypes.js";

describe("Merchant SKU Studio Validation — TC-UI-01 to TC-UI-03: Default State & Metadata Bounds", () => {
  it("should initialize default form state with clean blank baseline schema constants", () => {
    assert.equal(defaultCatalogFormState.skuId, "");
    assert.equal(defaultCatalogFormState.merchantDid, "");
    assert.equal(defaultCatalogFormState.originPincode, "");
    assert.equal(defaultCatalogFormState.minimumOrderQuantity, defaultMinOrderQuantity);
    assert.equal(defaultCatalogFormState.currency, "INR");
    assert.equal(defaultCatalogFormState.category, "General");
    assert.equal(defaultCatalogFormState.gstRatePercent, defaultGstRatePercent);
    assert.equal(defaultCatalogFormState.volumeTiers.length, 0);
    assert.equal(defaultCatalogFormState.bullionPricing.enabled, false);
  });

  it("should provide complete lookup constants and statutory preset collections", () => {
    assert.ok(categoryOptions.includes("Jewelry"));
    assert.ok(categoryOptions.includes("Apparel"));
    assert.ok(categoryOptions.includes("Pharma"));
    assert.ok(categoryOptions.includes("FMCG"));
    assert.ok(categoryOptions.includes("Electronics"));

    assert.deepEqual(gstRateOptions, [0, 3, 5, 12, 18, 28]);
    assert.equal(oracleFeedOptions.length, 3);
    assert.equal(metalPurityChoices.length, 3);
    assert.ok(hsnPresetOptions.length >= 8);
  });
});

describe("Merchant SKU Studio Validation — TC-UI-04 to TC-UI-07: INR to Integer Paise Conversion", () => {
  it("should convert standard integer and decimal Rupee inputs accurately to paise", () => {
    assert.equal(convertInrToPaise(4200), 420000);
    assert.equal(convertInrToPaise("4200"), 420000);
    assert.equal(convertInrToPaise("42.50"), 4250);
    assert.equal(convertInrToPaise("199.99"), 19999);
    assert.equal(convertInrToPaise("0.05"), 5);
    assert.equal(convertInrToPaise("150000"), 15000000);
  });

  it("should defensively handle empty, negative, invalid, or non-numeric price inputs", () => {
    assert.equal(convertInrToPaise(""), 0);
    assert.equal(convertInrToPaise("   "), 0);
    assert.equal(convertInrToPaise("-50"), 0);
    assert.equal(convertInrToPaise(-100), 0);
    assert.equal(convertInrToPaise("invalid_text"), 0);
    assert.equal(convertInrToPaise(null), 0);
    assert.equal(convertInrToPaise(undefined), 0);
    assert.equal(convertInrToPaise(NaN), 0);
  });

  it("should format integer paise to locale currency strings via formatPaiseToInr", () => {
    const formatted = formatPaiseToInr(420000);
    assert.ok(formatted.includes("4,200.00"));
    assert.equal(formatPaiseToInr(0), "₹0.00");
    assert.equal(formatPaiseToInr(undefined), "₹0.00");
    assert.equal(formatPaiseToInr(null), "₹0.00");
  });
});

describe("Merchant SKU Studio Validation — TC-UI-08 to TC-UI-11: HSN Statutory GST Resolution", () => {
  it("should resolve statutory GST rates for jewelry HSN codes (3% GST)", () => {
    assert.equal(resolveGstFromHsn("71131910"), 3);
    assert.equal(resolveGstFromHsn("71131120"), 3);
    assert.equal(resolveGstFromHsn("71141900"), 3);
    assert.equal(resolveGstFromHsn("71189000"), 3);
  });

  it("should resolve statutory GST rates for apparel and pharma HSN codes", () => {
    assert.equal(resolveGstFromHsn("61091000"), 5);
    assert.equal(resolveGstFromHsn("62034200"), 12);
    assert.equal(resolveGstFromHsn("30049099"), 12);
    assert.equal(resolveGstFromHsn("30021500"), 5);
  });

  it("should resolve statutory GST rates for FMCG, Electronics, and Books", () => {
    assert.equal(resolveGstFromHsn("04012000"), 0);
    assert.equal(resolveGstFromHsn("49011010"), 0);
    assert.equal(resolveGstFromHsn("84713010"), 18);
    assert.equal(resolveGstFromHsn("85171300"), 18);
    assert.equal(resolveGstFromHsn("21069099"), 18);
  });

  it("should fallback to default GST rate (18%) on unknown or empty HSN codes", () => {
    assert.equal(resolveGstFromHsn(""), defaultGstRatePercent);
    assert.equal(resolveGstFromHsn("99999999"), defaultGstRatePercent);
    assert.equal(resolveGstFromHsn("ABCD"), defaultGstRatePercent);
  });
});

describe("Merchant SKU Studio Validation — TC-UI-12 to TC-UI-15 & TC-UI-24 to TC-UI-30: Invariants & Error Detection", () => {
  it("should validate volume tier boundaries (minQuantity >= 1, discountBps between 0 and 10000)", () => {
    const invalidTiers: MerchantCatalogFormData = {
      ...defaultCatalogFormState,
      volumeTiers: [
        { minQuantity: 0, discountBps: 500 },
        { minQuantity: 10, discountBps: 15000 },
      ],
    };

    const validation = validateMerchantCatalogForm(invalidTiers);
    assert.equal(validation.isValid, false);
    assert.ok(validation.errors.volumeTier_0_qty);
    assert.ok(validation.errors.volumeTier_1_bps);
  });

  it("should validate bullion net weight and quote TTL boundaries", () => {
    const invalidBullionForm: MerchantCatalogFormData = {
      ...defaultCatalogFormState,
      bullionPricing: {
        ...defaultCatalogFormState.bullionPricing,
        enabled: true,
        netWeightGrams: 0,
        maxQuoteTtlSeconds: 5,
      },
    };

    const validation = validateMerchantCatalogForm(invalidBullionForm);
    assert.equal(validation.isValid, false);
    assert.ok(validation.errors.bullionNetWeight);
    assert.ok(validation.errors.bullionTtl);
  });

  it("should pass validation for a fully populated valid catalog form configuration", () => {
    const validForm: MerchantCatalogFormData = {
      ...defaultCatalogFormState,
      skuId: "SKU-TEST-001",
      merchantDid: "did:razoragent:merchant:12345",
      title: "Valid Product Title",
      description: "A valid descriptive summary of the product exceeding minimum characters.",
      hsnCode: "84713010",
      gstRatePercent: 18,
      basePriceInr: "1500.00",
      availableStock: 50,
      originPincode: "560001",
    };
    const validation = validateMerchantCatalogForm(validForm);
    assert.equal(validation.isValid, true);
    assert.deepEqual(validation.errors, {});
  });

  it("should catch and report malformed SKU ID, short title, and invalid HSN code", () => {
    const invalidForm: MerchantCatalogFormData = {
      ...defaultCatalogFormState,
      skuId: "!!",
      title: "a",
      description: "shrt",
      hsnCode: "12",
      originPincode: "12345",
    };

    const validation = validateMerchantCatalogForm(invalidForm);
    assert.equal(validation.isValid, false);
    assert.ok(validation.errors.skuId);
    assert.ok(validation.errors.title);
    assert.ok(validation.errors.description);
    assert.ok(validation.errors.hsnCode);
    assert.ok(validation.errors.originPincode);
  });

  it("should catch negative stock, zero base price (when not bullion), and invalid FMCG shelf life", () => {
    const invalidStockPriceForm: MerchantCatalogFormData = {
      ...defaultCatalogFormState,
      basePriceInr: "0.00",
      availableStock: -5,
      selectedFacet: "fmcg",
      bullionPricing: { ...defaultCatalogFormState.bullionPricing, enabled: false },
      fmcgFacet: {
        ...defaultCatalogFormState.fmcgFacet,
        shelfLifeDays: 0,
        fssaiNumber: "123",
      },
    };

    const validation = validateMerchantCatalogForm(invalidStockPriceForm);
    assert.equal(validation.isValid, false);
    assert.ok(validation.errors.basePriceInr);
    assert.ok(validation.errors.availableStock);
    assert.ok(validation.errors.fmcgShelfLife);
    assert.ok(validation.errors.fmcgFssai);
  });
});
