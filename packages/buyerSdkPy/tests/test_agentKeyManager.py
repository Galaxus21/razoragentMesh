"""Unit tests for AgentKeyManager, DID minting, and RFC 8785 JCS canonicalization."""

import pytest
from razoragent_buyer_sdk import (
    AgentKeyManager,
    ArithmeticDriftError,
    CryptographicVerificationError,
    InvalidDidError,
    canonicalizeJson,
    extractPublicKeyFromDid,
    formatDid,
    generateKeyPair,
)


def testKeypairGeneration() -> None:
    """Verifies fresh Ed25519 keypair generation and DID minting."""
    manager = AgentKeyManager.generate()
    assert len(manager.getPrivateKeyHex()) == 64
    assert len(manager.getPublicKeyHex()) == 64
    did = manager.getAgentDid()
    assert did.startswith("did:agent:")
    assert len(did) == 74
    assert did == formatDid(manager.getPublicKeyHex())


def testDidFormattingAndExtraction() -> None:
    """Verifies DID format compliance and public key extraction."""
    samplePubHex = "e1bc53c4826b553d077b949bc52579df6480bdf507e15312fb1016be3b1fefc3"
    did = formatDid(samplePubHex)
    assert did == f"did:agent:{samplePubHex}"
    extracted = extractPublicKeyFromDid(did)
    assert extracted == samplePubHex

    with pytest.raises(InvalidDidError):
        extractPublicKeyFromDid("did:other:12345")

    with pytest.raises(InvalidDidError):
        extractPublicKeyFromDid("did:agent:shortkey")


def testDetachedSignatureAndVerification() -> None:
    """Verifies detached Ed25519 signing and verification over canonical bytes."""
    manager = AgentKeyManager.generate()
    payload = {"account": "acc_001", "amountPaise": 50000}
    canonicalBytes = canonicalizeJson(payload)

    signatureHex = manager.signCanonicalBytes(canonicalBytes)
    assert len(signatureHex) == 128

    isValid = AgentKeyManager.verifySignature(manager.getPublicKeyHex(), canonicalBytes, signatureHex)
    assert isValid is True

    # Mutate canonical bytes
    mutatedBytes = canonicalizeJson({"account": "acc_001", "amountPaise": 50001})
    assert AgentKeyManager.verifySignature(manager.getPublicKeyHex(), mutatedBytes, signatureHex) is False

    # Mutate signature
    tamperedSig = signatureHex[:-2] + ("00" if signatureHex[-2:] != "00" else "ff")
    assert AgentKeyManager.verifySignature(manager.getPublicKeyHex(), canonicalBytes, tamperedSig) is False

    with pytest.raises(CryptographicVerificationError):
        AgentKeyManager.verifySignature(manager.getPublicKeyHex(), mutatedBytes, signatureHex, raiseOnFailure=True)


def testJcsPayloadSigningAndDeterminism() -> None:
    """Verifies RFC 8785 JCS canonicalization key-ordering invariance."""
    manager = AgentKeyManager.generate()
    payloadA = {"zebra": 10, "alpha": "test", "nested": {"b": 2, "a": 1}}
    payloadB = {"nested": {"a": 1, "b": 2}, "alpha": "test", "zebra": 10}

    bytesA = canonicalizeJson(payloadA)
    bytesB = canonicalizeJson(payloadB)
    assert bytesA == bytesB

    sigA = manager.signPayload(payloadA)
    sigB = manager.signPayload(payloadB)
    assert sigA == sigB


def testZeroFloatRejection() -> None:
    """Verifies strict rejection of floating-point values in financial payloads."""
    manager = AgentKeyManager.generate()
    payloadWithFloat = {"amount": 42.50, "currency": "INR"}

    with pytest.raises(ArithmeticDriftError):
        canonicalizeJson(payloadWithFloat)

    with pytest.raises(ArithmeticDriftError):
        manager.signPayload(payloadWithFloat)


def testFromSeedAndFromPrivateKeyHex() -> None:
    """Verifies instantiating key manager from raw seed bytes and hex strings."""
    seedBytes = b"\x01" * 32
    managerFromSeed = AgentKeyManager.fromSeed(seedBytes)
    assert len(managerFromSeed.getPublicKeyHex()) == 64

    managerFromHex = AgentKeyManager.fromPrivateKeyHex(managerFromSeed.getPrivateKeyHex())
    assert managerFromHex.getPublicKeyHex() == managerFromSeed.getPublicKeyHex()
    assert managerFromHex.getAgentDid() == managerFromSeed.getAgentDid()

    with pytest.raises(ValueError):
        AgentKeyManager.fromSeed(b"\x01" * 16)

    with pytest.raises(ValueError):
        AgentKeyManager.fromPrivateKeyHex("invalid_hex")
