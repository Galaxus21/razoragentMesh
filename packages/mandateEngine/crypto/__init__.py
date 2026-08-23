"""Cryptographic utilities and signature verification subpackage."""

from .cryptoKeyUtils import (
    extractPublicKeyFromDid,
    formatDid,
    generateKeyPair,
)
from .ed25519Signer import Ed25519Signer
from .ed25519Verifier import Ed25519Verifier
from .jcsCanonicalizer import (
    canonicalizeAndHash,
    canonicalizeJson,
    computeSha256Digest,
)
from .nonceGenerator import (
    generateNonce,
    generateTimestampedNonce,
)

__all__ = [
    "Ed25519Signer",
    "Ed25519Verifier",
    "canonicalizeAndHash",
    "canonicalizeJson",
    "computeSha256Digest",
    "extractPublicKeyFromDid",
    "formatDid",
    "generateKeyPair",
    "generateNonce",
    "generateTimestampedNonce",
]
