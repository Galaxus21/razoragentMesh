"""Merchant API constants, configuration defaults, and shared primitives."""

# Network & Server Configuration
merchantApiDefaultPort: int = 4002

# Application & API Metadata
defaultApiTitle: str = "RazorAgent Merchant API"
defaultApiVersion: str = "2.0.0"

# Redis Key Prefixes & Channels
inventoryStockPrefix: str = "inventory:stock:"
merchantKeypairPrefix: str = "mesh:merchant:keypair:"
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

# Vertical & Category Defaults
defaultVerticalApparel: str = "apparel"
defaultVerticalGeneral: str = "general"
defaultVerticalFmcg: str = "fmcg"
defaultVerticalJewelry: str = "jewelry"
defaultVerticalPharma: str = "pharma"

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

# Financial Unit Divisors & Rate Limits
paisePerRupee: int = 100
basisPointsDivisor: int = 10000
percentDivisor: int = 100
zeroPaise: int = 0
rateLimitBurst1000: int = 1000
rateLimitMax100M: int = 100000000

__all__ = [
    "basisPointsDivisor",
    "catalogUpdateActionAdded",
    "catalogUpdateActionRemoved",
    "catalogUpdateActionUpdated",
    "defaultApiTitle",
    "defaultApiVersion",
    "defaultCollectionName",
    "defaultCurrency",
    "defaultGstRatePercent",
    "defaultHsnCode",
    "defaultOriginPincode",
    "defaultQuoteTtlSeconds",
    "defaultVectorDimension",
    "defaultVerticalApparel",
    "defaultVerticalFmcg",
    "defaultVerticalGeneral",
    "defaultVerticalJewelry",
    "defaultVerticalPharma",
    "didMerchantPrefix",
    "gstCharsTable",
    "gstinLength",
    "gstinRegexPattern",
    "hsnCodeMaxLength",
    "hsnCodeMinLength",
    "hsnCodeRegexPattern",
    "inventoryStockPrefix",
    "jewelryGstRatePercent",
    "maxCsvRowsPerBatch",
    "maxHsnCodeLength",
    "maxSkuDescriptionLength",
    "maxSkuTitleLength",
    "merchantApiDefaultPort",
    "merchantKeypairPrefix",
    "minHsnCodeLength",
    "minRazorpayAccountIdLength",
    "modelNameBgeSmall",
    "modelNameMiniLm",
    "paisePerRupee",
    "percentDivisor",
    "pinCodeRegexPattern",
    "rateLimitBurst1000",
    "rateLimitMax100M",
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
