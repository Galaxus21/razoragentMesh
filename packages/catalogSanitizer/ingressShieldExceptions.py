"""Exception hierarchy for Layer 0 Ingress Security Shield."""


class IngressSecurityException(Exception):
    """Base exception for all Ingress Security Shield violations."""

    def __init__(self, message: str) -> None:
        super().__init__(message)
        self.message = message


class MaliciousPayloadDetectedException(IngressSecurityException):
    """Raised when active exploit patterns or forbidden characters are found."""


class InvalidSkuIdentifierException(IngressSecurityException):
    """Raised when an SKU ID fails strict format verification."""


class SchemaSanitizationFailureException(IngressSecurityException):
    """Raised when raw catalog data cannot be coerced into a valid schema."""
