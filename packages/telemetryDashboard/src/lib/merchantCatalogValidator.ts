import {
  defaultGstRatePercent,
  hsnGstLookupTable,
  maxDiscountBps,
  maxPromotionDiscountBps,
  maxQuoteTtlSeconds,
  minPromotionDiscountBps,
  minPromotionWindowSeconds,
  minQuoteTtlSeconds,
  minVolumeQuantity,
  paisePerInrUnit,
} from "@/constants/merchantCatalogConstants";
import {
  DynamicPricingRulePayload,
  FormValidationErrors,
  FormValidationResult,
  MerchantCatalogFormData,
  ScheduledPromotionInput,
  ScheduledPromotionPayload,
  UniversalProductListingPayload,
} from "@/types/merchantCatalogTypes";

const skuRegex = /^[A-Za-z0-9_-]{3,64}$/;
const hsnRegex = /^[0-9]{4,8}$/;
const pincodeRegex = /^[1-9][0-9]{5}$/;
const fssaiRegex = /^[0-9]{14}$/;

export function convertInrToPaise(rupees: number | string | undefined | null): number {
  if (rupees === undefined || rupees === null) {
    return 0;
  }
  if (typeof rupees === "string") {
    const trimmed = rupees.trim();
    if (!trimmed || isNaN(Number(trimmed))) {
      return 0;
    }
    const parsed = Number(trimmed);
    return parsed <= 0 ? 0 : Math.round(parsed * paisePerInrUnit);
  }
  if (typeof rupees !== "number" || isNaN(rupees) || rupees <= 0) {
    return 0;
  }
  return Math.round(rupees * paisePerInrUnit);
}

export function formatPaiseToInr(paise: number | undefined | null): string {
  if (paise === undefined || paise === null || isNaN(paise)) {
    return "₹0.00";
  }
  const rupees = paise / paisePerInrUnit;
  return new Intl.NumberFormat("en-IN", {
    style: "currency",
    currency: "INR",
    minimumFractionDigits: 2,
    maximumFractionDigits: 2,
  }).format(rupees);
}

export function resolveGstFromHsn(hsnCode: string): number {
  const digitsOnly = (hsnCode || "").replace(/\D/g, "");
  if (!digitsOnly) {
    return defaultGstRatePercent;
  }
  const prefixes = [
    digitsOnly.slice(0, 8),
    digitsOnly.slice(0, 6),
    digitsOnly.slice(0, 4),
    digitsOnly.slice(0, 2),
  ];
  for (const prefix of prefixes) {
    if (prefix && prefix in hsnGstLookupTable) {
      return hsnGstLookupTable[prefix];
    }
  }
  return defaultGstRatePercent;
}

function buildDynamicPricingPayload(
  formData: MerchantCatalogFormData
): DynamicPricingRulePayload | undefined {
  if (!formData.bullionPricing.enabled) {
    return undefined;
  }
  return {
    pricingType: "FORMULA_SPOT_LINKED",
    oracleFeedSymbol: formData.bullionPricing.oracleFeedSymbol,
    purityMultiplier: formData.bullionPricing.purityMultiplier.toString(),
    netWeightGrams: formData.bullionPricing.netWeightGrams.toString(),
    makingChargesPaise: convertInrToPaise(formData.bullionPricing.makingChargesInr),
    makingChargesType: formData.bullionPricing.makingChargesType,
    stoneChargesPaise: convertInrToPaise(formData.bullionPricing.stoneChargesInr),
    maxQuoteTtlSeconds: formData.bullionPricing.maxQuoteTtlSeconds,
  };
}

export function buildUniversalProductPayload(
  formData: MerchantCatalogFormData
): UniversalProductListingPayload {
  const basePaise = convertInrToPaise(formData.basePriceInr);
  const dynamicPricingRule = buildDynamicPricingPayload(formData);

  const payload: UniversalProductListingPayload = {
    skuId: formData.skuId.trim(),
    merchantDid: formData.merchantDid.trim(),
    title: formData.title.trim(),
    description: formData.description.trim(),
    category: formData.category.trim(),
    hsnCode: formData.hsnCode.trim(),
    gstRatePercent: Number(formData.gstRatePercent),
    baseUnitPricePaise: basePaise,
    availableStock: Number(formData.availableStock),
    originPincode: formData.originPincode.trim(),
    currency: "INR",
    minimumOrderQuantity: Number(formData.minimumOrderQuantity),
    volumeTiers: formData.volumeTiers.map((tier) => ({
      minQuantity: Number(tier.minQuantity),
      discountBps: Number(tier.discountBps),
    })),
    // Omitted when empty. The backend model is extra="forbid" and `promotions` is optional, so
    // an empty array is accepted but says something the merchant did not: that they considered
    // promotions and chose none, rather than never touching the section.
    ...(formData.promotions.length > 0 && {
      promotions: formData.promotions.map(buildScheduledPromotionPayload),
    }),
    ...(formData.selectedFacet === "jewelry" && {
      jewelryFacet: {
        purityCarat: formData.jewelryFacet.purityCarat,
        grossWeightGrams: formData.jewelryFacet.grossWeightGrams.toString(),
        hallmarkNumber: formData.jewelryFacet.hallmarkNumber.trim(),
        ...(dynamicPricingRule && { dynamicPricingRule }),
      },
    }),
    ...(formData.selectedFacet === "apparel" && {
      apparelFacet: {
        size: formData.apparelFacet.size.trim(),
        color: formData.apparelFacet.color.trim(),
        fabric: formData.apparelFacet.fabric.filter((fab) => fab.trim().length > 0),
        fitType: formData.apparelFacet.fitType.trim(),
        gender: formData.apparelFacet.gender,
      },
    }),
    ...(formData.selectedFacet === "pharma" && {
      pharmaFacet: {
        activeSalt: formData.pharmaFacet.activeSalt.trim(),
        dosageMg: Number(formData.pharmaFacet.dosageMg),
        schedule: formData.pharmaFacet.schedule.trim(),
        prescriptionRequired: Boolean(formData.pharmaFacet.prescriptionRequired),
      },
    }),
    ...(formData.selectedFacet === "fmcg" && {
      fmcgFacet: {
        allergens: formData.fmcgFacet.allergens.filter((alg) => alg.trim().length > 0),
        shelfLifeDays: Number(formData.fmcgFacet.shelfLifeDays),
        isVeg: Boolean(formData.fmcgFacet.isVeg),
        fssaiNumber: formData.fmcgFacet.fssaiNumber.trim(),
      },
    }),
  };

  return payload;
}

