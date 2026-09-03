import {
  defaultMerchantState,
  pincodePrefixStateMap,
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
import { CatalogSkuItem, InvalidPincodeException } from "../types/mcpToolTypes.js";
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

/**
 * Pure lookup: the state this prefix is registered to, or undefined when it is not in the map.
 * The single source of truth for "do we know where this pincode is", so the tax path and the
 * shipping path cannot disagree -- they previously did, one guessing "KA" and the other falling
 * through to the raw prefix. Callers choose whether an unknown pincode is reported or raised.
 */
export function lookupStateFromPincode(pincode: string): string | undefined {
  return pincodePrefixStateMap[pincode.slice(0, pincodePrefixLength)];
}

/**
 * Resolves the delivery state for TAX, and refuses when it cannot.
 *
 * This used to fall back to defaultFallbackState ("KA"), which is also defaultMerchantState -- so
 * an unmapped prefix took the intra-state branch and issued CGST+SGST for a delivery that might
 * be anywhere in India, with no warning and no field recording that the state was guessed. The
 * mandate engine already refuses these outright with InvalidPincodeException, so the old
 * behaviour was a deferred failure rather than a working path: the quote succeeded, and the
 * purchase died at settlement. Refusing here is a rejected order instead of a wrong tax head.
 */
export function resolveStateFromPincode(pincode: string): string {
  const state = lookupStateFromPincode(pincode);
  if (state === undefined) {
    throw new InvalidPincodeException(
      pincode,
      `no GST state is registered for the prefix '${pincode.slice(0, pincodePrefixLength)}'. ` +
        "The mesh will not guess a state, because guessing decides whether you are charged " +
        "CGST+SGST or IGST. Use a delivery pincode in a serviced state."
    );
  }
  return state;
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
  const discountResult = computeAutoDiscountStack(sku.baseUnitPricePaise, quantity, sku.volumeTiers, promoCode, sku.merchantOffers);
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
    category: sku.category,
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
