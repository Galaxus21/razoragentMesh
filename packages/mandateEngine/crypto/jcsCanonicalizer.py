"""RFC 8785 JSON Canonicalization Scheme (JCS) and SHA-256 Hasher."""

import hashlib
import json
from typing import Any
from pydantic import BaseModel

utf8Encoding: str = "utf-8"


def _verifyNoFloats(data: Any) -> None:
    """Recursively validates that no floating-point numbers exist in data structures."""
    if isinstance(data, float):
        from ..settlement.settlementExceptions import ArithmeticDriftException

        raise ArithmeticDriftException(
            f"Floating-point value '{data}' detected: financial payloads must use integer paise"
        )
    if isinstance(data, dict):
        for key, value in data.items():
            _verifyNoFloats(key)
            _verifyNoFloats(value)
        return
    if isinstance(data, (list, tuple, set, frozenset)):
        for item in data:
            _verifyNoFloats(item)
        return
    if isinstance(data, BaseModel):
        _verifyNoFloats(data.model_dump())


def _utf16SortKey(text: str) -> bytes:
    """Sort key that orders a string by UTF-16 code unit, as RFC 8785 requires.

    Python's `sorted()` / `dict` key ordering compares strings by Unicode code point,
    which disagrees with JCS for any astral-plane character (code point > U+FFFF):
    such a character is encoded as a UTF-16 surrogate pair whose high surrogate
    (U+D800-U+DBFF) is numerically *below* the BMP range U+E000-U+FFFF, so it must
    sort earlier under UTF-16 comparison despite having a larger code point. Encoding
    each key to big-endian UTF-16 bytes and comparing those bytes lexicographically
    reproduces that ordering exactly, since every UTF-16 code unit is the same width.
    """
    return text.encode("utf-16-be")


def _normalizeForJcs(data: Any) -> Any:
    """Recursively normalizes data types into JSON-serializable structures, with every
    object's keys pre-sorted by UTF-16 code unit so json.dumps can emit them as-is."""
    if isinstance(data, BaseModel):
        return _normalizeForJcs(data.model_dump())
    if isinstance(data, dict):
        stringKeyedItems = [(str(k), v) for k, v in data.items()]
        stringKeyedItems.sort(key=lambda pair: _utf16SortKey(pair[0]))
        return {k: _normalizeForJcs(v) for k, v in stringKeyedItems}
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
        sort_keys=False,  # keys are already ordered by _normalizeForJcs via _utf16SortKey
        ensure_ascii=False,
    )
    return canonicalString.encode(utf8Encoding)


def computeSha256Digest(canonicalBytes: bytes) -> str:
    """Computes lowercase 64-character hexadecimal SHA-256 digest of bytes."""
    return hashlib.sha256(canonicalBytes).hexdigest()


def canonicalizeAndHash(payload: Any) -> tuple[bytes, str]:
    """Generates canonical UTF-8 bytes and SHA-256 digest simultaneously."""
    canonicalBytes = canonicalizeJson(payload)
    digest = computeSha256Digest(canonicalBytes)
    return canonicalBytes, digest
