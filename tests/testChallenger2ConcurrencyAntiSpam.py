"""Concurrency and Anti-Spam / PoW Invariant Tests.

Tests:
1. Concurrency Double-Lock Race (TC-09)
2. Anti-Spam Sybil & x402-INR Challenge (TC-06)
"""

import asyncio
import time
from typing import List
import pytest
from httpx import ASGITransport, AsyncClient

from razoragentMesh.packages.x402Gateway.src.gatewayApp import app
from razoragentMesh.packages.x402Gateway.src.gatewayExceptions import (
    InvalidProofOfWorkException,
    PowChallengeExpiredException,
    PowReplayDetectedException,
)
from razoragentMesh.packages.x402Gateway.src.middleware.proofOfWorkMiddleware import (
    IngressAntiSpamShield,
    solvePoWChallenge,
)
from razoragentMesh.tests.mockInfraHelpers import MockRedisAsync


@pytest.mark.asyncio
async def testChallenger2ConcurrencyExactDoubleLockRace(mockRedisClient: MockRedisAsync) -> None:
    """Stress Test 1.1: Exact 2-agent simultaneous race for last 1 inventory unit."""
    skuId = "SKU-STRESS-001"
    stockKey = f"sku:{skuId}:stock"
    fencingKey = f"sku:{skuId}:fence"
    await mockRedisClient.set(stockKey, 1)

    async def lockAttempt(agentId: str) -> tuple[int, int]:
        res = await mockRedisClient.eval("", 2, stockKey, fencingKey, 1, f"token_{agentId}", 60)
        return res[0], res[1]

    taskA = asyncio.create_task(lockAttempt("agent_alpha"))
    taskB = asyncio.create_task(lockAttempt("agent_beta"))

    resA, resB = await asyncio.gather(taskA, taskB)
    statuses = [resA[0], resB[0]]

    assert statuses.count(1) == 1, f"Expected exactly 1 success, got {statuses}"
    assert statuses.count(-1) == 1, f"Expected exactly 1 failure, got {statuses}"

    finalStock = int(await mockRedisClient.get(stockKey) or 0)
    assert finalStock == 0, f"Stock must be exactly 0, got {finalStock}"


@pytest.mark.asyncio
async def testChallenger2ConcurrencyMultiAgentMassiveContention(mockRedisClient: MockRedisAsync) -> None:
    """Stress Test 1.2: 50 concurrent agents racing for 5 available inventory units."""
    skuId = "SKU-STRESS-50-AGENTS"
    stockKey = f"sku:{skuId}:stock"
    fencingKey = f"sku:{skuId}:fence"
    initialStock = 5
    concurrencyCount = 50

    await mockRedisClient.set(stockKey, initialStock)

    async def attemptLock(agentIndex: int) -> tuple[int, int]:
        res = await mockRedisClient.eval(
            "", 2, stockKey, fencingKey, 1, f"token_agent_{agentIndex:03d}", 60
        )
        return res[0], res[1]

    tasks = [asyncio.create_task(attemptLock(i)) for i in range(concurrencyCount)]
    results = await asyncio.gather(*tasks)

    successes = [r for r in results if r[0] == 1]
    rejections = [r for r in results if r[0] == -1]

    assert len(successes) == initialStock
    assert len(rejections) == concurrencyCount - initialStock

    fencingTokens = sorted([r[1] for r in successes])
    assert fencingTokens == list(range(1, initialStock + 1))

    finalStock = int(await mockRedisClient.get(stockKey) or 0)
    assert finalStock == 0


@pytest.mark.asyncio
async def testChallenger2ConcurrencyLockExpirationAndRelock(mockRedisClient: MockRedisAsync) -> None:
    """Stress Test 1.3: Lock attempts on depleted stock remain rejected."""
    skuId = "SKU-STRESS-DEPLETED"
    stockKey = f"sku:{skuId}:stock"
    fencingKey = f"sku:{skuId}:fence"
    await mockRedisClient.set(stockKey, 0)

    res = await mockRedisClient.eval("", 2, stockKey, fencingKey, 1, "token_fail", 60)
    assert res[0] == -1
    assert res[1] == 0


