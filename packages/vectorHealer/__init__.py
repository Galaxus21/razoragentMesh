"""Layer 3: vectorHealer Package - Sub-300ms Vector Similarity Cart Self-Healing."""

from razoragentMesh.packages.vectorHealer.constraintFilter import (
    ConstraintEvaluationResult,
    NegativeConstraintFilter,
    NegativeConstraintManifest,
)
from razoragentMesh.packages.vectorHealer.embeddingProvider import (
    EmbeddingProvider,
)
from razoragentMesh.packages.vectorHealer.healerConstants import (
    defaultGstRatePercent,
    defaultVectorDimension,
    maxPriceDeltaPercent,
    minCosineSimilarity,
    modelNameMiniLm,
    qdrantCollectionName,
    reasonInsufficientStock,
    targetSlaMs,
)
from razoragentMesh.packages.vectorHealer.healerExceptions import (
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
from razoragentMesh.packages.vectorHealer.mandatePatcher import (
    MandatePatcher,
)
from razoragentMesh.packages.vectorHealer.oosInterceptor import (
    OosInterceptor,
    SelfHealingCartEngine,
)
from razoragentMesh.packages.vectorHealer.vectorSearcher import (
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
    "defaultVectorDimension",
    "maxPriceDeltaPercent",
    "minCosineSimilarity",
    "modelNameMiniLm",
    "qdrantCollectionName",
    "reasonInsufficientStock",
    "targetSlaMs",
]
