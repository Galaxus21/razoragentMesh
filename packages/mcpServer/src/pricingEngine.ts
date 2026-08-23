import {
  bpsDivisor,
  percentDivisor,
  halfGstDivisor
} from "./mcpConstants.js";
import {
  VolumeTier,
  TaxBreakdown,
  ArithmeticDriftException
} from "./mcpTypes.js";

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
