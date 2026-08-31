// The MCP tool layer speaks snake_case (it is a Model Context Protocol tool surface, and the
// JSON-RPC tool schemas in ../schemas are snake_case by design). The buyer SDKs speak camelCase.
// This module is the single translation seam between the two, so neither side has to bend.

import type { SkuQuoteResponse } from "../schemas/skuQuoteSchema.js";
import type { InventoryLockResponse } from "../schemas/inventoryLockSchema.js";
import type { ShippingSlaResponse } from "../schemas/shippingSlaSchema.js";
import { defaultOriginPincode } from "../constants/httpAdapterConstants.js";
import { deliveryTierStandard } from "../constants/protocolConstants.js";

export interface SdkTaxBreakdown {
  readonly cgstPaise: number;
  readonly sgstPaise: number;
  readonly igstPaise: number;
  readonly totalTaxPaise: number;
}

export interface SdkAppliedDiscount {
  readonly code: string;
  readonly name: string;
  readonly discountPaise: number;
  readonly type: string;
}

export interface SdkUpcomingPromotion {
  readonly campaignId: string;
  readonly name: string;
  readonly startsAtUnix: number;
  readonly endsAtUnix: number;
  readonly expectedUnitPricePaise: number;
  readonly expectedSavingsPaise: number;
  readonly limitedStockAllocated?: number;
}

export interface SdkSkuQuote {
  readonly skuId: string;
  readonly baseUnitPricePaise: number;
  readonly offeredUnitPricePaise: number;
  readonly finalUnitPricePaise: number;
  readonly availableStock: number;
  readonly quantity: number;
  readonly currency: string;
  readonly hsnCode: string;
  readonly gstRatePercent: number;
  readonly taxableSubtotalPaise: number;
  readonly taxBreakdown: SdkTaxBreakdown;
  readonly appliedDiscounts: readonly SdkAppliedDiscount[];
  readonly totalSavingsPaise: number;
  readonly quoteExpiryTimestamp: number;
  readonly quoteHash: string;
  readonly upcomingPromotions: readonly SdkUpcomingPromotion[];
}

export interface SdkInventoryLock {
  readonly lockToken: string;
  readonly fencingToken: number;
  readonly skuId: string;
  readonly quantityLocked: number;
  readonly expiresAtUnixMs: number;
  readonly lockSignature: string;
}

export interface SdkSlaVerification {
  readonly pincode: string;
  readonly zone: string;
  readonly deliverySpeed: string;
  readonly slaHours: number;
  readonly shippingFeePaise: number;
  readonly weightGrams: number;
  readonly courierPartner: string;
  readonly serviceable: boolean;
}

function mapAppliedDiscounts(
  rawDiscounts: SkuQuoteResponse["applied_discounts"]
): readonly SdkAppliedDiscount[] {
  if (!rawDiscounts) {
    return [];
  }
  return rawDiscounts.map((discount) => ({
    code: discount.type,
    name: discount.label,
    discountPaise: discount.discountPaise ?? 0,
    type: discount.type
  }));
}

function mapUpcomingPromotions(
  rawPromotions: SkuQuoteResponse["upcoming_promotions"]
): readonly SdkUpcomingPromotion[] {
  if (!rawPromotions) {
    return [];
  }
  return rawPromotions.map((promotion) => ({
    campaignId: promotion.campaign_id,
    name: promotion.name,
    startsAtUnix: promotion.starts_at_unix,
    endsAtUnix: promotion.ends_at_unix,
    expectedUnitPricePaise: promotion.expected_unit_price_paise,
    expectedSavingsPaise: promotion.expected_savings_paise,
    ...(promotion.limited_stock_allocated !== undefined
      ? { limitedStockAllocated: promotion.limited_stock_allocated }
      : {})
  }));
}

export function toSdkSkuQuote(toolResponse: SkuQuoteResponse, quantity: number): SdkSkuQuote {
  const offeredUnitPricePaise = toolResponse.offered_unit_price_paise;
  return {
    skuId: toolResponse.sku_id,
    baseUnitPricePaise: toolResponse.base_unit_price_paise,
    offeredUnitPricePaise,
    // The SDK's `finalUnitPricePaise` is the post-discount, pre-tax unit price -- exactly what
    // the pricing engine calls `offered_unit_price_paise`. Kept as two names because the SDK
    // contract predates the tool schema; they are the same number by definition.
    finalUnitPricePaise: offeredUnitPricePaise,
    availableStock: toolResponse.available_stock,
    quantity,
    currency: toolResponse.currency,
    hsnCode: toolResponse.hsn_code,
    gstRatePercent: toolResponse.gst_rate_percent,
    taxableSubtotalPaise: offeredUnitPricePaise * quantity,
    taxBreakdown: {
      cgstPaise: toolResponse.tax_breakdown.cgst_paise,
      sgstPaise: toolResponse.tax_breakdown.sgst_paise,
      igstPaise: toolResponse.tax_breakdown.igst_paise,
      totalTaxPaise: toolResponse.tax_breakdown.total_tax_paise
    },
    appliedDiscounts: mapAppliedDiscounts(toolResponse.applied_discounts),
    totalSavingsPaise: toolResponse.total_savings_paise ?? 0,
    quoteExpiryTimestamp: toolResponse.quote_expiry_timestamp,
    quoteHash: toolResponse.quote_hash,
    upcomingPromotions: mapUpcomingPromotions(toolResponse.upcoming_promotions)
  };
}

export function toSdkInventoryLock(toolResponse: InventoryLockResponse): SdkInventoryLock {
  return {
    lockToken: toolResponse.lock_token,
    fencingToken: toolResponse.fencing_token,
    skuId: toolResponse.sku_id,
    quantityLocked: toolResponse.quantity_locked,
    expiresAtUnixMs: toolResponse.expires_at_unix_ms,
    lockSignature: toolResponse.signature
  };
}

export interface SlaEchoContext {
  readonly deliveryPincode: string;
  readonly weightGrams: number;
  readonly deliveryTier: string;
}

export function toSdkSlaVerification(
  toolResponse: ShippingSlaResponse,
  echo: SlaEchoContext
): SdkSlaVerification {
  return {
    pincode: echo.deliveryPincode,
    zone: toolResponse.zone_code,
    deliverySpeed: echo.deliveryTier,
    slaHours: toolResponse.guaranteed_sla_hours,
    shippingFeePaise: toolResponse.shipping_cost_paise,
    weightGrams: echo.weightGrams,
    courierPartner: toolResponse.courier_partner,
    serviceable: toolResponse.serviceable
  };
}

// The SDK sends only a destination pincode and a weight; the SLA tool needs a full
// origin/destination/tier triple. Fill the merchant-side half here rather than widening
// the SDK's `verifyShippingSla` signature.
export function toSlaToolInput(
  deliveryPincode: string,
  weightGrams: number,
  deliveryTier: string = deliveryTierStandard
): Record<string, unknown> {
  return {
    origin_pincode: defaultOriginPincode,
    delivery_pincode: deliveryPincode,
    package_weight_grams: weightGrams,
    required_delivery_tier: deliveryTier
  };
}
