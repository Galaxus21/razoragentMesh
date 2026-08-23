"""Unit tests for RFC 8785 JCS Canonicalization and SHA-256 Hasher."""

import pytest
from razoragentMesh.packages.mandateEngine.jcsCanonicalizer import (
    canonicalizeAndHash,
    canonicalizeJson,
    computeSha256Digest,
)
from razoragentMesh.packages.mandateEngine.settlementExceptions import (
    ArithmeticDriftException,
)


def testCanonicalizeKeySorting() -> None:
    """Verifies deterministic sorting of object keys."""
    unsortedObj = {"z": 100, "a": 200, "m": 300}
    canonicalBytes = canonicalizeJson(unsortedObj)
    assert canonicalBytes == b'{"a":200,"m":300,"z":100}'


def testCanonicalizeNestedStructures() -> None:
    """Verifies recursive sorting in nested dicts and lists."""
    nestedObj = {
        "items": [{"skuId": "SKU-2", "qty": 1}, {"skuId": "SKU-1", "qty": 5}],
        "cartId": "CART-123",
    }
    canonicalBytes = canonicalizeJson(nestedObj)
    assert canonicalBytes == b'{"cartId":"CART-123","items":[{"qty":1,"skuId":"SKU-2"},{"qty":5,"skuId":"SKU-1"}]}'


def testCanonicalizeRejectsFloats() -> None:
    """Verifies immediate rejection of any floating point numbers in payload."""
    payloadWithFloat = {"amountPaise": 1976.50}
    with pytest.raises(ArithmeticDriftException):
        canonicalizeJson(payloadWithFloat)

    payloadWithNestedFloat = {"data": {"items": [1, 2, 3.14]}}
    with pytest.raises(ArithmeticDriftException):
        canonicalizeJson(payloadWithNestedFloat)


def testCanonicalizeAndHash() -> None:
    """Verifies deterministic SHA-256 digest calculation."""
    payload = {"currency": "INR", "totalPaise": 420000}
    canonicalBytes, digest = canonicalizeAndHash(payload)
    assert isinstance(canonicalBytes, bytes)
    assert isinstance(digest, str)
    assert len(digest) == 64
    assert computeSha256Digest(canonicalBytes) == digest
