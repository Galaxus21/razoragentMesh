"""RFC 8785 JSON Canonicalization Scheme (JCS) and SHA-256 Hasher."""

import hashlib
import json
from typing import Any
from pydantic import BaseModel

from razoragentMesh.packages.mandateEngine.settlementExceptions import (
    ArithmeticDriftException,
)


def _verifyNoFloats(data: Any) -> None:
    """Recursively validates that no floating-point numbers exist in data structures."""
    if isinstance(data, float):
        raise ArithmeticDriftException(
            f"Floating-point value '{data}' detected: financial payloads must use integer paise"
        )
    if isinstance(data, dict):
        for key, value in data.items():
            _verifyNoFloats(key)
            _verifyNoFloats(value)
    elif isinstance(data, (list, tuple, set, frozenset)):
        for item in data:
            _verifyNoFloats(item)
    elif isinstance(data, BaseModel):
        _verifyNoFloats(data.model_dump())


def _normalizeForJcs(data: Any) -> Any:
    """Recursively normalizes data types into JSON-serializable structures."""
    if isinstance(data, BaseModel):
        return _normalizeForJcs(data.model_dump())
    if isinstance(data, dict):
        return {str(k): _normalizeForJcs(v) for k, v in data.items()}
    if isinstance(data, (list, tuple)):
        return [_normalizeForJcs(item) for item in data]
    if isinstance(data, (set, frozenset)):
        return sorted([_normalizeForJcs(item) for item in data])
    return data


def canonicalizeJson(payload: Any) -> bytes:
    """Serializes arbitrary payload into deterministic RFC 8785 canonical UTF-8 bytes."""
    _verifyNoFloats(payload)
    normalized = _normalizeForJcs(payload)
    canonicalString = json.dumps(
        normalized,
        separators=(",", ":"),
        sort_keys=True,
        ensure_ascii=False,
    )
    return canonicalString.encode("utf-8")


def computeSha256Digest(canonicalBytes: bytes) -> str:
    """Computes lowercase 64-character hexadecimal SHA-256 digest of bytes."""
    return hashlib.sha256(canonicalBytes).hexdigest()


def canonicalizeAndHash(payload: Any) -> tuple[bytes, str]:
    """Generates canonical UTF-8 bytes and SHA-256 digest simultaneously."""
    canonicalBytes = canonicalizeJson(payload)
    digest = computeSha256Digest(canonicalBytes)
    return canonicalBytes, digest