function validateBasicMetadata(
  formData: MerchantCatalogFormData,
  errors: FormValidationErrors
): void {
  if (!formData.skuId || !skuRegex.test(formData.skuId.trim())) {
    errors.skuId = "SKU ID must be 3-64 alphanumeric characters, underscores or hyphens.";
  }
  if (!formData.title || formData.title.trim().length < 3 || formData.title.length > 150) {
    errors.title = "Title must be between 3 and 150 characters.";
  }
  if (!formData.description || formData.description.trim().length < 5 || formData.description.length > 500) {
    errors.description = "Description must be between 5 and 500 characters.";
  }
  if (!formData.hsnCode || !hsnRegex.test(formData.hsnCode.trim())) {
    errors.hsnCode = "HSN Code must be 4 to 8 digits.";
  }
  if (formData.gstRatePercent < 0 || formData.gstRatePercent > 28) {
    errors.gstRatePercent = "GST Rate must be between 0% and 28%.";
  }
}

function validatePricingAndStock(
  formData: MerchantCatalogFormData,
  errors: FormValidationErrors
): void {
  const paise = convertInrToPaise(formData.basePriceInr);
  if (!formData.bullionPricing.enabled && paise <= 0) {
    errors.basePriceInr = "Base price in INR must be greater than 0.";
  }
  if (formData.availableStock < 0 || !Number.isInteger(Number(formData.availableStock))) {
    errors.availableStock = "Available stock must be a non-negative integer.";
  }
  if (!formData.originPincode || !pincodeRegex.test(formData.originPincode.trim())) {
    errors.originPincode = "Origin pincode must be a 6-digit Indian PIN code.";
  }
  if (formData.minimumOrderQuantity < 1) {
    errors.minimumOrderQuantity = "Minimum Order Quantity must be at least 1.";
  }
}

function validateVolumeTiers(
  formData: MerchantCatalogFormData,
  errors: FormValidationErrors
): void {
  formData.volumeTiers.forEach((tier, idx) => {
    if (tier.minQuantity < minVolumeQuantity) {
      errors[`volumeTier_${idx}_qty`] = `Tier ${idx + 1}: Minimum quantity must be >= 1.`;
    }
    if (tier.discountBps < 0 || tier.discountBps > maxDiscountBps) {
      errors[`volumeTier_${idx}_bps`] = `Tier ${idx + 1}: Discount must be between 0 and 10,000 BPS.`;
    }
  });
}

/**
 * Mirrors ScheduledPromotionSchema's own validatePromotionInvariants
 * (merchantApi/src/schemas/universalProductSchema.py). Enforced here so the merchant sees which
 * field is wrong, rather than a pydantic 422 relayed as an opaque publish failure.
 */
function validatePromotions(
  formData: MerchantCatalogFormData,
  errors: FormValidationErrors
): void {
  formData.promotions.forEach((promotion, idx) => {
    const label = `Promotion ${idx + 1}`;
    if (!promotion.campaignId.trim()) {
      errors[`promotion_${idx}_campaignId`] = `${label}: Campaign ID is required.`;
    }
    if (!promotion.name.trim()) {
      errors[`promotion_${idx}_name`] = `${label}: Display name is required.`;
    }
    if (promotion.startsAtUnix <= 0) {
      errors[`promotion_${idx}_startsAt`] = `${label}: Start time is required.`;
    }
    if (promotion.endsAtUnix <= 0) {
      errors[`promotion_${idx}_endsAt`] = `${label}: End time is required.`;
    }
    // The backend requires only that the window is non-empty. The form is stricter: a sale too
    // short to act on is advertised to buyer agents that then cannot reach it in time.
    if (
      promotion.startsAtUnix > 0 &&
      promotion.endsAtUnix > 0 &&
      promotion.endsAtUnix - promotion.startsAtUnix < minPromotionWindowSeconds
    ) {
      errors[`promotion_${idx}_endsAt`] =
        `${label}: The sale must run for at least ${minPromotionWindowSeconds / 60} minutes after it starts.`;
    }
    validatePromotionDiscount(promotion, idx, label, errors);
  });
}

