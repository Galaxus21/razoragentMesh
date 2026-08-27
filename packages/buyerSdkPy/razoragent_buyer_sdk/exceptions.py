"""Exception hierarchy for RazorAgent Buyer SDK."""

from typing import Optional


class BuyerSdkError(Exception):
    """Base exception for all RazorAgent Buyer SDK errors."""

    def __init__(self, message: str, details: Optional[dict] = None) -> None:
        super().__init__(message)
        self.message = message
        self.details = details or {}


class MandateValidationError(BuyerSdkError):
    """Raised when an AP2 mandate violates schema constraints or business invariants."""
    pass


class CryptographicVerificationError(BuyerSdkError):
    """Raised when an Ed25519 signature verification fails."""
    pass


class InvalidDidError(BuyerSdkError):
    """Raised when an agent or user DID format is invalid."""
    pass


class MandateHashMismatchError(BuyerSdkError):
    """Raised when an ExecutionMandate hash does not match the referenced mandate."""
    pass


class PowSolverError(BuyerSdkError):
    """Raised when a Proof-of-Work challenge cannot be solved or is invalid."""
    pass


class NetworkClientError(BuyerSdkError):
    """Raised when an HTTP transport error or unexpected status code occurs."""

    def __init__(self, message: str, statusCode: Optional[int] = None, details: Optional[dict] = None) -> None:
        super().__init__(message, details)
        self.statusCode = statusCode


class SettlementError(BuyerSdkError):
    """Raised when 2PC settlement saga fails or is rejected by gateway."""

    def __init__(self, message: str, statusCode: Optional[int] = None, details: Optional[dict] = None) -> None:
        super().__init__(message, details)
        self.statusCode = statusCode


class Http402RequiredError(BuyerSdkError):
    """Raised when HTTP 402 Payment Required challenge is returned."""

    def __init__(self, message: str, challengeToken: Optional[str] = None, difficulty: Optional[int] = None) -> None:
        super().__init__(message, {"challengeToken": challengeToken, "difficulty": difficulty})
        self.challengeToken = challengeToken
        self.difficulty = difficulty


class InsufficientEscrowError(BuyerSdkError):
    """Raised when micro-escrow balance is insufficient for negotiation turn."""
    pass


class ArithmeticDriftError(BuyerSdkError):
    """Raised when floating-point drift or non-integer financial paise is detected."""
    pass


# Compatibility Aliases
BuyerSdkException = BuyerSdkError
MandateValidationException = MandateValidationError
CryptographicVerificationException = CryptographicVerificationError
InvalidDidException = InvalidDidError
MandateHashChainMismatchException = MandateHashMismatchError
MandateHashMismatchException = MandateHashMismatchError
ProofOfWorkException = PowSolverError
SettlementExecutionException = SettlementError
ArithmeticDriftException = ArithmeticDriftError
InsufficientEscrowException = InsufficientEscrowError
Http402RequiredException = Http402RequiredError

__all__ = [
    "ArithmeticDriftError",
    "ArithmeticDriftException",
    "BuyerSdkError",
    "BuyerSdkException",
    "CryptographicVerificationError",
    "CryptographicVerificationException",
    "Http402RequiredError",
    "Http402RequiredException",
    "InsufficientEscrowError",
    "InsufficientEscrowException",
    "InvalidDidError",
    "InvalidDidException",
    "MandateHashChainMismatchException",
    "MandateHashMismatchError",
    "MandateHashMismatchException",
    "MandateValidationError",
    "MandateValidationException",
    "NetworkClientError",
    "PowSolverError",
    "ProofOfWorkException",
    "SettlementError",
    "SettlementExecutionException",
]
