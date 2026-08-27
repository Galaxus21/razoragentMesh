"""Constants for Layer 3 vector similarity self-healing engine."""

# Search & Similarity Thresholds
minCosineSimilarity: float = 0.85
maxPriceDeltaPercent: float = 5.0
targetSlaMs: float = 300.0

# Vector Embedding Configuration
defaultVectorDimension: int = 384
modelNameMiniLm: str = "sentence-transformers/all-MiniLM-L6-v2"
qdrantCollectionName: str = "merchantCatalog"

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

