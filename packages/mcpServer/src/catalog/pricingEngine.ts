import {
  bpsDivisor,
  percentDivisor,
  intraStateHalfBpsDivisor,
  millisPerSecond,
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
  DiscountStackResult,
  ScheduledPromotion,
  UpcomingPromotion,
  EvaluatedPromotionsResult
} from "../types/mcpToolTypes.js";

export type {
  VolumeTier,
  TaxBreakdown,
  AppliedDiscountItem,
  DiscountStackResult,
  ScheduledPromotion,
  UpcomingPromotion,
  EvaluatedPromotionsResult
};

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

export function assertIntegerPaise(amount: unknown, fieldName: string): asserts amount is number {
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
  const sortedTiers = [...tiers].sort((tierA, tierB) => tierB.minQuantity - tierA.minQuantity);
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
    throw new ArithmeticDriftException(`Invalid base price ${baseUnitPricePaise} or quantity ${quantity}`);
  }

  const matchingTier = findMatchingVolumeTier(quantity, tiers);
  const discountBps = matchingTier ? matchingTier.discountBps : zeroBps;
  const unitDiscountPaise = Math.floor((baseUnitPricePaise * discountBps) / bpsDivisor);
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
    throw new ArithmeticDriftException(`Taxable amount cannot be negative: received ${taxableAmountPaise}`);
  }
  const isIntraState = merchantState.trim().toUpperCase() === buyerState.trim().toUpperCase();
  if (isIntraState) {
    const rateBps = gstRatePercent * percentDivisor;
    // CGST and SGST are the same levy at half the combined rate, computed with the
    // same expression, so they are equal by construction rather than by coincidence.
    const cgstPaise = Math.floor((taxableAmountPaise * rateBps) / intraStateHalfBpsDivisor);
    const sgstPaise = cgstPaise;
    return { cgstPaise, sgstPaise, igstPaise: zeroPaise, totalTaxPaise: cgstPaise + sgstPaise };
  }
  const rateBps = Math.floor(gstRatePercent * percentDivisor);
  const igstPaise = Math.floor((taxableAmountPaise * rateBps) / bpsDivisor);
  return { cgstPaise: zeroPaise, sgstPaise: zeroPaise, igstPaise, totalTaxPaise: igstPaise };
}

function applyVolumeTierDiscountStep(
  unitPricePaise: number,
  quantity: number,
  tiers: readonly VolumeTier[],
  appliedDiscounts: AppliedDiscountItem[]
): number {
  const matchingTier = findMatchingVolumeTier(quantity, tiers);
  if (!matchingTier || matchingTier.discountBps <= zeroBps) return unitPricePaise;
  const discountPaise = Math.floor((unitPricePaise * matchingTier.discountBps) / bpsDivisor);
  if (discountPaise <= zeroPaise) return unitPricePaise;
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
  if (discountPaise <= zeroPaise) return unitPricePaise;
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
  if (discountPaise <= zeroPaise) return unitPricePaise;
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
  if (!promoCode || promoCode.trim().toUpperCase() !== corporatePromoCode) return unitPricePaise;
  const discountPaise = Math.floor((unitPricePaise * corporatePromoBps) / bpsDivisor);
  if (discountPaise <= zeroPaise) return unitPricePaise;
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
    throw new ArithmeticDriftException(`Invalid base price ${baseUnitPricePaise} or quantity ${quantity}`);
  }

  const appliedDiscounts: AppliedDiscountItem[] = [];
  let currentPrice = applyVolumeTierDiscountStep(baseUnitPricePaise, quantity, volumeTiers, appliedDiscounts);
  currentPrice = applyCampaignDiscountStep(currentPrice, appliedDiscounts);
  currentPrice = applyPaymentRailDiscountStep(currentPrice, appliedDiscounts);
  currentPrice = applyPromoCodeDiscountStep(currentPrice, promoCode, appliedDiscounts);

  const offeredUnitPricePaise = Math.max(zeroPaise, currentPrice);
  const totalSavingsPaise = (baseUnitPricePaise - offeredUnitPricePaise) * quantity;

  return { offeredUnitPricePaise, appliedDiscounts, totalSavingsPaise };
}

function calculatePromotionUnitPrice(
  baseUnitPricePaise: number,
  promotion: ScheduledPromotion
): number {
  if (promotion.fixedPricePaise !== undefined) {
    return promotion.fixedPricePaise;
  }
  if (promotion.discountBps !== undefined) {
    return Math.floor((baseUnitPricePaise * (bpsDivisor - promotion.discountBps)) / bpsDivisor);
  }
  if (promotion.discountPaise !== undefined) {
    return Math.max(zeroPaise, baseUnitPricePaise - promotion.discountPaise);
  }
  return baseUnitPricePaise;
}

export function evaluateSingleScheduledPromotion(
  baseUnitPricePaise: number,
  promotion: ScheduledPromotion
): UpcomingPromotion {
  if (promotion.endsAtUnix <= promotion.startsAtUnix) {
    throw new ArithmeticDriftException(
      `Invalid temporal window for campaign ${promotion.campaignId}: endsAtUnix (${promotion.endsAtUnix}) <= startsAtUnix (${promotion.startsAtUnix})`
    );
  }

  const expectedUnitPricePaise = calculatePromotionUnitPrice(baseUnitPricePaise, promotion);
  assertIntegerPaise(expectedUnitPricePaise, "expectedUnitPricePaise");

  const expectedSavingsPaise = baseUnitPricePaise - expectedUnitPricePaise;
  if (expectedSavingsPaise < zeroPaise) {
    throw new ArithmeticDriftException(
      `Negative promotion savings detected for campaign ${promotion.campaignId}: expectedUnitPricePaise (${expectedUnitPricePaise}) exceeds baseUnitPricePaise (${baseUnitPricePaise})`
    );
  }

  return {
    campaign_id: promotion.campaignId,
    name: promotion.name,
    starts_at_unix: promotion.startsAtUnix,
    ends_at_unix: promotion.endsAtUnix,
    expected_unit_price_paise: expectedUnitPricePaise,
    expected_savings_paise: expectedSavingsPaise,
    ...(promotion.limitedStockAllocated !== undefined
      ? { limited_stock_allocated: promotion.limitedStockAllocated }
      : {})
  };
}

export function evaluateScheduledPromotions(
  baseUnitPricePaise: number,
  promotions: readonly ScheduledPromotion[] = [],
  currentTimeUnix: number = Math.floor(Date.now() / millisPerSecond)
): EvaluatedPromotionsResult {
  assertIntegerPaise(baseUnitPricePaise, "baseUnitPricePaise");
  assertIntegerPaise(currentTimeUnix, "currentTimeUnix");

  const activePromotions: UpcomingPromotion[] = [];
  const upcomingPromotions: UpcomingPromotion[] = [];

  for (const promotion of promotions) {
    const evaluated = evaluateSingleScheduledPromotion(baseUnitPricePaise, promotion);

    if (promotion.startsAtUnix <= currentTimeUnix && currentTimeUnix < promotion.endsAtUnix) {
      activePromotions.push(evaluated);
    } else if (promotion.startsAtUnix > currentTimeUnix) {
      upcomingPromotions.push(evaluated);
    }
  }

  return {
    activePromotions,
    upcomingPromotions
  };
}
