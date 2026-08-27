"""Empirical Challenger 3 Test Suite: Adversarial Verification for Milestone 3 X402 Gateway.

Tests multi-round negotiation monotonicity, floor-price boundaries, concession rates,
HMAC-SHA256 webhook verification with corrupted payloads, dynamic PoW difficulty scaling,
and nonce exhaustion under strict integer paise invariants.
"""

import hashlib
import hmac
import json
import time
from typing import Any, Dict, List, Optional
from unittest.mock import AsyncMock, patch
from fastapi.testclient import TestClient
from httpx import Response
import pytest

from razoragentMesh.packages.mandateEngine.settlement.settlementExceptions import (
    ArithmeticDriftException,
    WebhookSignatureVerificationException,
)
from razoragentMesh.packages.mandateEngine.settlement.webhookVerifier import (
    verifyRazorpayWebhookSignature,
)
from razoragentMesh.packages.x402Gateway.src.alerts.priceDropAlertManager import (
    PriceDropAlert,
    PriceDropAlertManager,
    _buildWebhookPayload,
    _signWebhookPayload,
    eventPriceDropTriggered,
)
from razoragentMesh.packages.x402Gateway.src.constants.negotiationConstants import (
    defaultGatewaySecret,
    maxNegotiationTurns,
    microFeePerTurnPaise,
    minConcessionPaise,
    powChallengeTtlSeconds,
    powLeadingZeros,
)
from razoragentMesh.packages.x402Gateway.src.gatewayApp import createGatewayApp
from razoragentMesh.packages.x402Gateway.src.gatewayExceptions import (
    InvalidProofOfWorkException,
    NegotiationExhaustedException,
    NonMonotonicConcessionViolation,
    PowChallengeExpiredException,
    PowReplayDetectedException,
)
from razoragentMesh.packages.x402Gateway.src.middleware.proofOfWorkMiddleware import (
    IngressAntiSpamShield,
    evaluateDynamicDifficulty,
    powEscalatedLeadingZeros,
    powHighLoadThreshold,
    solvePoWChallenge,
)
from razoragentMesh.packages.x402Gateway.src.negotiation.bidStateMachine import (
    NegotiationStatus,
    RubinsteinStahlNegotiator,
)
from razoragentMesh.packages.x402Gateway.src.negotiation.marginEvaluator import (
    computeSellerCounterAsk,
    evaluateMargin,
)
from razoragentMesh.packages.x402Gateway.src.routes.negotiateRoute import (
    _resolveSellerCostFloor,
    activeNegotiators,
)
from razoragentMesh.tests.mockInfraHelpers import MockRedisAsync

# Constants in strict camelCase
testSkuIdProduct: str = "SKU-PREMIUM-CHAIR-001"
testBuyerDid: str = "did:mesh:buyer_challenger_m3"
testMerchantDid: str = "did:mesh:merchant_challenger_m3"
testCallbackUrl: str = "https://buyer-agent.mesh/api/v1/webhook"
testWebhookSecretKey: str = "whsec_challenger_m3_stress_secret_key"
testEscrowPoolPaise: int = 50000
testTurnFeePaise: int = microFeePerTurnPaise
testClientIpAlpha: str = "192.168.1.101"
testClientIpBeta: str = "192.168.1.202"


def testNegotiationMonotonicityAndConvergenceEmpiricalStress() -> None:
    """Stress-tests multi-round negotiation convergence, spread monotonicity, and turn fees."""
    negotiator = RubinsteinStahlNegotiator(
        skuId=testSkuIdProduct,
        quantity=1,
        escrowBalancePaise=testEscrowPoolPaise,
        sellerCostFloorPaise=80000,
    )
    bids = [80000, 85000, 90000, 95000]
    asks = [100000, 98000, 96000, 95000]
    prevSpread = 1000000

    for turnIdx, (bid, ask) in enumerate(zip(bids, asks), start=1):
        step = negotiator.executeTurn(turnNumber=turnIdx, buyerBidPaise=bid, sellerAskPaise=ask)
        assert step.spreadPaise < prevSpread, f"Spread failed monotonic decrease at turn {turnIdx}"
        prevSpread = step.spreadPaise
        assert step.cumulativeMicroFeesPaise == turnIdx * testTurnFeePaise

    assert negotiator.status == NegotiationStatus.CONVERGED
    assert prevSpread == 0


