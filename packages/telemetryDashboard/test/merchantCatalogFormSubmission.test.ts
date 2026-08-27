import { describe, it } from "node:test";
import assert from "node:assert/strict";

import { defaultCatalogFormState } from "../src/constants/merchantCatalogConstants.js";
import { buildUniversalProductPayload } from "../src/lib/merchantCatalogValidator.js";
import { MerchantCatalogFormData, VolumeTierInput } from "../src/types/merchantCatalogTypes.js";

describe("Merchant SKU Studio Submission — TC-UI-12 to TC-UI-15: Dynamic Volume Tiers Serialization", () => {
  it("should correctly serialize single and multi-tier volume discounts in payload", () => {
    const customTiers: VolumeTierInput[] = [
      { minQuantity: 5, discountBps: 250 },
      { minQuantity: 20, discountBps: 500 },
      { minQuantity: 50, discountBps: 1000 },
    ];
    const formWithTiers: MerchantCatalogFormData = {
      ...defaultCatalogFormState,
      volumeTiers: customTiers,
    };

    const payload = buildUniversalProductPayload(formWithTiers);
    assert.equal(payload.volumeTiers.length, 3);
    assert.equal(payload.volumeTiers[0].minQuantity, 5);
    assert.equal(payload.volumeTiers[0].discountBps, 250);
    assert.equal(payload.volumeTiers[1].minQuantity, 20);
    assert.equal(payload.volumeTiers[1].discountBps, 500);
    assert.equal(payload.volumeTiers[2].minQuantity, 50);
    assert.equal(payload.volumeTiers[2].discountBps, 1000);
  });
});

describe("Merchant SKU Studio Submission — TC-UI-16 to TC-UI-19: Bullion Formula Dynamic Pricing", () => {
  it("should serialize formula spot-linked dynamic pricing rule when bullion pricing is enabled", () => {
    const goldForm: MerchantCatalogFormData = {
      ...defaultCatalogFormState,
      selectedFacet: "jewelry",
      bullionPricing: {
        enabled: true,
        oracleFeedSymbol: "MCX_GOLD_24K_INR_PER_GRAM",
        purityMultiplier: 1.0,
        netWeightGrams: 10.5,
        makingChargesInr: "2500.00",
        makingChargesType: "FIXED_PAISE",
        stoneChargesInr: "500.00",
        maxQuoteTtlSeconds: 60,
      },
    };

    const payload = buildUniversalProductPayload(goldForm);
    assert.ok(payload.jewelryFacet);
    assert.ok(payload.jewelryFacet.dynamicPricingRule);
    assert.equal(payload.jewelryFacet.dynamicPricingRule.pricingType, "FORMULA_SPOT_LINKED");
    assert.equal(payload.jewelryFacet.dynamicPricingRule.oracleFeedSymbol, "MCX_GOLD_24K_INR_PER_GRAM");
    assert.equal(payload.jewelryFacet.dynamicPricingRule.purityMultiplier, "1");
    assert.equal(payload.jewelryFacet.dynamicPricingRule.netWeightGrams, "10.5");
    assert.equal(payload.jewelryFacet.dynamicPricingRule.makingChargesPaise, 250000);
    assert.equal(payload.jewelryFacet.dynamicPricingRule.stoneChargesPaise, 50000);
    assert.equal(payload.jewelryFacet.dynamicPricingRule.maxQuoteTtlSeconds, 60);
  });

  it("should omit dynamic pricing rule when bullion pricing is disabled", () => {
    const disabledForm: MerchantCatalogFormData = {
      ...defaultCatalogFormState,
      selectedFacet: "jewelry",
      bullionPricing: {
        ...defaultCatalogFormState.bullionPricing,
        enabled: false,
      },
    };

    const payload = buildUniversalProductPayload(disabledForm);
    assert.ok(payload.jewelryFacet);
    assert.equal(payload.jewelryFacet.dynamicPricingRule, undefined);
  });
});

