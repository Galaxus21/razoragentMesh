import {
  bpsDivisor,
  percentDivisor,
  halfGstDivisor,
  discountTypeVolumeTier,
  discountTypeCampaign,
  discountTypePaymentRail,
  discountTypePromoCode,
  festiveCampaignBps,
  festiveCampaignCapPaise,
  upiCashbackPaise,
  corporatePromoCode,
  corporatePromoBps
} from "../constants/protocolConstants.js";
import {
  VolumeTier,
  TaxBreakdown,
  ArithmeticDriftException,
  AppliedDiscountItem,
  DiscountStackResult
} from "../types/mcpToolTypes.js";

export type { AppliedDiscountItem, DiscountStackResult };

export interface PricingResult {
  readonly baseUnitPricePaise: number;
  readonly offeredUnitPricePaise: number;
  readonly discountBps: number;
  readonly unitDiscountPaise: number;
  readonly totalBasePaise: number;
  readonly totalOfferedPaise: number;
}

export const zeroPaise = 0;
export const zeroBps = 0;

export function assertIntegerPaise(
  amount: unknown,
  fieldName: string
): asserts amount is number {
  if (typeof amount !== "number" || !Number.isInteger(amount)) {
    throw new ArithmeticDriftException(
      `Float math drift detected in ${fieldName}: received ${String(amount)}, expected strict integer paise`
    );
  }
}

export function findMatchingVolumeTier(
  quantity: number,
  tiers: readonly VolumeTier[]
): VolumeTier | undefined {
  const sortedTiers = [...tiers].sort(
    (tierA, tierB) => tierB.minQuantity - tierA.minQuantity
  );

  return sortedTiers.find((tier) => quantity >= tier.minQuantity);
}

export function calculateVolumePricing(
  baseUnitPricePaise: number,
  quantity: number,
  tiers: readonly VolumeTier[] = []
): PricingResult {
  assertIntegerPaise(baseUnitPricePaise, "baseUnitPricePaise");
  assertIntegerPaise(quantity, "quantity");

  if (baseUnitPricePaise < zeroPaise || quantity < 1) {
    throw new ArithmeticDriftException(
      `Invalid base price ${baseUnitPricePaise} or quantity ${quantity}`
    );
  }

  const matchingTier = findMatchingVolumeTier(quantity, tiers);
  const discountBps = matchingTier ? matchingTier.discountBps : zeroBps;
  const unitDiscountPaise = Math.floor(
    (baseUnitPricePaise * discountBps) / bpsDivisor
  );
  const offeredUnitPricePaise = baseUnitPricePaise - unitDiscountPaise;
  const totalBasePaise = baseUnitPricePaise * quantity;
  const totalOfferedPaise = offeredUnitPricePaise * quantity;

  return {
    baseUnitPricePaise,
    offeredUnitPricePaise,
    discountBps,
    unitDiscountPaise,
    totalBasePaise,
    totalOfferedPaise
  };
}

export function calculateGstBreakdown(
  taxableAmountPaise: number,
  gstRatePercent: number,
  merchantState: string,
  buyerState: string
): TaxBreakdown {
  assertIntegerPaise(taxableAmountPaise, "taxableAmountPaise");

  if (taxableAmountPaise < zeroPaise) {
    throw new ArithmeticDriftException(
      `Taxable amount cannot be negative: received ${taxableAmountPaise}`
    );
  }

  const isIntraState =
    merchantState.trim().toUpperCase() === buyerState.trim().toUpperCase();

  if (isIntraState) {
    const halfRateBps = Math.floor(
      (gstRatePercent * percentDivisor) / halfGstDivisor
    );
    const cgstPaise = Math.floor((taxableAmountPaise * halfRateBps) / bpsDivisor);
    const sgstPaise = Math.floor((taxableAmountPaise * halfRateBps) / bpsDivisor);

    return {
      cgstPaise,
      sgstPaise,
      igstPaise: zeroPaise,
      totalTaxPaise: cgstPaise + sgstPaise
    };
  }

  const rateBps = Math.floor(gstRatePercent * percentDivisor);
  const igstPaise = Math.floor((taxableAmountPaise * rateBps) / bpsDivisor);

  return {
    cgstPaise: zeroPaise,
    sgstPaise: zeroPaise,
    igstPaise,
    totalTaxPaise: igstPaise
  };
}

