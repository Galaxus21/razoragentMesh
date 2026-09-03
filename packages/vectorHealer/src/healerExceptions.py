"""Domain exceptions for Layer 3 vector similarity self-healing engine."""


class HealerBaseException(Exception):
    """Base exception for all Layer 3 vector healer errors."""


class NoSubstituteFoundException(HealerBaseException):
    """Raised when no acceptable substitute meets similarity, price, or stock criteria."""


class EmbeddingInferenceException(HealerBaseException):
    """Raised when embedding model inference fails."""


__all__ = [
    "EmbeddingInferenceException",
    "HealerBaseException",
    "NoSubstituteFoundException",
]