describe("Merchant SKU Studio Submission — TC-UI-20 to TC-UI-23: Vertical Domain Facet Serialization", () => {
  it("should serialize Apparel domain facet with size, color, fabric, and gender", () => {
    const apparelForm: MerchantCatalogFormData = {
      ...defaultCatalogFormState,
      skuId: "SKU-APP-001",
      category: "Apparel",
      hsnCode: "61091000",
      selectedFacet: "apparel",
      bullionPricing: { ...defaultCatalogFormState.bullionPricing, enabled: false },
      apparelFacet: {
        size: "XL",
        color: "Midnight Blue",
        fabric: ["100% Organic Cotton", "Linen"],
        fitType: "Slim Fit",
        gender: "M",
      },
    };

    const payload = buildUniversalProductPayload(apparelForm);
    assert.equal("selectedFacet" in payload, false);
    assert.ok(payload.apparelFacet);
    assert.equal(payload.apparelFacet.size, "XL");
    assert.equal(payload.apparelFacet.color, "Midnight Blue");
    assert.deepEqual(payload.apparelFacet.fabric, ["100% Organic Cotton", "Linen"]);
    assert.equal(payload.apparelFacet.gender, "M");
    assert.equal(payload.jewelryFacet, undefined);
    assert.equal(payload.pharmaFacet, undefined);
    assert.equal(payload.fmcgFacet, undefined);
  });

  it("should serialize Pharma domain facet with active molecule, dosage, and schedule", () => {
    const pharmaForm: MerchantCatalogFormData = {
      ...defaultCatalogFormState,
      skuId: "SKU-PHARMA-001",
      category: "Pharma",
      hsnCode: "30049099",
      selectedFacet: "pharma",
      bullionPricing: { ...defaultCatalogFormState.bullionPricing, enabled: false },
      pharmaFacet: {
        activeSalt: "Amoxicillin Trihydrate",
        dosageMg: 500,
        schedule: "Schedule H",
        prescriptionRequired: true,
      },
    };

    const payload = buildUniversalProductPayload(pharmaForm);
    assert.ok(payload.pharmaFacet);
    assert.equal(payload.pharmaFacet.activeSalt, "Amoxicillin Trihydrate");
    assert.equal(payload.pharmaFacet.dosageMg, 500);
    assert.equal(payload.pharmaFacet.schedule, "Schedule H");
    assert.equal(payload.pharmaFacet.prescriptionRequired, true);
    assert.equal(payload.jewelryFacet, undefined);
  });

  it("should serialize FMCG domain facet with allergens, shelf life, and FSSAI license", () => {
    const fmcgForm: MerchantCatalogFormData = {
      ...defaultCatalogFormState,
      skuId: "SKU-FMCG-001",
      category: "FMCG",
      hsnCode: "21069099",
      selectedFacet: "fmcg",
      bullionPricing: { ...defaultCatalogFormState.bullionPricing, enabled: false },
      fmcgFacet: {
        allergens: ["Tree Nuts", "Soy"],
        shelfLifeDays: 90,
        isVeg: true,
        fssaiNumber: "10012011000123",
      },
    };

    const payload = buildUniversalProductPayload(fmcgForm);
    assert.ok(payload.fmcgFacet);
    assert.deepEqual(payload.fmcgFacet.allergens, ["Tree Nuts", "Soy"]);
    assert.equal(payload.fmcgFacet.shelfLifeDays, 90);
    assert.equal(payload.fmcgFacet.isVeg, true);
    assert.equal(payload.fmcgFacet.fssaiNumber, "10012011000123");
    assert.equal(payload.jewelryFacet, undefined);
  });

  it("should omit domain facets when selectedFacet is 'none'", () => {
    const noneForm: MerchantCatalogFormData = {
      ...defaultCatalogFormState,
      selectedFacet: "none",
      bullionPricing: { ...defaultCatalogFormState.bullionPricing, enabled: false },
    };

    const payload = buildUniversalProductPayload(noneForm);
    assert.equal(payload.jewelryFacet, undefined);
    assert.equal(payload.apparelFacet, undefined);
    assert.equal(payload.pharmaFacet, undefined);
    assert.equal(payload.fmcgFacet, undefined);
  });
});

describe("Merchant SKU Studio Submission — TC-UI-24 to TC-UI-30: RFC 8259 JSON Invariants", () => {
  it("should produce valid JSON string matching RFC 8259 without float drift", () => {
    const payload = buildUniversalProductPayload(defaultCatalogFormState);
    const jsonString = JSON.stringify(payload);
    assert.ok(jsonString.length > 50);

    const parsed = JSON.parse(jsonString);
    assert.equal(parsed.skuId, defaultCatalogFormState.skuId);
    assert.equal(typeof parsed.baseUnitPricePaise, "number");
    assert.equal(Number.isInteger(parsed.baseUnitPricePaise), true);
  });
});
