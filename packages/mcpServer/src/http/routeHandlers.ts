// REST handlers for the three tools the buyer SDKs call directly. Each one reuses the exact
// tool function the JSON-RPC path uses -- no duplicated pricing, locking, or SLA logic here,
// only wire-shape translation via ./wireMappers.js.

import { executeSkuQuote } from "../tools/skuQuoter.js";
import { reserveInventoryLock } from "../tools/inventoryLocker.js";
import { verifyShippingSla } from "../tools/slaVerifier.js";
import { defaultCatalogStore } from "../catalog/catalogStore.js";
import { defaultInMemoryLocker } from "../inventory/redisLockManager.js";
import { deliveryTierStandard } from "../constants/protocolConstants.js";
import { defaultQuoteQuantity, defaultSlaWeightGrams } from "../constants/httpRequestDefaults.js";
import {
  SdkInventoryLock,
  SdkSkuQuote,
  SdkSlaVerification,
  toSdkInventoryLock,
  toSdkSkuQuote,
  toSdkSlaVerification,
  toSlaToolInput
} from "./wireMappers.js";

function readNumericParam(rawValue: string | null, fallbackValue: number): number {
  if (rawValue === null || rawValue.trim() === "") {
    return fallbackValue;
  }
  const parsed = Number(rawValue);
  return Number.isFinite(parsed) ? parsed : Number.NaN;
}

// GET /api/v1/quote?skuId=&quantity=&buyerAgentDid=&deliveryPincode=&promoCode=
export function handleQuoteRequest(query: URLSearchParams): SdkSkuQuote {
  const quantity = readNumericParam(query.get("quantity"), defaultQuoteQuantity);
  // deliveryPincode is omitted rather than forwarded as null when the caller leaves it out.
  // The quote tool genuinely requires it -- the pincode decides whether the tax split is
  // CGST+SGST or IGST, so there is no safe default -- and passing null made zod report
  // "expected string, received null" for a field the SDK caller never mentioned. Omitting it
  // produces a plain "required" error naming the parameter instead.
  const deliveryPincode = query.get("deliveryPincode");
  const toolInput = {
    skuId: query.get("skuId"),
    quantity,
    buyerAgentDid: query.get("buyerAgentDid"),
    ...(deliveryPincode ? { deliveryPincode } : {}),
    ...(query.get("promoCode") ? { promoCode: query.get("promoCode") } : {})
  };
  // Reclaim lapsed reservations before reading stock, so `availableStock` reflects what a
  // lock attempt would actually find rather than what was held at some earlier moment.
  defaultInMemoryLocker.reclaimExpired(defaultCatalogStore);
  const toolResponse = executeSkuQuote(toolInput, defaultCatalogStore);
  return toSdkSkuQuote(toolResponse, quantity);
}

// POST /api/v1/lock  { skuId, quantity, buyerAgentDid, lockTtlSeconds, quoteHash }
export async function handleLockRequest(body: unknown): Promise<SdkInventoryLock> {
  const toolResponse = await reserveInventoryLock(body, { catalogStore: defaultCatalogStore });
  return toSdkInventoryLock(toolResponse);
}

// GET /api/v1/sla?pincode=&weightGrams=&deliveryTier=
export function handleSlaRequest(query: URLSearchParams): SdkSlaVerification {
  const deliveryPincode = query.get("pincode") ?? "";
  const weightGrams = readNumericParam(query.get("weightGrams"), defaultSlaWeightGrams);
  const deliveryTier = query.get("deliveryTier") ?? deliveryTierStandard;
  const toolResponse = verifyShippingSla(toSlaToolInput(deliveryPincode, weightGrams, deliveryTier));
  return toSdkSlaVerification(toolResponse, { deliveryPincode, weightGrams, deliveryTier });
}
