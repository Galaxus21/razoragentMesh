import {
  defaultMerchantState,
  discountTypeNegotiated,
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
  DiscountStackResult,
  ScheduledPromotion,
  UpcomingPromotion,
  TaxBreakdown
} from "../catalog/pricingEngine.js";
import { CatalogSkuItem, InvalidPincodeException } from "../types/mcpToolTypes.js";
import { computeQuoteHash } from "../crypto/quoteHashSigner.js";
import {
  defaultIssuedQuoteRegistry,
  IssuedQuoteRegistry
} from "../inventory/issuedQuoteRegistry.js";
import {
  AgreedPrice,
  AgreedPriceRegistry,
  defaultAgreedPriceRegistry
} from "../negotiation/agreedPriceRegistry.js";

export interface SkuQuotePricingResult {
  readonly offeredUnitPricePaise: number;
  readonly appliedDiscounts: AppliedDiscountItem[];
  readonly totalSavingsPaise: number;
  readonly tax: TaxBreakdown;
  // Present only when a negotiated agreement actually set the price. The packager reads it to
  // bound the quote's expiry by the agreement's; nothing else depends on it.
  readonly agreement?: AgreedPrice;
}

export interface SignAndPackageQuoteParams {
  readonly request: SkuQuoteRequest;
  readonly sku: CatalogSkuItem;
  readonly pricing: SkuQuotePricingResult;
  readonly secretKey?: string;
  readonly quoteRegistry?: IssuedQuoteRegistry;
}

export const pincodePrefixLength = 2;
// Rupee formatting for discount labels only. Every price this file computes stays in paise.
const paisePerRupee = 100;

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
  secretKey?: string,
  quoteRegistry: IssuedQuoteRegistry = defaultIssuedQuoteRegistry,
  agreedPriceRegistry: AgreedPriceRegistry = defaultAgreedPriceRegistry
): SkuQuoteResponse {
  const { request, sku, buyerState } = _resolveCatalogItem(rawRequest, catalogStore);
  const pricing = _computeQuoteWithDiscounts(sku, request, buyerState, agreedPriceRegistry);
  return _signAndPackageQuote({ request, sku, pricing, secretKey, quoteRegistry });
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
  request: SkuQuoteRequest,
  buyerState: string,
  agreedPriceRegistry: AgreedPriceRegistry
): SkuQuotePricingResult {
  // `sku.promotions` reaches the discount stack so an OPEN merchant sale is priced, not merely
  // classified. `_resolveUpcomingPromotions` below still reports the ones that have not started.
  const discountResult = computeAutoDiscountStack(
    sku.baseUnitPricePaise,
    request.quantity,
    sku.volumeTiers,
    request.promo_code,
    sku.merchantOffers,
    sku.promotions
  );
  const priced = _applyNegotiatedAgreement(sku, request, discountResult, agreedPriceRegistry);
  const taxableSubtotalPaise = priced.offeredUnitPricePaise * request.quantity;
  const tax = calculateGstBreakdown(
    taxableSubtotalPaise,
    sku.gstRatePercent,
    defaultMerchantState,
    buyerState
  );

  return { ...priced, tax };
}

/**
 * Applies a converged negotiation, when this buyer has one live for this exact purchase.
 *
 * The LOWER of the two prices, never the agreed one outright. A merchant sale that opened after
 * the bargain was struck must still reach the buyer, and taking the agreed figure unconditionally
 * would let a negotiation RAISE what someone pays -- the one outcome bargaining must never
 * produce. When the automatic stack already wins, the agreement goes unapplied and the quote
 * keeps its ordinary expiry.
 *
 * cartMandateCreator re-runs this whole path before the merchant signs, so the agreement is
 * looked up twice and the price is the mesh's own on both passes. That is why a bindable
 * negotiation needs no change to the quote hash: an agent still cannot name a price, it can only
 * have negotiated one.
 */
function _applyNegotiatedAgreement(
  sku: CatalogSkuItem,
  request: SkuQuoteRequest,
  automatic: DiscountStackResult,
  registry: AgreedPriceRegistry
): Omit<SkuQuotePricingResult, "tax"> {
  const ordinary = {
    offeredUnitPricePaise: automatic.offeredUnitPricePaise,
    appliedDiscounts: [...automatic.appliedDiscounts],
    totalSavingsPaise: automatic.totalSavingsPaise
  };
  const agreement = registry.lookup({
    skuId: sku.skuId,
    quantity: request.quantity,
    buyerAgentId: request.buyer_agent_id
  });
  if (!agreement || agreement.agreedUnitPricePaise >= ordinary.offeredUnitPricePaise) {
    return ordinary;
  }

  const discountPaise = ordinary.offeredUnitPricePaise - agreement.agreedUnitPricePaise;
  ordinary.appliedDiscounts.push({
    type: discountTypeNegotiated,
    label: _negotiatedDiscountLabel(discountPaise),
    discountPaise
  });
  return {
    offeredUnitPricePaise: agreement.agreedUnitPricePaise,
    appliedDiscounts: ordinary.appliedDiscounts,
    totalSavingsPaise: (sku.baseUnitPricePaise - agreement.agreedUnitPricePaise) * request.quantity,
    agreement
  };
}

function _signAndPackageQuote(params: SignAndPackageQuoteParams): SkuQuoteResponse {
  const { request, sku, pricing, secretKey } = params;
  const currentUnixSeconds = Math.floor(Date.now() / millisPerSecond);
  const quoteExpiryTimestamp = _resolveQuoteExpiry(currentUnixSeconds, pricing.agreement);
  const quoteHash = computeQuoteHash(
    {
      skuId: sku.skuId, quantity: request.quantity, offeredUnitPricePaise: pricing.offeredUnitPricePaise,
      totalTaxPaise: pricing.tax.totalTaxPaise, quoteExpiryTimestamp, buyerAgentId: request.buyer_agent_id
    },
    secretKey
  );

  // Recorded here rather than at the tool boundary so every path that mints a quote_hash --
  // MCP, the REST adapter, the SDKs -- registers it. reserve_inventory_lock refuses a hash that
  // never passed through here, which is what stops a fabricated one from taking real stock.
  (params.quoteRegistry ?? defaultIssuedQuoteRegistry).record(
    {
      quoteHash,
      skuId: sku.skuId,
      quantity: request.quantity,
      buyerAgentId: request.buyer_agent_id,
      quoteExpiryTimestamp
    },
    currentUnixSeconds
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

/** Rupees for the agent's benefit; the paise figure beside it is the one that reconciles. */
function _negotiatedDiscountLabel(discountPaise: number): string {
  return `Negotiated with the merchant (₹${(discountPaise / paisePerRupee).toFixed(2)} off the offered price)`;
}

/**
 * A quote priced by a negotiation must not outlive the agreement that priced it.
 *
 * cartMandateCreator re-quotes and compares hashes. If the agreement lapsed in between, the
 * re-quote returns to list, the two hashes differ, and the agent is told "quote mismatch" --
 * which sends it looking for a hashing bug when the truth is that its bargain ran out. Capping
 * the expiry means that case arrives as the ordinary "quote expired, quote again" refusal, which
 * names an action the agent can actually take.
 */
function _resolveQuoteExpiry(nowUnix: number, agreement: AgreedPrice | undefined): number {
  const ordinaryExpiry = nowUnix + quoteValiditySeconds;
  return agreement === undefined
    ? ordinaryExpiry
    : Math.min(ordinaryExpiry, agreement.agreementExpiresAt);
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
