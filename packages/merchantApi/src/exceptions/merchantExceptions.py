"""Domain exceptions for Merchant Ingestion API."""


class MerchantApiException(Exception):
    """Base domain exception for merchant API operations."""

    def __init__(self, message: str, statusCode: int = 400) -> None:
        super().__init__(message)
        self.message = message
        self.statusCode = statusCode


class InvalidGstinException(MerchantApiException):
    """Raised when GSTIN format or checksum validation fails."""

    def __init__(self, message: str = "Invalid Indian GSTIN format or checksum") -> None:
        super().__init__(message=message, statusCode=400)


class InvalidRazorpayAccountException(MerchantApiException):
    """Raised when Razorpay Route account ID format is invalid."""

    def __init__(self, message: str = "Invalid Razorpay Route account ID format") -> None:
        super().__init__(message=message, statusCode=400)


class CatalogNotFoundException(MerchantApiException):
    """Raised when a SKU is not found in the merchant catalog."""

    def __init__(self, message: str) -> None:
        super().__init__(message=message, statusCode=404)


class PolicyNotFoundException(MerchantApiException):
    """Raised when negotiation policy is not configured for a merchant."""

    def __init__(self, message: str) -> None:
        super().__init__(message=message, statusCode=404)


class PolicyConflictException(MerchantApiException):
    """Raised when negotiation policy parameters conflict."""

    def __init__(self, message: str = "Policy conflict detected") -> None:
        super().__init__(message=message, statusCode=409)


class BulkIngestionException(MerchantApiException):
    """Raised when bulk CSV, Shopify, or ERP ingestion fails."""

    def __init__(self, message: str) -> None:
        super().__init__(message=message, statusCode=400)


class MerchantStorageUnavailableException(MerchantApiException):
    """Raised when Redis or storage backend is unavailable."""

    def __init__(self, message: str = "Redis storage service is unavailable") -> None:
        super().__init__(message=message, statusCode=503)


__all__ = [
    "BulkIngestionException",
    "CatalogNotFoundException",
    "InvalidGstinException",
    "InvalidRazorpayAccountException",
    "MerchantApiException",
    "MerchantStorageUnavailableException",
    "PolicyConflictException",
    "PolicyNotFoundException",
]