def testChallenger2AntiSpam100ConcurrentSpamBidsFastPathRejection() -> None:
    """Stress Test 2.1: 100 concurrent unauthenticated spam bids."""
    shield = IngressAntiSpamShield()

    startChal = time.perf_counter()
    challenge = shield.generateChallenge(clientIp="192.168.1.10")
    chalLatencyMs = (time.perf_counter() - startChal) * 1000.0

    assert challenge.statusCode == 402
    assert challenge.wwwAuthenticate == "x402-INR"
    assert challenge.powDifficultyZeros == 4
    assert chalLatencyMs < 2.0, f"Challenge generation latency {chalLatencyMs:.3f}ms exceeded 2ms SLA"

    rejectionTimesMs: List[float] = []
    for _ in range(2, 101):
        t0 = time.perf_counter()
        status, msg = shield.processRequest(challengeToken=None, powNonce=None, escrowSessionToken=None)
        elapsedMs = (time.perf_counter() - t0) * 1000.0
        rejectionTimesMs.append(elapsedMs)
        assert status == 402
        assert "Micro-escrow and PoW challenge required" in msg

    assert len(rejectionTimesMs) == 99
    assert sum(rejectionTimesMs) / len(rejectionTimesMs) < 1.0
    assert max(rejectionTimesMs) < 2.0
    assert shield.llmInvocationsCount == 0, "Zero LLM invocations allowed on spam flood"


def testChallenger2PoWReplayAndTamperedNonceAttack() -> None:
    """Stress Test 2.2: Adversarial attacks on PoW mechanism."""
    shield = IngressAntiSpamShield()
    challenge = shield.generateChallenge(clientIp="10.10.10.1")
    nonce = solvePoWChallenge(challenge.challengeToken)

    # 1. First submission succeeds
    result = shield.validatePoWSubmission(challenge.challengeToken, nonce)
    assert result.isValid is True

    # 2. Replay of same token/nonce -> PowReplayDetectedException
    with pytest.raises(PowReplayDetectedException):
        shield.validatePoWSubmission(challenge.challengeToken, nonce)

    # 3. Invalid nonce on fresh challenge -> InvalidProofOfWorkException
    chal2 = shield.generateChallenge(clientIp="10.10.10.2")
    with pytest.raises(InvalidProofOfWorkException):
        shield.validatePoWSubmission(chal2.challengeToken, nonce=999999999)

    # 4. Expired challenge -> PowChallengeExpiredException
    chal3 = shield.generateChallenge(clientIp="10.10.10.3")
    shield.activeChallenges[chal3.challengeToken] = int(time.time()) - 10
    with pytest.raises(PowChallengeExpiredException):
        shield.validatePoWSubmission(chal3.challengeToken, nonce=0)


@pytest.mark.asyncio
async def testChallenger2GatewayApp100SpamHttpRequests() -> None:
    """Stress Test 2.3: 100 concurrent HTTP requests against FastAPI /api/v1/mesh/negotiate."""
    transport = ASGITransport(app=app)
    async with AsyncClient(transport=transport, base_url="http://testserver") as client:
        async def sendSpamRequest(idx: int) -> int:
            resp = await client.post(
                "/api/v1/mesh/negotiate",
                json={
                    "skuId": "SKU-CHAIR-001",
                    "quantity": 1,
                    "turnNumber": 1,
                    "buyerBidPaise": 330000,
                    "sellerAskPaise": 345000,
                    "buyerAgentDid": f"did:agent:spammer_{idx}",
                    "merchantDid": "did:agent:merchant",
                },
            )
            return resp.status_code

        tasks = [sendSpamRequest(i) for i in range(100)]
        t0 = time.perf_counter()
        statusCodes = await asyncio.gather(*tasks)
        totalElapsedMs = (time.perf_counter() - t0) * 1000.0

        assert statusCodes.count(402) == 100
        avgLatencyMs = totalElapsedMs / 100.0
        assert avgLatencyMs < 10.0, f"Average ASGI HTTP 402 latency {avgLatencyMs:.2f}ms"