function validatePromotionDiscount(
  promotion: ScheduledPromotionInput,
  idx: number,
  label: string,
  errors: FormValidationErrors
): void {
  const key = `promotion_${idx}_discount`;
  if (promotion.discountKind === "PERCENT") {
    if (
      promotion.discountBps < minPromotionDiscountBps ||
      promotion.discountBps > maxPromotionDiscountBps
    ) {
      errors[key] = `${label}: Discount must be between ${minPromotionDiscountBps} and ${maxPromotionDiscountBps} BPS.`;
    }
    return;
  }
  // convertInrToPaise returns 0 for anything unparseable or non-positive, so this one check
  // covers a blank field, a negative and "abc" alike -- and the schema rejects all three.
  const amountPaise = convertInrToPaise(
    promotion.discountKind === "FLAT_OFF" ? promotion.discountInr : promotion.fixedPriceInr
  );
  if (amountPaise <= 0) {
    errors[key] =
      promotion.discountKind === "FLAT_OFF"
        ? `${label}: Enter the rupee amount to take off.`
        : `${label}: Enter the fixed sale price in rupees.`;
  }
}

/**
 * Emits exactly one of the three discount fields.
 *
 * ScheduledPromotionSchema requires at least one and forbids unknown keys, so sending all three
 * with two zeroed would both over-specify the promotion and, for a zero discountBps, fail the
 * schema's own ge= bound. `limitedStockAllocated` is dropped at 0, which the form uses to mean
 * unlimited -- the backend spells that as an absent field, not a zero.
 */
export function buildScheduledPromotionPayload(
  promotion: ScheduledPromotionInput
): ScheduledPromotionPayload {
  return {
    campaignId: promotion.campaignId.trim(),
    name: promotion.name.trim(),
    startsAtUnix: Number(promotion.startsAtUnix),
    endsAtUnix: Number(promotion.endsAtUnix),
    ...(promotion.discountKind === "PERCENT" && { discountBps: Number(promotion.discountBps) }),
    ...(promotion.discountKind === "FLAT_OFF" && {
      discountPaise: convertInrToPaise(promotion.discountInr),
    }),
    ...(promotion.discountKind === "FIXED_PRICE" && {
      fixedPricePaise: convertInrToPaise(promotion.fixedPriceInr),
    }),
    ...(promotion.limitedStockAllocated > 0 && {
      limitedStockAllocated: Number(promotion.limitedStockAllocated),
    }),
  };
}

function validateFacets(
  formData: MerchantCatalogFormData,
  errors: FormValidationErrors
): void {
  if (formData.bullionPricing.enabled) {
    if (formData.bullionPricing.netWeightGrams <= 0) {
      errors.bullionNetWeight = "Net weight must be greater than 0 grams.";
    }
    if (
      formData.bullionPricing.maxQuoteTtlSeconds < minQuoteTtlSeconds ||
      formData.bullionPricing.maxQuoteTtlSeconds > maxQuoteTtlSeconds
    ) {
      errors.bullionTtl = `Quote TTL must be between ${minQuoteTtlSeconds}s and ${maxQuoteTtlSeconds}s.`;
    }
  }

  if (formData.selectedFacet === "jewelry") {
    if (formData.jewelryFacet.grossWeightGrams <= 0) {
      errors.jewelryGrossWeight = "Jewelry gross weight must be greater than 0g.";
    }
    if (!formData.jewelryFacet.hallmarkNumber.trim()) {
      errors.jewelryHallmark = "Hallmark certificate number is required.";
    }
  } else if (formData.selectedFacet === "pharma") {
    if (!formData.pharmaFacet.activeSalt.trim()) {
      errors.pharmaSalt = "Active pharmaceutical salt name is required.";
    }
  } else if (formData.selectedFacet === "fmcg") {
    if (formData.fmcgFacet.shelfLifeDays < 1) {
      errors.fmcgShelfLife = "Shelf life must be at least 1 day.";
    }
    if (formData.fmcgFacet.fssaiNumber && !fssaiRegex.test(formData.fmcgFacet.fssaiNumber.trim())) {
      errors.fmcgFssai = "FSSAI license number must be exactly 14 digits.";
    }
  }
}

export function validateMerchantCatalogForm(formData: MerchantCatalogFormData): FormValidationResult {
  const errors: FormValidationErrors = {};
  validateBasicMetadata(formData, errors);
  validatePricingAndStock(formData, errors);
  validateVolumeTiers(formData, errors);
  validatePromotions(formData, errors);
  validateFacets(formData, errors);

  return {
    isValid: Object.keys(errors).length === 0,
    errors,
  };
}
