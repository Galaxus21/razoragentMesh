"""JCS Canonicalization and SHA-256 digest serialization wrapper for gateway compiler."""

import hashlib
import json
from typing import Any
from pydantic import BaseModel


def _normalizeForJcs(data: Any) -> Any:
    """Recursively normalizes data types into JSON-serializable structures."""
    if isinstance(data, BaseModel):
        return _normalizeForJcs(data.model_dump())
    if isinstance(data, dict):
        return {str(k): _normalizeForJcs(v) for k, v in sorted(data.items())}
    if isinstance(data, (list, tuple)):
        return [_normalizeForJcs(item) for item in data]
    return data


def canonicalizeJson(payload: Any) -> bytes:
    """Canonicalizes a dictionary or Pydantic model into deterministic RFC 8785 JCS bytes."""
    normalized = _normalizeForJcs(payload)
    return json.dumps(normalized, separators=(",", ":"), sort_keys=True, ensure_ascii=False).encode("utf-8")


def computeSha256Digest(contentBytes: bytes) -> str:
    """Computes SHA-256 digest in lowercase hexadecimal format."""
    return hashlib.sha256(contentBytes).hexdigest()


__all__ = [
    "canonicalizeJson",
    "computeSha256Digest",
]
