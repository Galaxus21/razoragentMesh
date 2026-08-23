"""PyNaCl Ed25519 cryptographic signature verifier."""

from typing import Any
import nacl.exceptions
import nacl.signing

from razoragentMesh.packages.mandateEngine.jcsCanonicalizer import canonicalizeJson
from razoragentMesh.packages.mandateEngine.settlementExceptions import (
    SignatureVerificationFailedException,
)


class Ed25519Verifier:
    """Validates Ed25519 signatures over RFC 8785 canonical payloads."""

    @staticmethod
    def verifySignature(
        publicKeyHex: str,
        canonicalBytes: bytes,
        signatureHex: str,
        raiseOnFailure: bool = False,
    ) -> bool:
        """Verifies Ed25519 detached signature against raw canonical bytes."""
        if len(publicKeyHex.strip()) != 64 or len(signatureHex.strip()) != 128:
            if raiseOnFailure:
                raise SignatureVerificationFailedException("Invalid key or signature length")
            return False

        try:
            verifyKey = nacl.signing.VerifyKey(bytes.fromhex(publicKeyHex.strip()))
            verifyKey.verify(canonicalBytes, bytes.fromhex(signatureHex.strip()))
            return True
        except (nacl.exceptions.BadSignatureError, ValueError) as err:
            if raiseOnFailure:
                raise SignatureVerificationFailedException(
                    f"Ed25519 signature verification failed: {str(err)}"
                ) from err
            return False

    @classmethod
    def verifyPayloadSignature(
        cls,
        publicKeyHex: str,
        payload: Any,
        signatureHex: str,
        raiseOnFailure: bool = False,
    ) -> bool:
        """Canonicalizes payload using JCS and verifies the detached signature."""
        canonicalBytes = canonicalizeJson(payload)
        return cls.verifySignature(
            publicKeyHex=publicKeyHex,
            canonicalBytes=canonicalBytes,
            signatureHex=signatureHex,
            raiseOnFailure=raiseOnFailure,
        )
