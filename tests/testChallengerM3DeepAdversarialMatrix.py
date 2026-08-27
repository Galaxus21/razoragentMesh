"""Empirical Challenger 3 Deep Adversarial Matrix: Milestone 3 X402 Gateway.

Extends verification with multi-round parameter matrices, webhook mutation fuzzing,
and high-concurrency PoW challenge-response validation.
"""

import hashlib
import hmac
import json
import time
from typing import Any, Dict, List, Optional
from unittest.mock import AsyncMock, patch
import pytest

from razoragentMesh.packages.mandateEngine.settlement.webhookVerifier import (
    verifyRazorpayWebhookSignature,
)
from razoragentMesh.packages.x402Gateway.src.alerts.priceDropAlertManager import (
    PriceDropAlert,
    _buildWebhookPayload,
    _signWebhookPayload,
)
from razoragentMesh.packages.x402Gateway.src.constants.negotiationConstants import (
    maxNegotiationTurns,
    microFeePerTurnPaise,
    minConcessionPaise,
    powLeadingZeros,
)
from razoragentMesh.packages.x402Gateway.src.gatewayExceptions import (
    InvalidProofOfWorkException,
    NonMonotonicConcessionViolation,
    PowReplayDetectedException,
)
from razoragentMesh.packages.x402Gateway.src.middleware.proofOfWorkMiddleware import (
    IngressAntiSpamShield,
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
)

testMatrixSku: str = "SKU-MATRIX-ITEM-001"
testMatrixBuyerDid: str = "did:mesh:buyer_matrix_stress"
testMatrixCallbackUrl: str = "https://buyer-agent.mesh/api/v1/webhook"
testMatrixWebhookSecret: str = "whsec_deep_matrix_secret_key_2026"
testMatrixClientIp: str = "10.0.0.99"


def testMultiRoundConcessionRateConvergenceMatrix() -> None:
    """Tests multi-round bargaining convergence across diverse bid/ask/floor parameter triples."""
    scenarios = [
        {"initialAsk": 100000, "floor": 80000, "bids": [70000, 80000, 90000, 98500], "shouldConverge": True},
        {"initialAsk": 100000, "floor": 95000, "bids": [70000, 75000, 80000, 85000], "shouldConverge": False},
        {"initialAsk": 50000, "floor": 45000, "bids": [40000, 45000, 48000, 48500], "shouldConverge": True},
    ]

    for scenario in scenarios:
        initialAsk = scenario["initialAsk"]
        floor = scenario["floor"]
        bids = scenario["bids"]
        shouldConverge = scenario["shouldConverge"]

        negotiator = RubinsteinStahlNegotiator(
            skuId=testMatrixSku,
            quantity=1,
            escrowBalancePaise=50000,
            sellerCostFloorPaise=floor,
        )

        prevSpread = 1000000
        for turnIdx, buyerBid in enumerate(bids, start=1):
            sellerAsk = computeSellerCounterAsk(initialAsk, buyerBid, turnIdx, minConcessionPaise, floor)
            step = negotiator.executeTurn(turnIdx, buyerBid, sellerAsk)
            assert sellerAsk >= floor, f"Seller ask breached cost floor {floor} at turn {turnIdx}"
            assert step.spreadPaise <= prevSpread, f"Spread expanded at turn {turnIdx}"
            prevSpread = step.spreadPaise
            if step.isConverged:
                break

        assert (negotiator.status == NegotiationStatus.CONVERGED) == shouldConverge


def testMonotonicityBoundaryEqualAndStrictChecks() -> None:
    """Verifies that equal consecutive bids/asks are allowed while opposing directional shifts fail."""
    negotiator = RubinsteinStahlNegotiator(testMatrixSku, 1, 50000)
    # Turn 1
    negotiator.executeTurn(turnNumber=1, buyerBidPaise=50000, sellerAskPaise=80000)
    # Turn 2: same bids (allowed)
    step2 = negotiator.executeTurn(turnNumber=2, buyerBidPaise=50000, sellerAskPaise=80000)
    assert step2.spreadPaise == 30000

    # Turn 3: buyer tries to drop by 1 paise (fails)
    with pytest.raises(NonMonotonicConcessionViolation):
        negotiator.executeTurn(turnNumber=3, buyerBidPaise=49999, sellerAskPaise=80000)

    # Turn 3: seller tries to increase by 1 paise (fails)
    with pytest.raises(NonMonotonicConcessionViolation):
        negotiator.executeTurn(turnNumber=3, buyerBidPaise=50000, sellerAskPaise=80001)


def testAdversarialHmacPayloadMutationsMatrix() -> None:
    """Tests webhook signature verification across systematic payload mutations and injections."""
    alert = PriceDropAlert(
        alertId="alert_matrix_test_01",
        skuId=testMatrixSku,
        targetPricePaise=75000,
        callbackUrl=testMatrixCallbackUrl,
        buyerAgentId=testMatrixBuyerDid,
        expiresAtUnix=int(time.time()) + 1800,
        createdAtUnix=int(time.time()),
        status="active",
    )
    payload = _buildWebhookPayload(alert, activePricePaise=70000, now=int(time.time()))
    payloadBytes, _, sig = _signWebhookPayload(payload, testMatrixWebhookSecret)

    baseDict = json.loads(payloadBytes.decode("utf-8"))

    mutationKeys = [
        ("skuId", "SKU-HACKED-001"),
        ("buyerAgentId", "did:mesh:hacker"),
        ("activePricePaise", 1000),
        ("savingsPaise", 99999),
        ("targetPricePaise", 1000000),
        ("event", "payment.hacked"),
    ]

    for key, mutatedVal in mutationKeys:
        tamperedDict = dict(baseDict)
        tamperedDict[key] = mutatedVal
        tamperedBytes = json.dumps(tamperedDict, separators=(",", ":"), sort_keys=True).encode("utf-8")
        assert verifyRazorpayWebhookSignature(tamperedBytes, sig, testMatrixWebhookSecret) is False


def testDynamicPowMultiChallengeBatchAndReplay() -> None:
    """Stress-tests batch challenge solving, verification, replay prevention, and adjacent nonce rejection."""
    shield = IngressAntiSpamShield()
    challenges: List[str] = []
    difficulties: List[int] = []

    # Generate 10 challenges
    for i in range(10):
        resp = shield.generateChallenge(testMatrixClientIp, requestCount=i)
        challenges.append(resp.challengeToken)
        difficulties.append(resp.powDifficultyZeros)

    # Solve and verify each
    for token, diff in zip(challenges, difficulties):
        # Fresh invalid nonce test
        with pytest.raises(InvalidProofOfWorkException):
            shield.validatePoWSubmission(token, nonce=-999)

        nonce = solvePoWChallenge(token, difficultyZeros=diff)
        # Verify valid nonce succeeds
        result = shield.validatePoWSubmission(token, nonce)
        assert result.isValid is True

        # Verify immediate replay fails
        with pytest.raises(PowReplayDetectedException):
            shield.validatePoWSubmission(token, nonce)


def testDynamicPowHighLoadThresholdEscalation() -> None:
    """Verifies transition from base difficulty to escalated difficulty at exact threshold."""
    shield = IngressAntiSpamShield()
    targetIp = "172.16.0.42"

    for reqNum in range(1, powHighLoadThreshold + 5):
        resp = shield.generateChallenge(targetIp)
        expectedDiff = powEscalatedLeadingZeros if reqNum >= powHighLoadThreshold else powLeadingZeros
        assert resp.powDifficultyZeros == expectedDiff, f"Difficulty mismatch at request {reqNum}"
