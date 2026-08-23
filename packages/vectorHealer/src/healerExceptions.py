"""Domain exceptions for Layer 3 vector similarity self-healing engine."""


class HealerBaseException(Exception):
    """Base exception for all Layer 3 vector healer errors."""


class NoSubstituteFoundException(HealerBaseException):
    """Raised when no acceptable substitute meets similarity, price, or stock criteria."""


class ConstraintViolationException(HealerBaseException):
    """Raised when candidate substitute violates buyer's negative constraint manifest."""


class AllergenConstraintViolation(ConstraintViolationException):
    """Raised when candidate contains blacklisted allergen."""


class BrandExclusionViolation(ConstraintViolationException):
    """Raised when candidate belongs to blacklisted brand."""


class WeightLimitExceededViolation(ConstraintViolationException):
    """Raised when candidate weight exceeds maximum allowed threshold."""


class DimensionLimitExceededViolation(ConstraintViolationException):
    """Raised when candidate physical dimensions exceed maximum bounds."""


class SlaExceededViolation(ConstraintViolationException):
    """Raised when candidate delivery SLA exceeds maximum allowed hours."""


class EmbeddingInferenceException(HealerBaseException):
    """Raised when embedding model inference fails."""


class MandatePatchingException(HealerBaseException):
    """Raised when generating or dual-signing amended mandate fails."""


__all__ = [
    "AllergenConstraintViolation",
    "BrandExclusionViolation",
    "ConstraintViolationException",
    "DimensionLimitExceededViolation",
    "EmbeddingInferenceException",
    "HealerBaseException",
    "MandatePatchingException",
    "NoSubstituteFoundException",
    "SlaExceededViolation",
    "WeightLimitExceededViolation",
]
