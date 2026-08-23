"""JCS Canonicalization and SHA-256 digest serialization wrapper for gateway compiler."""

from typing import Any
from razoragentMesh.packages.mandateEngine.crypto.jcsCanonicalizer import (
    canonicalizeJson as mandateCanonicalizeJson,
    computeSha256Digest as mandateComputeSha256Digest,
)


def canonicalizeJson(payload: Any) -> bytes:
    """Canonicalizes a dictionary or Pydantic model into deterministic RFC 8785 JCS bytes."""
    return mandateCanonicalizeJson(payload)


def computeSha256Digest(contentBytes: bytes) -> str:
    """Computes SHA-256 digest in lowercase hexadecimal format."""
    return mandateComputeSha256Digest(contentBytes)


__all__ = [
    "canonicalizeJson",
    "computeSha256Digest",
]
