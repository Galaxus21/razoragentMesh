import {
  defaultMerchantState,
  pincodePrefixStateMap,
  defaultFallbackState,
  quoteValiditySeconds,
  millisPerSecond,
  currencyInr
} from "../constants/protocolConstants.js";
import {
  SkuQuoteRequest,
  SkuQuoteResponse,
  skuQuoteRequestSchema,
  skuQuoteResponseSchema
} from "../schemas/skuQuoteSchema.js";
import { defaultCatalogStore, CatalogStore } from "../catalog/catalogStore.js";
import {
  calculateGstBreakdown,
  computeAutoDiscountStack,
  evaluateScheduledPromotions,
  AppliedDiscountItem,
  ScheduledPromotion,
  UpcomingPromotion,
  TaxBreakdown
} from "../catalog/pricingEngine.js";
import { CatalogSkuItem } from "../types/mcpToolTypes.js";
import { computeQuoteHash } from "../crypto/quoteHashSigner.js";

export interface SkuQuotePricingResult {
  readonly offeredUnitPricePaise: number;
  readonly appliedDiscounts: AppliedDiscountItem[];
  readonly totalSavingsPaise: number;
  readonly tax: TaxBreakdown;
}

export interface SignAndPackageQuoteParams {
  readonly request: SkuQuoteRequest;
  readonly sku: CatalogSkuItem;
  readonly pricing: SkuQuotePricingResult;
  readonly secretKey?: string;
}

export const pincodePrefixLength = 2;

export function resolveStateFromPincode(pincode: string): string {
  const prefix = pincode.slice(0, pincodePrefixLength);
  return pincodePrefixStateMap[prefix] ?? defaultFallbackState;
}

export function normalizeQuoteRequest(rawInput: unknown): SkuQuoteRequest {
  const inputObj = rawInput as Record<string, unknown>;
  const normalized = {
    sku_id: inputObj.sku_id ?? inputObj.skuId,
    quantity: inputObj.quantity,
    buyer_agent_id: inputObj.buyer_agent_id ?? inputObj.buyerAgentId ?? inputObj.buyerAgentDid,
    delivery_pincode: inputObj.delivery_pincode ?? inputObj.deliveryPincode,
    promo_code: inputObj.promo_code ?? inputObj.promoCode
  };

  return skuQuoteRequestSchema.parse(normalized);
}

export function executeSkuQuote(
  rawRequest: unknown,
  catalogStore: CatalogStore = defaultCatalogStore,
  secretKey?: string
): SkuQuoteResponse {
  const { request, sku, buyerState } = _resolveCatalogItem(rawRequest, catalogStore);
  const pricing = _computeQuoteWithDiscounts(sku, request.quantity, request.promo_code, buyerState);
  return _signAndPackageQuote({ request, sku, pricing, secretKey });
}

function _resolveCatalogItem(
  rawRequest: unknown,
  catalogStore: CatalogStore
): { request: SkuQuoteRequest; sku: CatalogSkuItem; buyerState: string } {
  const request = normalizeQuoteRequest(rawRequest);
  const sku = catalogStore.getRequiredSku(request.sku_id);
  const buyerState = resolveStateFromPincode(request.delivery_pincode);
  return { request, sku, buyerState };
}

function _computeQuoteWithDiscounts(
  sku: CatalogSkuItem,
  quantity: number,
  promoCode: string | undefined,
  buyerState: string
): SkuQuotePricingResult {
  const discountResult = computeAutoDiscountStack(sku.baseUnitPricePaise, quantity, sku.volumeTiers, promoCode);
  const taxableSubtotalPaise = discountResult.offeredUnitPricePaise * quantity;
  const tax = calculateGstBreakdown(taxableSubtotalPaise, sku.gstRatePercent, defaultMerchantState, buyerState);

  return {
    offeredUnitPricePaise: discountResult.offeredUnitPricePaise,
    appliedDiscounts: [...discountResult.appliedDiscounts],
    totalSavingsPaise: discountResult.totalSavingsPaise,
    tax
  };
}

function _signAndPackageQuote(params: SignAndPackageQuoteParams): SkuQuoteResponse {
  const { request, sku, pricing, secretKey } = params;
  const currentUnixSeconds = Math.floor(Date.now() / millisPerSecond);
  const quoteExpiryTimestamp = currentUnixSeconds + quoteValiditySeconds;
  const quoteHash = computeQuoteHash(
    {
      skuId: sku.skuId, quantity: request.quantity, offeredUnitPricePaise: pricing.offeredUnitPricePaise,
      totalTaxPaise: pricing.tax.totalTaxPaise, quoteExpiryTimestamp, buyerAgentId: request.buyer_agent_id
    },
    secretKey
  );

  const upcomingPromotions = _resolveUpcomingPromotions(sku.baseUnitPricePaise, sku.promotions, currentUnixSeconds);
  const response: SkuQuoteResponse = {
    sku_id: sku.skuId,
    available_stock: sku.availableStock,
    base_unit_price_paise: sku.baseUnitPricePaise,
    offered_unit_price_paise: pricing.offeredUnitPricePaise,
    currency: currencyInr,
    hsn_code: sku.hsnCode,
    gst_rate_percent: sku.gstRatePercent,
    tax_breakdown: {
      cgst_paise: pricing.tax.cgstPaise, sgst_paise: pricing.tax.sgstPaise,
      igst_paise: pricing.tax.igstPaise, total_tax_paise: pricing.tax.totalTaxPaise
    },
    quote_expiry_timestamp: quoteExpiryTimestamp,
    quote_hash: quoteHash,
    applied_discounts: pricing.appliedDiscounts,
    total_savings_paise: pricing.totalSavingsPaise,
    ...(upcomingPromotions && upcomingPromotions.length > 0 ? { upcoming_promotions: upcomingPromotions } : {})
  };

  return skuQuoteResponseSchema.parse(response);
}

function _resolveUpcomingPromotions(
  baseUnitPricePaise: number,
  promotions: readonly ScheduledPromotion[] | undefined,
  currentUnixSeconds: number
): UpcomingPromotion[] | undefined {
  if (!promotions || promotions.length === 0) {
    return undefined;
  }
  const evaluated = evaluateScheduledPromotions(baseUnitPricePaise, promotions, currentUnixSeconds);
  return evaluated.upcomingPromotions.length > 0 ? [...evaluated.upcomingPromotions] : undefined;
}
