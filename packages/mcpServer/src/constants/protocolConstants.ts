export interface CourierSlaRule {
  readonly maxHours: number;
  readonly costPaise: number;
  readonly courierPartner: string;
}

export const toolGetLiveSkuQuote = "get_live_sku_quote";
export const toolReserveInventoryLock = "reserve_inventory_lock";
export const toolVerifyShippingSla = "verify_shipping_sla";

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

export const defaultLockTtlSeconds = 60;
export const minLockTtlSeconds = 10;
export const maxLockTtlSeconds = 120;
export const quoteValiditySeconds = 60;

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

export const parseErrorCode = -32700;
export const invalidRequestErrorCode = -32600;
export const methodNotFoundErrorCode = -32601;
export const invalidParamsErrorCode = -32602;
export const internalErrorCode = -32603;
export const skuNotFoundErrorCode = -32004;
export const unregisteredZoneErrorCode = -32005;
export const arithmeticDriftErrorCode = -32008;
export const insufficientStockErrorCode = 409;

export const pincodePrefixStateMap: Record<string, string> = {
  "11": "DL",
  "12": "HR",
  "13": "HR",
  "14": "PB",
  "15": "PB",
  "16": "CH",
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
  "74": "WB"
};

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
