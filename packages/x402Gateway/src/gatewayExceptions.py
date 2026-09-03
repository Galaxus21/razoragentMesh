"""Domain exceptions for Layer 2 x402-INR negotiation gateway."""


class GatewayBaseException(Exception):
    """Base exception for all Layer 2 gateway errors."""


class NonMonotonicConcessionViolation(GatewayBaseException):
    """Raised when buyer or seller attempts a non-monotonic price concession."""


class NegotiationExhaustedException(GatewayBaseException):
    """Raised when max negotiation turns are reached without price convergence."""


class InvalidProofOfWorkException(GatewayBaseException):
    """Raised when client supplies an invalid or incorrect PoW nonce solution."""


class PowChallengeExpiredException(GatewayBaseException):
    """Raised when client PoW challenge token has exceeded TTL window."""


class PowReplayDetectedException(GatewayBaseException):
    """Raised when client attempts to reuse a previously consumed PoW challenge."""


class EscrowSessionNotFoundException(GatewayBaseException):
    """Raised when micro-escrow session token does not exist or has expired."""


class InsufficientEscrowBalanceException(GatewayBaseException):
    """Raised when micro-escrow balance is insufficient for turn micro-metering."""


class UnsafeCallbackUrlException(GatewayBaseException, ValueError):
    """Raised when a webhook callback URL targets a non-HTTPS, private, loopback,
    or link-local address, to prevent server-side request forgery (SSRF).

    Also inherits ValueError so Pydantic field validators can raise it directly
    and have it converted into a 422 response, rather than an unhandled 500.
    """


try:
    from razoragentMesh.packages.mandateEngine import ArithmeticDriftException
except Exception:
    class ArithmeticDriftException(GatewayBaseException):
        """Raised when financial float drift or integer violation is detected."""


__all__ = [
    "ArithmeticDriftException",
    "EscrowSessionNotFoundException",
    "GatewayBaseException",
    "InsufficientEscrowBalanceException",
    "InvalidProofOfWorkException",
    "NegotiationExhaustedException",
    "NonMonotonicConcessionViolation",
    "PowChallengeExpiredException",
    "PowReplayDetectedException",
    "UnsafeCallbackUrlException",
]
