"""Exception hierarchy for Layer 0 Ingress Security Shield."""


class IngressSecurityException(Exception):
    """Base exception for all Ingress Security Shield violations."""

    def __init__(self, message: str) -> None:
        super().__init__(message)
        self.message = message


class InvalidSkuIdentifierException(IngressSecurityException):
    """Raised when an SKU ID fails strict format verification."""


class SchemaSanitizationFailureException(IngressSecurityException):
    """Raised when raw catalog data cannot be coerced into a valid schema."""


class ArithmeticDriftException(IngressSecurityException):
    """Raised when monetary or tax arithmetic drift is detected in catalog quote.

    Defined unconditionally, and deliberately so. This used to be a `try: from
    razoragentMesh.packages.mandateEngine import ArithmeticDriftException / except Exception:`
    with this class as the fallback, which meant the class *identity* depended on sys.path: inside
    the monorepo the import succeeded and the name bound to the engine's exception, which does not
    descend from IngressSecurityException; installed standalone (pyproject declares only pydantic)
    the fallback ran and it did.

    The consequence was that a caller writing the documented `except IngressSecurityException`
    caught malformed SKU ids and schema failures but silently let tax drift through -- in the
    monorepo only. Two deployments, two hierarchies, both "working". The engine has its own
    ArithmeticDriftException for its own settlement path; the two are separate exceptions for
    separate layers and are not meant to be the same object.
    """


__all__ = [
    "ArithmeticDriftException",
    "IngressSecurityException",
    "InvalidSkuIdentifierException",
    "SchemaSanitizationFailureException",
]
