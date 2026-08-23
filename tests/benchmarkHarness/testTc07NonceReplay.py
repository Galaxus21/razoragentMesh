import time
from typing import Any, Dict
import pytest

from razoragentMesh.packages.mandateEngine.crypto.ed25519Signer import Ed25519Signer
from razoragentMesh.packages.mandateEngine.crypto.ed25519Verifier import Ed25519Verifier
from razoragentMesh.packages.mandateEngine.crypto.jcsCanonicalizer import canonicalizeJson
from razoragentMesh.packages.mandateEngine.nonce.nonceLedger import NonceLedger
from razoragentMesh.packages.mandateEngine.settlement.settlementExceptions import (
    FutureTimestampException,
    NonceReplayException,
    SignatureVerificationFailedException,
    TimestampExpiredException,
)

# Benchmark Constants
originalAmountPaise = 420000
tamperedAmountPaise = 420001


@pytest.mark.asyncio
async def testTc07NonceReplayDefense(mockRedisClient: Any) -> None:
    """TC-07: Nonce Replay Defense — Replaying consumed nonce raises NonceReplayException (409 Conflict)."""
    nonceLedger = NonceLedger(mockRedisClient)
    currentTime = int(time.time())
    testNonce = "nonce_unique_test_tc07_uuid"

    # Step 1: Initial valid request successfully records nonce
    firstAttempt = await nonceLedger.validateAndRecordNonce(
        nonce=testNonce,
        timestamp=currentTime,
        serverTime=currentTime,
    )
    assert firstAttempt is True

    # Step 2: Attacker replays same nonce within TTL -> Redis SETNX raises NonceReplayException
    replayedTime = currentTime + 30
    with pytest.raises(NonceReplayException) as excInfo:
        await nonceLedger.validateAndRecordNonce(
            nonce=testNonce,
            timestamp=replayedTime,
            serverTime=replayedTime,
        )
    assert "Replay attack detected (409)" in str(excInfo.value)


def testTc07NtpTimestampWindowingDrift(mockRedisClient: Any) -> None:
    """Verifies that timestamps outside [T - 5s, T + 60s] are strictly rejected."""
    nonceLedger = NonceLedger(mockRedisClient)
    serverTime = 1000

    # 1. Expired timestamp: T - 6s (< 995)
    with pytest.raises(TimestampExpiredException):
        nonceLedger.verifyTimestampWindow(timestamp=994, serverTime=serverTime)

    # 2. Future timestamp: T + 61s (> 1060)
    with pytest.raises(FutureTimestampException):
        nonceLedger.verifyTimestampWindow(timestamp=1061, serverTime=serverTime)

    # 3. Boundary values: T - 5s (995) and T + 60s (1060) are valid
    assert nonceLedger.verifyTimestampWindow(timestamp=995, serverTime=serverTime) is True
    assert nonceLedger.verifyTimestampWindow(timestamp=1060, serverTime=serverTime) is True


def testTc07SignatureTamperingInterception(agentKeyFixtures: Dict[str, Any]) -> None:
    """Verifies that tampering with signed mandate payload invalidates Ed25519 signature."""
    buyerKey = agentKeyFixtures["buyerAgent"]
    signer = Ed25519Signer(buyerKey["privateKeyHex"])
    publicKeyHex = signer.getPublicKeyHex()

    originalPayload = {
        "executionId": "exec_tc07_tamper_test",
        "settlementAmountPaise": originalAmountPaise,
        "currency": "INR",
        "timestamp": 1755936000,
    }
    signature = signer.signPayload(originalPayload)

    # 1. Verify original payload validates cleanly
    assert Ed25519Verifier.verifyPayloadSignature(
        publicKeyHex=publicKeyHex,
        payload=originalPayload,
        signatureHex=signature,
    ) is True

    # 2. Attacker tampers amount by +1 paise (420000 -> 420001)
    tamperedPayload = {
        "executionId": "exec_tc07_tamper_test",
        "settlementAmountPaise": tamperedAmountPaise,
        "currency": "INR",
        "timestamp": 1755936000,
    }

    # Verify tampering is cryptographically intercepted
    with pytest.raises(SignatureVerificationFailedException):
        Ed25519Verifier.verifyPayloadSignature(
            publicKeyHex=publicKeyHex,
            payload=tamperedPayload,
            signatureHex=signature,
            raiseOnFailure=True,
        )
