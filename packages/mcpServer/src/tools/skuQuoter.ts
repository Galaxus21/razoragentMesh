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
import { calculateVolumePricing, calculateGstBreakdown } from "../catalog/pricingEngine.js";
import { computeQuoteHash } from "../crypto/quoteHashSigner.js";

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
    buyer_agent_id: inputObj.buyer_agent_id ?? inputObj.buyerAgentId,
    delivery_pincode: inputObj.delivery_pincode ?? inputObj.deliveryPincode
  };

  return skuQuoteRequestSchema.parse(normalized);
}

export function executeSkuQuote(
  rawRequest: unknown,
  catalogStore: CatalogStore = defaultCatalogStore,
  secretKey?: string
): SkuQuoteResponse {
  const request = normalizeQuoteRequest(rawRequest);
  const sku = catalogStore.getRequiredSku(request.sku_id);
  const buyerState = resolveStateFromPincode(request.delivery_pincode);

  const pricing = calculateVolumePricing(
    sku.baseUnitPricePaise,
    request.quantity,
    sku.volumeTiers
  );

  const tax = calculateGstBreakdown(
    pricing.totalOfferedPaise,
    sku.gstRatePercent,
    defaultMerchantState,
    buyerState
  );

  const currentUnixSeconds = Math.floor(Date.now() / millisPerSecond);
  const quoteExpiryTimestamp = currentUnixSeconds + quoteValiditySeconds;

  const quoteHash = computeQuoteHash(
    {
      skuId: sku.skuId,
      quantity: request.quantity,
      offeredUnitPricePaise: pricing.offeredUnitPricePaise,
      totalTaxPaise: tax.totalTaxPaise,
      quoteExpiryTimestamp,
      buyerAgentId: request.buyer_agent_id
    },
    secretKey
  );

  const response: SkuQuoteResponse = {
    sku_id: sku.skuId,
    available_stock: sku.availableStock,
    base_unit_price_paise: sku.baseUnitPricePaise,
    offered_unit_price_paise: pricing.offeredUnitPricePaise,
    currency: currencyInr,
    hsn_code: sku.hsnCode,
    gst_rate_percent: sku.gstRatePercent,
    tax_breakdown: {
      cgst_paise: tax.cgstPaise,
      sgst_paise: tax.sgstPaise,
      igst_paise: tax.igstPaise,
      total_tax_paise: tax.totalTaxPaise
    },
    quote_expiry_timestamp: quoteExpiryTimestamp,
    quote_hash: quoteHash
  };

  return skuQuoteResponseSchema.parse(response);
}