function applyVolumeTierDiscountStep(
  unitPricePaise: number,
  quantity: number,
  tiers: readonly VolumeTier[],
  appliedDiscounts: AppliedDiscountItem[]
): number {
  const matchingTier = findMatchingVolumeTier(quantity, tiers);
  if (!matchingTier || matchingTier.discountBps <= zeroBps) {
    return unitPricePaise;
  }
  const discountPaise = Math.floor((unitPricePaise * matchingTier.discountBps) / bpsDivisor);
  if (discountPaise <= zeroPaise) {
    return unitPricePaise;
  }
  appliedDiscounts.push({
    type: discountTypeVolumeTier,
    label: `Volume Tier Discount (${matchingTier.discountBps / 100}%)`,
    discountBps: matchingTier.discountBps,
    discountPaise
  });
  return unitPricePaise - discountPaise;
}

function applyCampaignDiscountStep(
  unitPricePaise: number,
  appliedDiscounts: AppliedDiscountItem[]
): number {
  const uncappedPaise = Math.floor((unitPricePaise * festiveCampaignBps) / bpsDivisor);
  const discountPaise = Math.min(festiveCampaignCapPaise, uncappedPaise);
  if (discountPaise <= zeroPaise) {
    return unitPricePaise;
  }
  appliedDiscounts.push({
    type: discountTypeCampaign,
    label: `Festive Campaign (${festiveCampaignBps / 100}% off capped at ₹${festiveCampaignCapPaise / 100})`,
    discountBps: festiveCampaignBps,
    discountPaise
  });
  return unitPricePaise - discountPaise;
}

function applyPaymentRailDiscountStep(
  unitPricePaise: number,
  appliedDiscounts: AppliedDiscountItem[]
): number {
  const discountPaise = Math.min(unitPricePaise, upiCashbackPaise);
  if (discountPaise <= zeroPaise) {
    return unitPricePaise;
  }
  appliedDiscounts.push({
    type: discountTypePaymentRail,
    label: `UPI Instant Cashback (₹${(upiCashbackPaise / 100).toFixed(2)})`,
    discountPaise
  });
  return unitPricePaise - discountPaise;
}

function applyPromoCodeDiscountStep(
  unitPricePaise: number,
  promoCode: string | undefined,
  appliedDiscounts: AppliedDiscountItem[]
): number {
  if (!promoCode || promoCode.trim().toUpperCase() !== corporatePromoCode) {
    return unitPricePaise;
  }
  const discountPaise = Math.floor((unitPricePaise * corporatePromoBps) / bpsDivisor);
  if (discountPaise <= zeroPaise) {
    return unitPricePaise;
  }
  appliedDiscounts.push({
    type: discountTypePromoCode,
    label: `Corporate Promo Code (${corporatePromoBps / 100}% off)`,
    discountBps: corporatePromoBps,
    discountPaise
  });
  return unitPricePaise - discountPaise;
}

export function computeAutoDiscountStack(
  baseUnitPricePaise: number,
  quantity: number,
  volumeTiers: readonly VolumeTier[],
  promoCode?: string
): DiscountStackResult {
  assertIntegerPaise(baseUnitPricePaise, "baseUnitPricePaise");
  assertIntegerPaise(quantity, "quantity");

  if (baseUnitPricePaise < zeroPaise || quantity < 1) {
    throw new ArithmeticDriftException(
      `Invalid base price ${baseUnitPricePaise} or quantity ${quantity}`
    );
  }

  const appliedDiscounts: AppliedDiscountItem[] = [];
  let currentPrice = applyVolumeTierDiscountStep(baseUnitPricePaise, quantity, volumeTiers, appliedDiscounts);
  currentPrice = applyCampaignDiscountStep(currentPrice, appliedDiscounts);
  currentPrice = applyPaymentRailDiscountStep(currentPrice, appliedDiscounts);
  currentPrice = applyPromoCodeDiscountStep(currentPrice, promoCode, appliedDiscounts);

  const offeredUnitPricePaise = Math.max(zeroPaise, currentPrice);
  const totalSavingsPaise = (baseUnitPricePaise - offeredUnitPricePaise) * quantity;

  return {
    offeredUnitPricePaise,
    appliedDiscounts,
    totalSavingsPaise
  };
}
