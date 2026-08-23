"""Merchant API constants, configuration defaults, and shared primitives."""

# Network & Server Configuration
merchantApiDefaultPort: int = 4002

# Redis Key Prefixes & Channels
redisCatalogHashKeyPrefix: str = "mesh:catalog:"
redisMerchantPolicyKeyPrefix: str = "mesh:merchant:policy:"
redisCatalogUpdatesChannel: str = "mesh:catalog:updates"
redisSpotRateKeyPrefix: str = "mesh:oracle:spot:"
redisMerchantProfileKeyPrefix: str = "mesh:merchant:profile:"
redisCatalogKeyPrefix: str = "mesh:catalog:"
redisMerchantCatalogPrefix: str = "mesh:catalog:"

# Cache & Quote TTLs (in seconds)
spotRateTtlSeconds: int = 5
defaultQuoteTtlSeconds: int = 60

# Regular Expression Patterns & Identification Formats
gstinRegexPattern: str = r"^[0-9]{2}[A-Z]{5}[0-9]{4}[A-Z]{1}[1-9A-Z]{1}Z[0-9A-Z]{1}$"
pinCodeRegexPattern: str = r"^[1-9][0-9]{5}$"
hsnCodeRegexPattern: str = r"^[0-9]{4,8}$"
razorpayRouteAccountPrefix: str = "acc_"
didMerchantPrefix: str = "did:razoragent:merchant:"
gstCharsTable: str = "0123456789ABCDEFGHIJKLMNOPQRSTUVWXYZ"
gstinLength: int = 15
minRazorpayAccountIdLength: int = 14

# HSN Code Length Limits & Defaults
hsnCodeMinLength: int = 4
hsnCodeMaxLength: int = 8
minHsnCodeLength: int = 4
maxHsnCodeLength: int = 8
defaultHsnCode: str = "6109"
defaultOriginPincode: str = "400001"
defaultCurrency: str = "INR"

# Statutory GST Defaults
defaultGstRatePercent: int = 18
zeroRatedGstPercent: int = 0
jewelryGstRatePercent: int = 3

# Ingestion Batch & Catalog Field Size Limits
maxCsvRowsPerBatch: int = 500
maxSkuTitleLength: int = 150
maxSkuDescriptionLength: int = 500

# PubSub Catalog Update Actions
catalogUpdateActionAdded: str = "CATALOG_ITEM_ADDED"
catalogUpdateActionUpdated: str = "CATALOG_ITEM_UPDATED"
catalogUpdateActionRemoved: str = "CATALOG_ITEM_REMOVED"

# Vector Search & Embedding Configuration
defaultCollectionName: str = "merchant_products"
defaultVectorDimension: int = 384
modelNameMiniLm: str = "all-MiniLM-L6-v2"
modelNameBgeSmall: str = "BAAI/bge-small-en-v1.5"

# Financial Unit Divisors & Zero Paired Primitives
paisePerRupee: int = 100
basisPointsDivisor: int = 10000
percentDivisor: int = 100
zeroPaise: int = 0

__all__ = [
    "basisPointsDivisor",
    "catalogUpdateActionAdded",
    "catalogUpdateActionRemoved",
    "catalogUpdateActionUpdated",
    "defaultCollectionName",
    "defaultCurrency",
    "defaultGstRatePercent",
    "defaultHsnCode",
    "defaultOriginPincode",
    "defaultQuoteTtlSeconds",
    "defaultVectorDimension",
    "didMerchantPrefix",
    "gstCharsTable",
    "gstinLength",
    "gstinRegexPattern",
    "hsnCodeMaxLength",
    "hsnCodeMinLength",
    "hsnCodeRegexPattern",
    "jewelryGstRatePercent",
    "maxCsvRowsPerBatch",
    "maxHsnCodeLength",
    "maxSkuDescriptionLength",
    "maxSkuTitleLength",
    "merchantApiDefaultPort",
    "minHsnCodeLength",
    "minRazorpayAccountIdLength",
    "modelNameBgeSmall",
    "modelNameMiniLm",
    "paisePerRupee",
    "percentDivisor",
    "pinCodeRegexPattern",
    "razorpayRouteAccountPrefix",
    "redisCatalogHashKeyPrefix",
    "redisCatalogKeyPrefix",
    "redisCatalogUpdatesChannel",
    "redisMerchantCatalogPrefix",
    "redisMerchantPolicyKeyPrefix",
    "redisMerchantProfileKeyPrefix",
    "redisSpotRateKeyPrefix",
    "spotRateTtlSeconds",
    "zeroPaise",
    "zeroRatedGstPercent",
]
