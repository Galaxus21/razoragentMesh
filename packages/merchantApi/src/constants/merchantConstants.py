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
#
# This MUST match the collection scripts/seedCatalog.py writes to. It previously read
# "merchant_products" while the seeder used "razoragent_catalog" -- the only collection that
# exists on a running mesh. Nothing noticed, because no request path ever called the
# vectorizer. Wiring it in with the old value would have put newly published products in a
# second, empty collection where a search over the seeded catalog could never find them.
defaultCollectionName: str = "razoragent_catalog"
defaultVectorDimension: int = 384
# Must be the fully-qualified fastembed name. The bare "all-MiniLM-L6-v2" is rejected by
# fastembed 0.8.0 ("not supported in TextEmbedding"), which the engine caught and silently
# downgraded to character-hash vectors -- so "office chair" ranked an optocoupler first.
# packages/vectorHealer already used the qualified form; only this copy was wrong.
modelNameMiniLm: str = "sentence-transformers/all-MiniLM-L6-v2"
modelNameBgeSmall: str = "BAAI/bge-small-en-v1.5"

# Which producer made an embedding. Cosine over a character hash is meaningless for language,
# so every search response reports this rather than presenting the two as equivalent.
embeddingModeModel: str = "model"
embeddingModeHash: str = "hash"

# Qdrant connection, used to build the client the catalog routes vectorise through.
qdrantHostEnvVar: str = "QDRANT_HOST"
qdrantPortEnvVar: str = "QDRANT_PORT"
defaultQdrantHost: str = "localhost"
defaultQdrantPort: int = 6333
defaultSearchLimit: int = 5
maxSearchLimit: int = 50

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
    "defaultQdrantHost",
    "defaultQdrantPort",
    "defaultSearchLimit",
    "embeddingModeHash",
    "embeddingModeModel",
    "maxSearchLimit",
    "qdrantHostEnvVar",
    "qdrantPortEnvVar",
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
