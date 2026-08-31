"""Adversarial stress tests for AgentKeyManager and JCS canonicalization."""

from typing import Any
import pytest
import nacl.signing
from pydantic import BaseModel
from razoragent_buyer_sdk import (
    AgentKeyManager,
    ArithmeticDriftError,
    CryptographicVerificationError,
    InvalidDidError,
    canonicalizeAndHash,
    canonicalizeJson,
    computeSha256Digest,
    extractPublicKeyFromDid,
    formatDid,
    generateKeyPair,
)


class SampleNestedModel(BaseModel):
    """Pydantic model for float and type validation tests."""
    fieldInt: int
    fieldStr: str
    fieldFloat: float = 0.0


class SampleValidModel(BaseModel):
    """Pydantic model with strict integer paise."""
    amountPaise: int
    currency: str


def _assertFloatRaises(val: Any) -> None:
    with pytest.raises(ArithmeticDriftError):
        canonicalizeJson(val)


def testFloatInjectionInNestedStructures() -> None:
    """Stress tests recursive float rejection across diverse container types."""
    cases = [
        42.5, -0.01, 0.0, float("inf"), float("nan"),
        {"level1": {"level2": {"badFloat": 10.5}}},
        {"items": [100, 200, 300.5]},
        {"data": (1, 2, 3.14)},
        {"keys": {10, 20.0, 30}},
        {"keys": frozenset([1, 2.5, 3])},
        SampleNestedModel(fieldInt=10, fieldStr="test", fieldFloat=1.5),
    ]
    for case in cases:
        _assertFloatRaises(case)



def testJcsDeterminismWithComplexTypes() -> None:
    """Verifies deterministic canonicalization for complex types and keys."""
    # Dict key sorting
    payloadUnsorted = {"z": 1, "a": 2, "m": {"y": 10, "b": 20}}
    payloadSorted = {"a": 2, "m": {"b": 20, "y": 10}, "z": 1}
    assert canonicalizeJson(payloadUnsorted) == canonicalizeJson(payloadSorted)

    # Integer keys are stringified and sorted lexicographically
    intKeysDict = {100: "hundred", 20: "twenty", 3: "three"}
    cBytes = canonicalizeJson(intKeysDict)
    assert cBytes == b'{"100":"hundred","20":"twenty","3":"three"}'

    # Sets are sorted deterministically
    setPayload1 = {"tags": {"beta", "alpha", "gamma"}}
    setPayload2 = {"tags": {"gamma", "beta", "alpha"}}
    assert canonicalizeJson(setPayload1) == canonicalizeJson(setPayload2)

    # Boolean values are serialized as true/false
    boolPayload = {"isActive": True, "isBlocked": False}
    assert canonicalizeJson(boolPayload) == b'{"isActive":true,"isBlocked":false}'

    # Non-ASCII Unicode characters preserved in UTF-8
    unicodePayload = {"currency": "\u20b9", "merchant": "\u092d\u093e\u0930\u0924"}
    cBytesUnicode = canonicalizeJson(unicodePayload)
    assert "\u20b9".encode("utf-8") in cBytesUnicode
    assert "\u092d\u093e\u0930\u0924".encode("utf-8") in cBytesUnicode


def testDidParsingAdversarialVectors() -> None:
    """Stress tests DID formatting and extraction with adversarial inputs."""
    validPubHex = "a" * 64
    validDid = f"did:agent:{validPubHex}"
    assert extractPublicKeyFromDid(validDid) == validPubHex

    # Uppercase handling
    upperPub = validPubHex.upper()
    upperDid = f"DID:AGENT:{upperPub}"
    with pytest.raises(InvalidDidError):
        extractPublicKeyFromDid(upperDid)

    # Invalid prefixes
    with pytest.raises(InvalidDidError):
        extractPublicKeyFromDid("did:merchant:" + "a" * 64)

    with pytest.raises(InvalidDidError):
        extractPublicKeyFromDid("did:user:" + "a" * 64)

    with pytest.raises(InvalidDidError):
        extractPublicKeyFromDid("invalid_did_format")

    # Wrong length public keys in DID
    with pytest.raises(InvalidDidError):
        extractPublicKeyFromDid("did:agent:" + "a" * 63)

    with pytest.raises(InvalidDidError):
        extractPublicKeyFromDid("did:agent:" + "a" * 65)

    with pytest.raises(InvalidDidError):
        extractPublicKeyFromDid("did:agent:")


def _assertInvalidSigOrKeyFails(pubHex: str, cBytes: bytes, sig: str) -> None:
    assert AgentKeyManager.verifySignature(pubHex, cBytes, sig) is False
    with pytest.raises(CryptographicVerificationError):
        AgentKeyManager.verifySignature(pubHex, cBytes, sig, raiseOnFailure=True)


def testKeyManagerAdversarialVerification() -> None:
    """Stress tests signature verification with corrupted keys, payloads, and signatures."""
    manager = AgentKeyManager.generate()
    payload = {"account": "acc_xyz", "amountPaise": 50000}
    cBytes, _ = canonicalizeAndHash(payload)
    sig = manager.signPayload(payload)
    pubHex = manager.getPublicKeyHex()

    assert AgentKeyManager.verifySignature(pubHex, cBytes, sig) is True
    assert manager.verifyPayloadSignature(pubHex, payload, sig) is True

    flippedChar = "1" if sig[0] != "1" else "2"
    badCombos = [
        (pubHex, sig[:-2]),
        (pubHex, sig + "00"),
        (pubHex[:-2], sig),
        ("z" * 64, sig),
        (pubHex, "z" * 128),
        (pubHex, flippedChar + sig[1:]),
    ]
    for badPub, badSig in badCombos:
        _assertInvalidSigOrKeyFails(badPub, cBytes, badSig)



def testKeypairUniquenessAndEntropy() -> None:
    """Stress tests generation of 100 distinct keypairs ensuring high entropy and uniqueness."""
    generatedDids = set()
    generatedPubs = set()
    generatedPrivs = set()

    for _ in range(100):
        km = AgentKeyManager.generate()
        did = km.getAgentDid()
        pub = km.getPublicKeyHex()
        priv = km.getPrivateKeyHex()

        assert did not in generatedDids
        assert pub not in generatedPubs
        assert priv not in generatedPrivs

        generatedDids.add(did)
        generatedPubs.add(pub)
        generatedPrivs.add(priv)
