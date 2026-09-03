export interface CourierSlaRule {
  readonly maxHours: number;
  readonly costPaise: number;
  readonly courierPartner: string;
}

export const toolGetLiveSkuQuote = "get_live_sku_quote";
export const toolReserveInventoryLock = "reserve_inventory_lock";
export const toolVerifyShippingSla = "verify_shipping_sla";
// Discovery. Without this an agent can only quote a SKU id it was already given,
// so a third-party agent had no way to begin a purchase on its own.
export const toolSearchCatalog = "search_catalog";
// Enumeration, as distinct from search. An agent that cannot phrase a good semantic query still
// needs to find out what the mesh sells at all.
export const toolBrowseCatalog = "browse_catalog";
// Price discovery by bargaining rather than by lookup. The x402-INR gateway has spoken the
// alternating-offer protocol from the start, but over raw HTTP only -- so an MCP agent could take
// the list price or leave it.
export const toolNegotiatePrice = "negotiate_price";

// The purchase half of the protocol. Discovery, quoting and locking let an agent price a cart;
// these four let it actually buy, by producing the three AP2 mandates and settling them. Each
// signs with a different key, which is the whole point of the three-party split:
//   principal key -> M_I (userSignature)   merchant key -> M_C (merchantSignature)
//   buyer key     -> M_E (agentSignature)
export const toolEstablishAgentDelegation = "establish_agent_delegation";
export const toolCreateCartMandate = "create_cart_mandate";
export const toolSignExecutionMandate = "sign_execution_mandate";
export const toolExecuteSettlement = "execute_settlement";

export const jsonRpcVersion = "2.0";
export const mcpServerName = "razoragent-mesh-mcp";
export const mcpServerVersion = "2.0.0";
export const currencyInr = "INR";

export const defaultMerchantId = "mer_razoragent_mesh_01";
export const defaultMerchantState = "KA";
export const defaultOriginPincode = "560001";
// docker-compose passes HMAC_SECRET_KEY and MERCHANT_PRIVATE_KEY_HEX into this container, but
// nothing read them: the signing keys resolved to the hardcoded fallbacks below regardless of
// what the operator configured, and .env.example shipped a *different* HMAC value than the
// fallback -- so a configured mesh would sign with one key while peers verified with another.
// These now prefer the environment and fall back only for the bundled demo.
const developmentMerchantSecretKey = "mesh_hmac_secret_key_prod_v2_98f4a2";
const developmentMerchantPrivateKeyHex = "4c3b2a1009080706050403020100ffeeddccbbaa99887766554433221100ffee";

export const defaultMerchantSecretKey =
  process.env.HMAC_SECRET_KEY || developmentMerchantSecretKey;
export const defaultMerchantPrivateKeyHex =
  process.env.MERCHANT_PRIVATE_KEY_HEX || developmentMerchantPrivateKeyHex;

// docker-compose passes `MERCHANT_PRIVATE_KEY_HEX=${MERCHANT_PRIVATE_KEY_HEX:-}`, so an unset
// variable arrives as "" -- falsy in JS -- and the fallback above wins silently. These flags let
// startup say so out loud rather than leaving the operator to infer it.
export const merchantPrivateKeyIsDevelopmentFallback =
  defaultMerchantPrivateKeyHex === developmentMerchantPrivateKeyHex;
export const merchantSecretKeyIsDevelopmentFallback =
  defaultMerchantSecretKey === developmentMerchantSecretKey;

export const defaultLockTtlSeconds = 60;
export const minLockTtlSeconds = 10;
export const maxLockTtlSeconds = 120;
export const quoteValiditySeconds = 60;
/**
 * How far past quoteExpiryTimestamp a quote is still honoured, absorbing the round trip between
 * get_live_sku_quote and create_cart_mandate. Also bounds the reconciliation scan below the
 * expiry, so a quote that lapsed can be named as expired rather than reported as a hash mismatch.
 */
export const quoteExpiryGraceSeconds = 2;

export const minQuantity = 1;
export const maxQuantity = 10000;

export const bpsDivisor = 10000;
export const percentDivisor = 100;
// Divisor for the intra-state half-rate split (bpsDivisor * 2). Applying it once
// (rather than halving the rate, then dividing again) keeps CGST and SGST exactly
// equal and the total exactly conserved.
export const intraStateHalfBpsDivisor = 20000;
export const millisPerSecond = 1000;

export const hexEncoding = "hex";
export const base64Encoding = "base64";
export const utf8Encoding = "utf-8";
export const hmacAlgorithm = "sha256";
export const seedByteLength = 32;

export const deliveryTierStandard = "standard";
export const deliveryTierExpress = "express";
export const deliveryTierSameDay = "sameDay";

export const courierDelhivery = "Delhivery";
export const courierBlueDart = "BlueDart";