def testNegotiationFloorPriceBoundariesAndConcessionRate() -> None:
    """Verifies seller counter-ask calculations with floor constraints and margin evaluation."""
    initialAsk = 100000
    buyerBid = 70000
    costFloor = 85000

    for turn in range(1, 10):
        askWithFloor = computeSellerCounterAsk(initialAsk, buyerBid, turn, minConcessionPaise, costFloor)
        askWithoutFloor = computeSellerCounterAsk(initialAsk, buyerBid, turn, minConcessionPaise, None)
        assert askWithFloor >= costFloor, f"Counter-ask dropped below cost floor {costFloor}"
        expectedNoFloor = max(initialAsk - minConcessionPaise * turn, buyerBid)
        assert askWithoutFloor == expectedNoFloor

    assert evaluateMargin(wholesaleCostPaise=80000, askPaise=84000, marginFloorBps=500) is True
    assert evaluateMargin(wholesaleCostPaise=80000, askPaise=83999, marginFloorBps=500) is False


def testNegotiationMonotonicityViolationAdversarialBreaches() -> None:
    """Verifies strict rejection of non-monotonic bids and asks, and non-integer inputs."""
    negotiator = RubinsteinStahlNegotiator(testSkuIdProduct, 1, testEscrowPoolPaise)
    negotiator.executeTurn(turnNumber=1, buyerBidPaise=50000, sellerAskPaise=100000)

    # Buyer bid decrease attempt
    with pytest.raises(NonMonotonicConcessionViolation, match="Buyer bid cannot decrease"):
        negotiator.executeTurn(turnNumber=2, buyerBidPaise=49000, sellerAskPaise=99000)

    # Seller ask increase attempt
    with pytest.raises(NonMonotonicConcessionViolation, match="Seller ask cannot increase"):
        negotiator.executeTurn(turnNumber=2, buyerBidPaise=51000, sellerAskPaise=101000)

    # Floating-point paise attempt
    with pytest.raises(ArithmeticDriftException):
        negotiator.executeTurn(turnNumber=2, buyerBidPaise=52000.5, sellerAskPaise=98000)  # type: ignore[arg-type]


def testNegotiationMaxTurnsExhaustion() -> None:
    """Verifies negotiation terminates with exception when turn limit is exceeded."""
    negotiator = RubinsteinStahlNegotiator(testSkuIdProduct, 1, testEscrowPoolPaise)
    for turn in range(1, maxNegotiationTurns + 1):
        step = negotiator.executeTurn(turn, 50000 + turn * 1000, 100000 - turn * 1000)
        assert step.isConverged is False

    assert negotiator.status == NegotiationStatus.NEGOTIATION_EXHAUSTED
    with pytest.raises(NegotiationExhaustedException, match="Maximum negotiation turns exceeded"):
        negotiator.executeTurn(maxNegotiationTurns + 1, 60000, 90000)


@pytest.mark.asyncio
async def testSellerCostFloorResolutionLogic() -> None:
    """Verifies merchant policy floor calculation from Redis margin BPS and absolute paise."""
    mockRedis = MockRedisAsync()
    didBps = "did:mesh:merchant_bps"
    didPaise = "did:mesh:merchant_paise"
    await mockRedis.set(f"mesh:merchant:policy:{didBps}", json.dumps({"marginFloorBps": 1000}))
    await mockRedis.set(f"mesh:merchant:policy:{didPaise}", json.dumps({"sellerCostFloorPaise": 75000}))

    floorFromBps = await _resolveSellerCostFloor(didBps, sellerAskPaise=100000, redisClient=mockRedis)
    assert floorFromBps == 90000  # 100000 * (10000 - 1000) / 10000

    floorFromPaise = await _resolveSellerCostFloor(didPaise, sellerAskPaise=100000, redisClient=mockRedis)
    assert floorFromPaise == 75000


def testWebhookHmacVerificationValidAndCorruptedPayloads() -> None:
    """Empirically tests HMAC-SHA256 signature generation and rejection on corrupted payloads."""
    alert = PriceDropAlert(
        alertId="alert_m3_stress_01",
        skuId=testSkuIdProduct,
        targetPricePaise=90000,
        callbackUrl=testCallbackUrl,
        buyerAgentId=testBuyerDid,
        expiresAtUnix=int(time.time()) + 3600,
        createdAtUnix=int(time.time()),
        status="active",
    )
    payload = _buildWebhookPayload(alert, activePricePaise=85000, now=int(time.time()))
    payloadBytes, headers, sig = _signWebhookPayload(payload, testWebhookSecretKey)

    assert verifyRazorpayWebhookSignature(payloadBytes, sig, testWebhookSecretKey) is True
    assert headers["X-Mesh-Signature"] == sig
    assert headers["X-Razorpay-Signature"] == sig

    # Corrupt payload by bit flip and tampering
    corruptedBytes = bytearray(payloadBytes)
    corruptedBytes[5] ^= 0xFF
    assert verifyRazorpayWebhookSignature(bytes(corruptedBytes), sig, testWebhookSecretKey) is False

    # Wrong secret
    assert verifyRazorpayWebhookSignature(payloadBytes, sig, "incorrect_secret_999") is False

    with pytest.raises(WebhookSignatureVerificationException):
        verifyRazorpayWebhookSignature(payloadBytes, "0" * 64, testWebhookSecretKey, raiseOnFailure=True)


