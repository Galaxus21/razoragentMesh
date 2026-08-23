"""Layer 3: vectorHealer Package - Sub-300ms Vector Similarity Cart Self-Healing."""

from .src.constants import (
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
from .src.constraints import (
    ConstraintEvaluationResult,
    NegativeConstraintFilter,
    NegativeConstraintManifest,
)
from .src.healerExceptions import (
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
from .src.interception import (
    OosInterceptor,
    SelfHealingCartEngine,
)
from .src.patching import (
    MandatePatcher,
    generateCartDiff,
)
from .src.search import (
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
