"""Unit tests for PyNaCl Ed25519 asymmetric cryptography."""

import pytest
from razoragentMesh.packages.mandateEngine.crypto.cryptoKeyUtils import (
    extractPublicKeyFromDid,
    formatDid,
    generateKeyPair,
)
from razoragentMesh.packages.mandateEngine.crypto.ed25519Signer import Ed25519Signer
from razoragentMesh.packages.mandateEngine.crypto.ed25519Verifier import Ed25519Verifier
from razoragentMesh.packages.mandateEngine.settlement.settlementExceptions import (
    SignatureVerificationFailedException,
)


def testKeyPairGenerationAndDid() -> None:
    """Verifies generation of 32-byte Ed25519 keypairs and DID formatting."""
    privateKeyHex, publicKeyHex = generateKeyPair()
    assert len(privateKeyHex) == 64
    assert len(publicKeyHex) == 64

    did = formatDid(publicKeyHex)
    assert did.startswith("did:agent:")
    assert extractPublicKeyFromDid(did) == publicKeyHex


def testSigningAndVerificationRoundTrip() -> None:
    """Verifies that an Ed25519 signature verified against the public key succeeds."""
    privateKeyHex, publicKeyHex = generateKeyPair()
    signer = Ed25519Signer(privateKeyHex)
    assert signer.getPublicKeyHex() == publicKeyHex

    testPayload = {"mandateId": "M-100", "amountPaise": 50000}
    signatureHex = signer.signPayload(testPayload)
    assert len(signatureHex) == 128

    isValid = Ed25519Verifier.verifyPayloadSignature(
        publicKeyHex=publicKeyHex,
        payload=testPayload,
        signatureHex=signatureHex,
    )
    assert isValid is True


def testTamperedPayloadFailsVerification() -> None:
    """Verifies that tampering with signed payload invalidates signature."""
    privateKeyHex, publicKeyHex = generateKeyPair()
    signer = Ed25519Signer(privateKeyHex)

    originalPayload = {"mandateId": "M-100", "amountPaise": 50000}
    signatureHex = signer.signPayload(originalPayload)

    tamperedPayload = {"mandateId": "M-100", "amountPaise": 99999}
    isValid = Ed25519Verifier.verifyPayloadSignature(
        publicKeyHex=publicKeyHex,
        payload=tamperedPayload,
        signatureHex=signatureHex,
    )
    assert isValid is False

    with pytest.raises(SignatureVerificationFailedException):
        Ed25519Verifier.verifyPayloadSignature(
            publicKeyHex=publicKeyHex,
            payload=tamperedPayload,
            signatureHex=signatureHex,
            raiseOnFailure=True,
        )
