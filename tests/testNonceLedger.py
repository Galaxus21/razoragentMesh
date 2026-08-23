"""Unit tests for Nonce Generator and Distributed Redis Nonce Ledger."""

import time
import pytest
import fakeredis.aioredis
from razoragentMesh.packages.mandateEngine.nonceGenerator import (
    generateNonce,
    generateTimestampedNonce,
)
from razoragentMesh.packages.mandateEngine.nonceLedger import NonceLedger
from razoragentMesh.packages.mandateEngine.settlementExceptions import (
    FutureTimestampException,
    NonceReplayException,
    TimestampExpiredException,
)


def testNonceGenerator() -> None:
    """Verifies format and uniqueness of generated nonces."""
    nonce1 = generateNonce()
    nonce2 = generateNonce()
    assert nonce1.startswith("nonce_")
    assert nonce1 != nonce2

    n3, ts = generateTimestampedNonce()
    assert n3.startswith("nonce_")
    assert ts > 0


@pytest.mark.asyncio
async def testNonceLedgerFreshAndReplay() -> None:
    """Verifies fresh nonce acceptance and replay attack rejection (409)."""
    fakeRedis = fakeredis.aioredis.FakeRedis()
    ledger = NonceLedger(fakeRedis)

    nonce = generateNonce()
    now = int(time.time())

    # First consumption: fresh -> succeeds
    recorded = await ledger.validateAndRecordNonce(nonce, now, serverTime=now)
    assert recorded is True

    # Second consumption of same nonce: replay attack -> raises NonceReplayException
    with pytest.raises(NonceReplayException):
        await ledger.validateAndRecordNonce(nonce, now, serverTime=now)


@pytest.mark.asyncio
async def testNonceLedgerTimestampDriftWindow() -> None:
    """Verifies NTP drift window bounds [T - 5s, T + 60s]."""
    fakeRedis = fakeredis.aioredis.FakeRedis()
    ledger = NonceLedger(fakeRedis)
    serverTime = 1000

    # Within valid window
    assert ledger.verifyTimestampWindow(1000, serverTime=serverTime) is True
    assert ledger.verifyTimestampWindow(995, serverTime=serverTime) is True  # T - 5s
    assert ledger.verifyTimestampWindow(1060, serverTime=serverTime) is True  # T + 60s

    # Expired past T - 5s
    with pytest.raises(TimestampExpiredException):
        ledger.verifyTimestampWindow(994, serverTime=serverTime)

    # Future past T + 60s
    with pytest.raises(FutureTimestampException):
        ledger.verifyTimestampWindow(1061, serverTime=serverTime)
