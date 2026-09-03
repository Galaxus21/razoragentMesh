import {
  bpsDivisor,
  percentDivisor,
  intraStateHalfBpsDivisor,
  millisPerSecond,
  discountTypeVolumeTier,
  discountTypeScheduledPromotion,
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
  EvaluatedPromotionsResult,
  MerchantAuthoredOffers,
  MerchantPromoCodeOffer
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

/**
 * The campaign, cashback and promo codes this SKU actually offers.
 *
 * A SKU that carries `merchantOffers` states its offers completely -- so an absent `campaign`
 * there means no campaign, not "fall back to the demo default". Otherwise a merchant could add
 * offers from the Studio but never switch the built-in festive discount off, which is worse than
 * not letting them author offers at all.
 *
 * A SKU with no `merchantOffers` keeps the original demo-wide constants, so every fixture and
 * every previously published listing prices exactly as before.
 */
export function resolveSkuOffers(offers: MerchantAuthoredOffers | undefined): {
  readonly campaignBps: number;
  readonly campaignCapPaise: number | null;
  readonly campaignLabel: string | null;
  readonly cashbackPaise: number;
  readonly promoCodes: readonly MerchantPromoCodeOffer[];
} {
  if (!offers) {
    return {
      campaignBps: festiveCampaignBps,
      campaignCapPaise: festiveCampaignCapPaise,
      campaignLabel: null,
      cashbackPaise: upiCashbackPaise,
      promoCodes: [{ code: corporatePromoCode, discountBps: corporatePromoBps }]
    };
  }
  return {
    campaignBps: offers.campaign?.discountBps ?? zeroBps,
    // null is uncapped. `?? null` rather than `|| null` because a cap of 0 is a real instruction
    // -- it means the campaign discounts nothing -- and must not be read as "no cap".
    campaignCapPaise: offers.campaign?.capPaise ?? null,
    campaignLabel: offers.campaign?.label ?? null,
    cashbackPaise: offers.paymentRailCashbackPaise ?? zeroPaise,
    promoCodes: offers.promoCodes ?? []
  };
}

/**
 * Applies the merchant's own scheduled sale, when one is open.
 *
 * This step did not exist. `evaluateScheduledPromotions` split promotions into active and
 * upcoming, `upcomingPromotions` was returned to the agent, and `activePromotions` was read by no
 * production code -- so a sale was advertised while it was still coming and then never charged
 * once it arrived. Measured on 2026-09-03: the mesh promised `expectedUnitPricePaise: 1800000`
 * while upcoming and charged 2397850 thirty minutes into the window.
 *
 * It runs FIRST, on the base price, because `expectedUnitPricePaise` is computed from the base
 * price too. Anything else and the price the mesh promised while the sale was upcoming would not
 * be the price it charges once the sale opens -- which is the whole defect. Later steps compound
 * on the promoted price, so a buyer can only end up paying less than was advertised, never more.
 *
 * A malformed promotion (inverted window, fixed price above list) throws in the evaluator. It is
 * swallowed here for the same reason `catalogBrowser` swallows it: a merchant's bad promotion
 * record must cost that sale's discount, not the ability to quote the SKU at all.
 */
function applyScheduledPromotionStep(
  baseUnitPricePaise: number,
  promotions: readonly ScheduledPromotion[],
  currentTimeUnix: number,
  appliedDiscounts: AppliedDiscountItem[]
): number {
  if (promotions.length === 0) return baseUnitPricePaise;

  let active: readonly UpcomingPromotion[];
  try {
    active = evaluateScheduledPromotions(baseUnitPricePaise, promotions, currentTimeUnix)
      .activePromotions;
  } catch {
    return baseUnitPricePaise;
  }
  if (active.length === 0) return baseUnitPricePaise;

  // Deepest wins. Overlapping windows are a merchant authoring mistake, not a stacking
  // instruction: charging the sum of two sales can drive a price to zero.
  const best = active.reduce((deepest, promotion) =>
    promotion.expected_unit_price_paise < deepest.expected_unit_price_paise ? promotion : deepest
  );
  const discountPaise = baseUnitPricePaise - best.expected_unit_price_paise;
  if (discountPaise <= zeroPaise) return baseUnitPricePaise;

  appliedDiscounts.push({
    type: discountTypeScheduledPromotion,
    label: `${best.name ?? best.campaign_id} (merchant sale)`,
    discountPaise
  });
  return best.expected_unit_price_paise;
}

function applyCampaignDiscountStep(
  unitPricePaise: number,
  offers: MerchantAuthoredOffers | undefined,
  appliedDiscounts: AppliedDiscountItem[]
): number {
  const { campaignBps, campaignCapPaise, campaignLabel } = resolveSkuOffers(offers);
  if (campaignBps <= zeroBps) return unitPricePaise;
  const uncappedPaise = Math.floor((unitPricePaise * campaignBps) / bpsDivisor);
  const discountPaise =
    campaignCapPaise === null ? uncappedPaise : Math.min(campaignCapPaise, uncappedPaise);
  if (discountPaise <= zeroPaise) return unitPricePaise;
  const capText = campaignCapPaise === null ? "" : ` capped at ₹${campaignCapPaise / 100}`;
  appliedDiscounts.push({
    type: discountTypeCampaign,
    label: `${campaignLabel ?? "Festive Campaign"} (${campaignBps / 100}% off${capText})`,
    discountBps: campaignBps,
    discountPaise
  });
  return unitPricePaise - discountPaise;
}

function applyPaymentRailDiscountStep(
  unitPricePaise: number,
  offers: MerchantAuthoredOffers | undefined,
  appliedDiscounts: AppliedDiscountItem[]
): number {
  const { cashbackPaise } = resolveSkuOffers(offers);
  const discountPaise = Math.min(unitPricePaise, cashbackPaise);
  if (discountPaise <= zeroPaise) return unitPricePaise;
  appliedDiscounts.push({
    type: discountTypePaymentRail,
    label: `UPI Instant Cashback (₹${(discountPaise / 100).toFixed(2)})`,
    discountPaise
  });
  return unitPricePaise - discountPaise;
}

function applyPromoCodeDiscountStep(
  unitPricePaise: number,
  promoCode: string | undefined,
  offers: MerchantAuthoredOffers | undefined,
  appliedDiscounts: AppliedDiscountItem[]
): number {
  if (!promoCode) return unitPricePaise;
  const normalised = promoCode.trim().toUpperCase();
  const { promoCodes } = resolveSkuOffers(offers);
  const matched = promoCodes.find((offer) => offer.code.trim().toUpperCase() === normalised);
  if (!matched || matched.discountBps <= zeroBps) return unitPricePaise;
  const discountPaise = Math.floor((unitPricePaise * matched.discountBps) / bpsDivisor);
  if (discountPaise <= zeroPaise) return unitPricePaise;
  appliedDiscounts.push({
    type: discountTypePromoCode,
    label: `${matched.label ?? "Promo Code"} ${matched.code} (${matched.discountBps / 100}% off)`,
    discountBps: matched.discountBps,
    discountPaise
  });
  return unitPricePaise - discountPaise;
}

export function computeAutoDiscountStack(
  baseUnitPricePaise: number,
  quantity: number,
  volumeTiers: readonly VolumeTier[],
  promoCode?: string,
  merchantOffers?: MerchantAuthoredOffers,
  promotions: readonly ScheduledPromotion[] = [],
  currentTimeUnix: number = Math.floor(Date.now() / millisPerSecond)
): DiscountStackResult {
  assertIntegerPaise(baseUnitPricePaise, "baseUnitPricePaise");
  assertIntegerPaise(quantity, "quantity");

  if (baseUnitPricePaise < zeroPaise || quantity < 1) {
    throw new ArithmeticDriftException(`Invalid base price ${baseUnitPricePaise} or quantity ${quantity}`);
  }

  const appliedDiscounts: AppliedDiscountItem[] = [];
  let currentPrice = applyScheduledPromotionStep(
    baseUnitPricePaise,
    promotions,
    currentTimeUnix,
    appliedDiscounts
  );
  currentPrice = applyVolumeTierDiscountStep(currentPrice, quantity, volumeTiers, appliedDiscounts);
  currentPrice = applyCampaignDiscountStep(currentPrice, merchantOffers, appliedDiscounts);
  currentPrice = applyPaymentRailDiscountStep(currentPrice, merchantOffers, appliedDiscounts);
  currentPrice = applyPromoCodeDiscountStep(currentPrice, promoCode, merchantOffers, appliedDiscounts);

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
