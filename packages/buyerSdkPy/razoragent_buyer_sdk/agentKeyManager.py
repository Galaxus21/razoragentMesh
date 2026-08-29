"""PyNaCl Ed25519 Key Management, DID Minting, and RFC 8785 JCS Canonicalization."""

import hashlib
import json
from typing import Any, Optional, Tuple
import nacl.exceptions
import nacl.signing
from pydantic import BaseModel

from .constants import (
    didPrefix,
    keyHexLength,
    signatureHexLength,
    utf8Encoding,
)
from .exceptions import (
    ArithmeticDriftError,
    CryptographicVerificationError,
    InvalidDidError,
)
from .models import AgentKeypair


def _verifyNoFloats(data: Any) -> None:
    """Recursively validates that no floating-point numbers exist in data structures."""
    if isinstance(data, float):
        raise ArithmeticDriftError(
            f"Floating-point value '{data}' detected: financial payloads must strictly use integer paise"
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


def canonicalizeAndHash(payload: Any) -> Tuple[bytes, str]:
    """Generates canonical UTF-8 bytes and SHA-256 digest simultaneously."""
    canonicalBytes = canonicalizeJson(payload)
    digest = computeSha256Digest(canonicalBytes)
    return canonicalBytes, digest


def formatDid(publicKeyHex: str) -> str:
    """Formats a 32-byte public key hex into a standardized DID identifier."""
    return f"{didPrefix}{publicKeyHex.lower()}"


def extractPublicKeyFromDid(did: str) -> str:
    """Extracts raw hexadecimal public key from a DID identifier."""
    if not isinstance(did, str) or not did.startswith(didPrefix):
        raise InvalidDidError(f"Invalid DID format: '{did}', expected prefix '{didPrefix}'")
    publicKeyHex = did[len(didPrefix):].strip().lower()
    if len(publicKeyHex) != keyHexLength:
        raise InvalidDidError(
            f"Invalid public key length in DID: expected {keyHexLength} hex chars, got {len(publicKeyHex)}"
        )
    return publicKeyHex


def generateKeyPair() -> Tuple[str, str]:
    """Generates a fresh 32-byte Ed25519 signing keypair in hexadecimal format."""
    signingKey = nacl.signing.SigningKey.generate()
    privateKeyHex = signingKey.encode().hex().lower()
    publicKeyHex = signingKey.verify_key.encode().hex().lower()
    return privateKeyHex, publicKeyHex


class AgentKeyManager:
    """Asymmetric Ed25519 key manager producing RFC 8785 detached signatures and DIDs."""

    def __init__(self, privateKeyHex: str) -> None:
        cleanedHex = privateKeyHex.strip().lower() if isinstance(privateKeyHex, str) else ""
        if len(cleanedHex) != keyHexLength:
            raise ValueError(f"privateKeyHex must be a {keyHexLength}-character hexadecimal string")
        self._signingKey = nacl.signing.SigningKey(bytes.fromhex(cleanedHex))
        self._privateKeyHex = cleanedHex
        self._publicKeyHex = self._signingKey.verify_key.encode().hex().lower()
        self._agentDid = formatDid(self._publicKeyHex)

    @classmethod
    def generate(cls) -> "AgentKeyManager":
        """Generates a new random Ed25519 keypair and wraps it in an AgentKeyManager."""
        privateHex, _ = generateKeyPair()
        return cls(privateHex)

    @classmethod
    def generateKeypair(cls) -> "AgentKeyManager":
        """Alias for generate() for API compatibility."""
        return cls.generate()

    @classmethod
    def fromPrivateKeyHex(cls, privateKeyHex: str) -> "AgentKeyManager":
        """Instantiates AgentKeyManager from a 64-character hexadecimal private key string."""
        return cls(privateKeyHex)

    @classmethod
    def fromSeed(cls, seedBytes: bytes) -> "AgentKeyManager":
        """Instantiates AgentKeyManager from 32 raw seed bytes."""
        if len(seedBytes) != 32:
            raise ValueError(f"seedBytes must be exactly 32 bytes, got {len(seedBytes)}")
        return cls(seedBytes.hex())

    def getPrivateKeyHex(self) -> str:
        """Returns the private key as a 64-character lowercase hex string."""
        return self._privateKeyHex

    def getPublicKeyHex(self) -> str:
        """Returns the public key as a 64-character lowercase hex string."""
        return self._publicKeyHex

    def getAgentDid(self) -> str:
        """Returns the standardized DID identifier (did:agent:<hex64>)."""
        return self._agentDid

    def getKeypair(self) -> AgentKeypair:
        """Returns an immutable AgentKeypair model."""
        return AgentKeypair(
            privateKeyHex=self._privateKeyHex,
            publicKeyHex=self._publicKeyHex,
            agentDid=self._agentDid,
        )

    def signCanonicalBytes(self, canonicalBytes: bytes) -> str:
        """Generates a 64-byte (128 hex character) detached Ed25519 signature."""
        signedObject = self._signingKey.sign(canonicalBytes)
        return signedObject.signature.hex().lower()

    def signPayload(self, payload: Any) -> str:
        """Canonicalizes payload using JCS and returns the detached signature hex."""
        canonicalBytes = canonicalizeJson(payload)
        return self.signCanonicalBytes(canonicalBytes)

    @staticmethod
    def verifySignature(
        publicKeyHex: str,
        canonicalBytes: bytes,
        signatureHex: str,
        raiseOnFailure: bool = False,
    ) -> bool:
        """Verifies detached Ed25519 signature against canonical bytes."""
        cleanedPub = publicKeyHex.strip().lower()
        cleanedSig = signatureHex.strip().lower()
        if len(cleanedPub) != keyHexLength or len(cleanedSig) != signatureHexLength:
            if raiseOnFailure:
                raise CryptographicVerificationError("Invalid public key or signature hex length")
            return False

        try:
            verifyKey = nacl.signing.VerifyKey(bytes.fromhex(cleanedPub))
            verifyKey.verify(canonicalBytes, bytes.fromhex(cleanedSig))
            return True
        except (nacl.exceptions.BadSignatureError, nacl.exceptions.CryptoError, ValueError) as err:
            if raiseOnFailure:
                raise CryptographicVerificationError(f"Ed25519 signature verification failed: {err}") from err
            return False

    @classmethod
    def verifyPayloadSignature(
        cls,
        publicKeyHex: str,
        payload: Any,
        signatureHex: str,
        raiseOnFailure: bool = False,
    ) -> bool:
        """Canonicalizes payload using JCS and verifies the detached Ed25519 signature."""
        canonicalBytes = canonicalizeJson(payload)
        return cls.verifySignature(publicKeyHex, canonicalBytes, signatureHex, raiseOnFailure=raiseOnFailure)


__all__ = [
    "AgentKeyManager",
    "canonicalizeAndHash",
    "canonicalizeJson",
    "computeSha256Digest",
    "extractPublicKeyFromDid",
    "formatDid",
    "generateKeyPair",
]
