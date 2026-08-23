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
    AllergenConstraintViolation,
    BrandExclusionViolation,
    ConstraintViolationException,
    DimensionLimitExceededViolation,
    EmbeddingInferenceException,
    HealerBaseException,
    MandatePatchingException,
    NoSubstituteFoundException,
    SlaExceededViolation,
    WeightLimitExceededViolation,
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
    "AllergenConstraintViolation",
    "BrandExclusionViolation",
    "ConstraintEvaluationResult",
    "ConstraintViolationException",
    "DimensionLimitExceededViolation",
    "EmbeddingInferenceException",
    "EmbeddingProvider",
    "HealerBaseException",
    "MandatePatcher",
    "MandatePatchingException",
    "NegativeConstraintFilter",
    "NegativeConstraintManifest",
    "NoSubstituteFoundException",
    "OosInterceptor",
    "ScoredPointCandidate",
    "SelfHealingCartEngine",
    "SlaExceededViolation",
    "VectorSearcher",
    "WeightLimitExceededViolation",
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
