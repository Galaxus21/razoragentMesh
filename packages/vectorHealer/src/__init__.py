"""Source modules for Layer 3 vector similarity cart self-healing."""

from .constants import (
    defaultGstRatePercent,
    defaultMaxSearchCandidates,
    defaultVectorDimension,
    lockExpiryTtlSeconds,
    maxPriceDeltaPercent,
    minCosineSimilarity,
    modelNameMiniLm,
    qdrantCollectionName,
    reasonInsufficientStock,
    targetSlaMs,
)
from .constraints import (
    ConstraintEvaluationResult,
    NegativeConstraintFilter,
    NegativeConstraintManifest,
)
from .healerExceptions import (
    EmbeddingInferenceException,
    HealerBaseException,
    NoSubstituteFoundException,
)
from .interception import (
    OosInterceptor,
    SelfHealingCartEngine,
)
from .patching import (
    MandatePatcher,
    generateCartDiff,
)
from .search import (
    EmbeddingProvider,
    ScoredPointCandidate,
    VectorSearcher,
)

__all__ = [
    "ConstraintEvaluationResult",
    "EmbeddingInferenceException",
    "EmbeddingProvider",
    "HealerBaseException",
    "MandatePatcher",
    "NegativeConstraintFilter",
    "NegativeConstraintManifest",
    "NoSubstituteFoundException",
    "OosInterceptor",
    "ScoredPointCandidate",
    "SelfHealingCartEngine",
    "VectorSearcher",
    "defaultGstRatePercent",
    "defaultMaxSearchCandidates",
    "defaultVectorDimension",
    "generateCartDiff",
    "lockExpiryTtlSeconds",
    "maxPriceDeltaPercent",
    "minCosineSimilarity",
    "modelNameMiniLm",
    "qdrantCollectionName",
    "reasonInsufficientStock",
    "targetSlaMs",
]