export const zoneCodeA = "ZONE_A";
export const zoneCodeB = "ZONE_B";
export const zoneCodeC = "ZONE_C";
export const zoneCodeD = "ZONE_D";

export const zoneAStandardHours = 24;
export const zoneAStandardCostPaise = 4000;
export const zoneAExpressHours = 12;
export const zoneAExpressCostPaise = 8000;
export const zoneASameDayHours = 6;
export const zoneASameDayCostPaise = 15000;

export const zoneBStandardHours = 48;
export const zoneBStandardCostPaise = 7000;
export const zoneBExpressHours = 24;
export const zoneBExpressCostPaise = 12000;

export const zoneCStandardHours = 72;
export const zoneCStandardCostPaise = 12000;
export const zoneCExpressHours = 36;
export const zoneCExpressCostPaise = 22000;

// MCP revisions this server implements. The newest is offered when a client asks for
// something we do not recognise; when the client names one of these we echo it back, which
// is what the spec requires and what strict clients check before proceeding.
export const supportedProtocolVersions: ReadonlyArray<string> = ["2025-06-18", "2025-03-26", "2024-11-05"];
export const preferredProtocolVersion = supportedProtocolVersions[0];

export const parseErrorCode = -32700;
export const invalidRequestErrorCode = -32600;
export const methodNotFoundErrorCode = -32601;
export const invalidParamsErrorCode = -32602;
export const internalErrorCode = -32603;
export const skuNotFoundErrorCode = -32004;
export const unregisteredZoneErrorCode = -32005;
export const arithmeticDriftErrorCode = -32008;

export const pincodePrefixStateMap: Record<string, string> = {
  "11": "DL",
  "12": "HR",
  "13": "HR",
  "14": "PB",
  "15": "PB",
  "16": "CH",
  "17": "HP",
  "18": "JK",
  "19": "JK",
  "20": "UP",
  "21": "UP",
  "22": "UP",
  "23": "UP",
  "24": "UP",
  "25": "UP",
  "26": "UP",
  "27": "UP",
  "28": "UP",
  "30": "RJ",
  "31": "RJ",
  "32": "RJ",
  "33": "RJ",
  "34": "RJ",
  "36": "GJ",
  "37": "GJ",
  "38": "GJ",
  "39": "GJ",
  "40": "MH",
  "41": "MH",
  "42": "MH",
  "43": "MH",
  "44": "MH",
  "45": "MP",
  "46": "MP",
  "47": "MP",
  "48": "MP",
  "49": "CG",
  "50": "TS",
  "51": "AP",
  "52": "AP",
  "53": "AP",
  "56": "KA",
  "57": "KA",
  "58": "KA",
  "59": "KA",
  "60": "TN",
  "61": "TN",
  "62": "TN",
  "63": "TN",
  "64": "TN",
  "67": "KL",
  "68": "KL",
  "69": "KL",
  "70": "WB",
  "71": "WB",
  "72": "WB",
  "73": "WB",
  "74": "WB",
  "75": "OD",
  "76": "OD",
  "77": "OD",
  "78": "AS",
  "79": "AR",
  "80": "BR",
  "81": "BR",
  "82": "JH",
  "83": "JH",
  "84": "BR",
  "85": "BR"
};

/**
 * The merchant's own state, used only where the ORIGIN pincode is the mesh's own configured
 * `defaultOriginPincode`. It is deliberately not a fallback for a buyer's delivery pincode: this
 * value is also `defaultMerchantState`, so guessing it for an unmapped delivery prefix routes the
 * cart down the intra-state CGST+SGST branch for a delivery that could be anywhere in India.
 */
export const defaultFallbackState = "KA";
 
 export const discountTypeVolumeTier = "VOLUME_TIER" as const;
 export const discountTypeCampaign = "CAMPAIGN" as const;
 export const discountTypePaymentRail = "PAYMENT_RAIL" as const;
 export const discountTypePromoCode = "PROMO_CODE" as const;
 
 export const festiveCampaignName = "RAZORPAY_FESTIVE_10";
 export const festiveCampaignBps = 1000;
 export const festiveCampaignCapPaise = 2000;
 export const upiCashbackName = "UPI_CASHBACK";
 export const upiCashbackPaise = 150;
 export const corporatePromoCode = "CORP_5PCT";
 export const corporatePromoBps = 500;
 
 export const meshCatalogUpdatesChannel = "mesh:catalog:updates";
// Every merchant SKU is stored at `mesh:catalog:{skuId}`. The updates channel above shares
// this prefix but is a channel, not a key.
export const meshCatalogKeyPrefix = "mesh:catalog:";
 export const catalogEventAdded = "CATALOG_ITEM_ADDED";
 export const catalogEventUpdated = "CATALOG_ITEM_UPDATED";
 export const catalogEventRemoved = "CATALOG_ITEM_REMOVED";
