"""Constants for Layer 3 vector similarity self-healing engine."""

# Search & Similarity Thresholds
minCosineSimilarity: float = 0.85
maxPriceDeltaPercent: float = 5.0
targetSlaMs: float = 300.0

# Vector Embedding Configuration
defaultVectorDimension: int = 384
modelNameMiniLm: str = "sentence-transformers/all-MiniLM-L6-v2"
# MUST equal merchantApi/src/constants/merchantConstants.py:defaultCollectionName, which is
# what AutoVectorizer.upsertListing actually writes to. This said "merchantCatalog" and
# nothing has ever written a collection by that name, so every Layer 3 search queried a
# collection that did not exist and found nothing -- the reason no OOS_HEALED has ever been
# published by a real heal. Measured 2026-09-04 against the running stack.
qdrantCollectionName: str = "razoragent_catalog"

# Amendment Metadata & Codes
reasonInsufficientStock: str = "INSUFFICIENT_STOCK_OOS_HEALED"
defaultGstRatePercent: int = 18
defaultFallbackHsnCode: str = "8471"
defaultMaxSearchCandidates: int = 5
lockExpiryTtlSeconds: int = 60
millisecondsPerSecond: float = 1000.0

__all__ = [
    "defaultFallbackHsnCode",
    "defaultGstRatePercent",
    "defaultMaxSearchCandidates",
    "defaultVectorDimension",
    "lockExpiryTtlSeconds",
    "maxPriceDeltaPercent",
    "millisecondsPerSecond",
    "minCosineSimilarity",
    "modelNameMiniLm",
    "qdrantCollectionName",
    "reasonInsufficientStock",
    "targetSlaMs",
]