def testDynamicPowChallengeDifficultyScaling() -> None:
    """Verifies dynamic PoW challenge difficulty escalation under high request load."""
    shield = IngressAntiSpamShield()

    assert evaluateDynamicDifficulty(testClientIpAlpha, requestCount=0) == powLeadingZeros
    assert evaluateDynamicDifficulty(testClientIpAlpha, requestCount=99) == powLeadingZeros
    assert evaluateDynamicDifficulty(testClientIpAlpha, requestCount=100) == powEscalatedLeadingZeros
    assert evaluateDynamicDifficulty(testClientIpAlpha, requestCount=500) == powEscalatedLeadingZeros

    # Generate 99 challenges for IP Alpha (low load)
    for _ in range(powHighLoadThreshold - 1):
        resp = shield.generateChallenge(testClientIpAlpha)
        assert resp.powDifficultyZeros == powLeadingZeros

    # 100th challenge triggers escalation
    resp100 = shield.generateChallenge(testClientIpAlpha)
    assert resp100.powDifficultyZeros == powEscalatedLeadingZeros

    # Independent IP Beta remains at base difficulty
    respBeta = shield.generateChallenge(testClientIpBeta)
    assert respBeta.powDifficultyZeros == powLeadingZeros


def testPowSolvingVerificationReplayAndExpiry() -> None:
    """Stress-tests PoW solver, verification, replay prevention, and TTL expiration."""
    shield = IngressAntiSpamShield()
    resp = shield.generateChallenge(testClientIpAlpha, requestCount=1)
    challenge = resp.challengeToken

    nonce = solvePoWChallenge(challenge, difficultyZeros=resp.powDifficultyZeros)
    assert shield.verifyPoWSolution(challenge, nonce, difficultyZeros=resp.powDifficultyZeros) is True

    result = shield.validatePoWSubmission(challenge, nonce)
    assert result.isValid is True
    assert challenge not in shield.activeChallenges

    # Replay attack attempt
    with pytest.raises(PowReplayDetectedException, match="already consumed"):
        shield.validatePoWSubmission(challenge, nonce)

    # Expired challenge validation
    expiredResp = shield.generateChallenge(testClientIpAlpha, requestCount=1)
    with patch("time.time", return_value=int(time.time()) + powChallengeTtlSeconds + 10):
        with pytest.raises(PowChallengeExpiredException, match="expired"):
            shield.validatePoWSubmission(expiredResp.challengeToken, 12345)

    # Invalid PoW nonce
    freshResp = shield.generateChallenge(testClientIpAlpha, requestCount=1)
    with pytest.raises(InvalidProofOfWorkException, match="did not satisfy"):
        shield.validatePoWSubmission(freshResp.challengeToken, nonce=-1)


def testNegotiateRouteEndToEndWithTestClient() -> None:
    """Verifies end-to-end FastAPI negotiate route error codes and convergence AST compilation."""
    app = createGatewayApp()
    client = TestClient(app)

    challengeResp = client.get("/api/v1/mesh/challenge")
    assert challengeResp.status_code == 200
    token = challengeResp.json()["challengeToken"]
    diff = challengeResp.json()["powDifficultyZeros"]
    solution = solvePoWChallenge(token, diff)

    escrowResp = client.post(
        "/api/v1/mesh/escrow",
        json={"buyerAgentDid": testBuyerDid, "initialHoldPaise": 10000},
    )
    assert escrowResp.status_code == 201
    escrowToken = escrowResp.json()["sessionToken"]

    headers = {
        "X-Mesh-Pow-Challenge": token,
        "X-Mesh-Pow-Solution": str(solution),
        "X-Mesh-Escrow-Token": escrowToken,
    }
    payload = {
        "buyerAgentDid": testBuyerDid,
        "skuId": testSkuIdProduct,
        "quantity": 1,
        "turnNumber": 1,
        "buyerBidPaise": 95000,
        "sellerAskPaise": 95000,
        "merchantDid": testMerchantDid,
    }

    turnResp = client.post("/api/v1/mesh/negotiate", json=payload, headers=headers)
    assert turnResp.status_code == 200
    data = turnResp.json()
    assert data["stepResult"]["isConverged"] is True
    assert data["contractAst"] is not None
    assert data["contractAstHash"] is not None
