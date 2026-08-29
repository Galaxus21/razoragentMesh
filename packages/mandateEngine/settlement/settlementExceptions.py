"""Comprehensive exception hierarchy for Layer 4 mandate and settlement engine."""


class MandateEngineException(Exception):
    """Base exception for all mandateEngine operations."""

    def __init__(self, message: str) -> None:
        super().__init__(message)
        self.message = message


class ArithmeticDriftException(MandateEngineException):
    """Raised when floating-point math or non-integer paise values are detected."""


class BudgetExceededViolation(MandateEngineException):
    """Raised when requested settlement exceeds delegated budget cap."""


class PaymentBlockedException(MandateEngineException):
    """Raised when payment is blocked by budget gating or validation failure."""


class MandateExpiredException(MandateEngineException):
    """Raised when current time exceeds mandate validity timestamp."""


class ArithmeticEnclaveMismatchException(MandateEngineException):
    """Raised when recomputed enclave arithmetic diverges from mandate amounts."""


class NonceReplayException(MandateEngineException):
    """Raised when an already consumed nonce is submitted (HTTP 409 Conflict)."""


class TimestampExpiredException(MandateEngineException):
    """Raised when request timestamp is older than the NTP drift window (T - 5s)."""


class FutureTimestampException(MandateEngineException):
    """Raised when request timestamp is further in future than NTP drift window (T + 60s)."""


class SignatureVerificationFailedException(MandateEngineException):
    """Raised when an Ed25519 signature fails cryptographic verification."""


class MandateHashChainMismatchException(MandateEngineException):
    """Raised when cryptographic binding H(M_I) or H(M_C) in M_E does not match."""


class CategoryNotAuthorizedException(MandateEngineException):
    """Raised when an item category is not present in delegated authorization list."""


class UnauthorizedAgentException(MandateEngineException):
    """Raised when the agent that signed the ExecutionMandate is not the agent the user
    delegated authority to in the IntentMandate.

    Without this check the delegation is decorative: the verifying key is derived from the DID
    carried inside the mandate itself, so any agent's own signature validates and any observer
    of a signed IntentMandate could spend against it.
    """


class CumulativeBudgetExceededException(MandateEngineException):
    """Raised when cumulative spend recorded against an IntentMandate would exceed its
    maxBudgetPaise ceiling, as distinct from a single transaction exceeding it."""


class CartAlreadySettledException(MandateEngineException):
    """Raised when a CartMandate that has already been settled is presented again.

    The nonce ledger only prevents replaying an identical ExecutionMandate; without this
    guard a buyer can mint a fresh ExecutionMandate (new nonce) against the same signed cart
    and settle it repeatedly.
    """


class InventoryLockExpiredException(MandateEngineException):
    """Raised when settlement is attempted after the cart's inventory reservation has lapsed."""


class SingleTransactionLimitExceededException(MandateEngineException):
    """Raised when transaction amount exceeds delegated single transaction limit."""


class SettlementCompensationTriggeredException(MandateEngineException):
    """Raised when 2PC split transfers fail and saga triggers reverse_transfer rollback."""


class WebhookSignatureVerificationException(MandateEngineException):
    """Raised when Razorpay webhook HMAC-SHA256 signature verification fails."""


class InvalidPincodeException(MandateEngineException):
    """Raised when postal pincode is invalid or cannot map to a GST state code."""
