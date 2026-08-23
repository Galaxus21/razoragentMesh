"""PyNaCl Ed25519 cryptographic signature verifier."""

from typing import Any
import nacl.exceptions
import nacl.signing

publicKeyHexLength: int = 64
signatureHexLength: int = 128


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
        if len(publicKeyHex.strip()) != publicKeyHexLength or len(signatureHex.strip()) != signatureHexLength:
            if raiseOnFailure:
                from ..settlement.settlementExceptions import (
                    SignatureVerificationFailedException,
                )

                raise SignatureVerificationFailedException("Invalid key or signature length")
            return False

        try:
            verifyKey = nacl.signing.VerifyKey(bytes.fromhex(publicKeyHex.strip()))
            verifyKey.verify(canonicalBytes, bytes.fromhex(signatureHex.strip()))
            return True
        except (nacl.exceptions.BadSignatureError, ValueError) as err:
            if raiseOnFailure:
                from ..settlement.settlementExceptions import (
                    SignatureVerificationFailedException,
                )

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
        from .jcsCanonicalizer import canonicalizeJson

        canonicalBytes = canonicalizeJson(payload)
        return cls.verifySignature(
            publicKeyHex=publicKeyHex,
            canonicalBytes=canonicalBytes,
            signatureHex=signatureHex,
            raiseOnFailure=raiseOnFailure,
        )
