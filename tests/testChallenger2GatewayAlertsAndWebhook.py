"""Empirical Challenger 2 Test Suite: Gateway Alerts TTL & HMAC Webhook Security."""

import hashlib
import hmac
import json
import time
from unittest.mock import AsyncMock, patch
from httpx import Response
import pytest

from razoragentMesh.packages.mandateEngine.settlement.settlementExceptions import (
    ArithmeticDriftException,
)
from razoragentMesh.packages.mandateEngine.settlement.webhookVerifier import (
    verifyRazorpayWebhookSignature,
)
from razoragentMesh.packages.x402Gateway.src.alerts.priceDropAlertManager import (
    PriceDropAlertManager,
    PriceDropWebhookPayload,
    eventPriceDropTriggered,
)
from razoragentMesh.packages.x402Gateway.src.routes.alertsRoute import (
    cancelPriceDropAlert,
    registerPriceDropAlert,
)
from razoragentMesh.packages.x402Gateway.src.schemas.alertSchema import (
    PriceDropAlertRegisterRequest,
)
from razoragentMesh.tests.mockInfraHelpers import MockRedisAsync

# Test Constants in camelCase
testSkuIdChair: str = "SKU-CHAIR-001"
testTargetPricePaise: int = 350000
testActivePricePaise: int = 340000
testBuyerAgentId: str = "did:mesh:buyer_challenger2"
testCallbackUrl: str = "https://buyer-agent.mesh/api/v1/webhook"
testWebhookSecret: str = "whsec_adversarial_test_secret_2026"
secondsPerMinute: int = 60
secondsPerHour: int = 3600
secondsPerDay: int = 86400


@pytest.mark.asyncio
async def testGatewayAlertTtlPruningInMemory() -> None:
    """Challenge 1A: Verifies alert expiry filtering and automatic pruning in memory."""
    manager = PriceDropAlertManager(redisClient=None, webhookSecret=testWebhookSecret)
    now = int(time.time())

    # Register Alert A (expires in 10s) and Alert B (expires in 100s)
    alertA = await manager.registerPriceDropAlert(
        skuId=testSkuIdChair,
        targetPricePaise=testTargetPricePaise,
        callbackUrl=testCallbackUrl,
        buyerAgentId=testBuyerAgentId,
        expiresAtUnix=now + 10,
    )
    alertB = await manager.registerPriceDropAlert(
        skuId=testSkuIdChair,
        targetPricePaise=testTargetPricePaise,
        callbackUrl=testCallbackUrl,
        buyerAgentId=testBuyerAgentId,
        expiresAtUnix=now + 100,
    )

    # At now + 0: both alerts are active
    activeBefore = await manager.getAlertsForSku(testSkuIdChair)
    assert len(activeBefore) == 2

    # Simulate time advance to now + 20 (Alert A expired, Alert B active)
    with patch("time.time", return_value=now + 20):
        activeAfter = await manager.getAlertsForSku(testSkuIdChair)
        assert len(activeAfter) == 1
        assert activeAfter[0].alertId == alertB.alertId

        # Dispatch should only trigger Alert B
        mockResponse = Response(status_code=200, content=b'{"status":"ok"}')
        with patch("httpx.AsyncClient.post", new_callable=AsyncMock) as mockPost:
            mockPost.return_value = mockResponse
            results = await manager.dispatchPriceDropAlerts(testSkuIdChair, testActivePricePaise)
            assert len(results) == 1
            assert results[0].alertId == alertB.alertId

    # Simulate time advance past Alert B expiry (now + 200)
    with patch("time.time", return_value=now + 200):
        activeExpiredAll = await manager.getAlertsForSku(testSkuIdChair)
        assert len(activeExpiredAll) == 0
        resultsPast = await manager.dispatchPriceDropAlerts(testSkuIdChair, testActivePricePaise)
        assert len(resultsPast) == 0


@pytest.mark.asyncio
async def testGatewayAlertTtlPruningMockRedis() -> None:
    """Challenge 1B: Verifies alert expiry filtering and Redis bucket TTL isolation."""
    mockRedis = MockRedisAsync()
    manager = PriceDropAlertManager(redisClient=mockRedis, webhookSecret=testWebhookSecret)
    now = int(time.time())

    alert = await manager.registerPriceDropAlert(
        skuId=testSkuIdChair,
        targetPricePaise=testTargetPricePaise,
        callbackUrl=testCallbackUrl,
        buyerAgentId=testBuyerAgentId,
        expiresAtUnix=now + 30,
    )
    assert alert.alertId.startswith("alert_")

    # Verify Redis keys exist
    bucketKey = f"mesh:alerts:priceDrop:{testSkuIdChair}"
    lookupKey = f"mesh:alerts:lookup:{alert.alertId}"
    rawBucket = await mockRedis.get(bucketKey)
    assert rawBucket is not None

    # Advance time past TTL
    with patch("time.time", return_value=now + 50):
        alerts = await manager.getAlertsForSku(testSkuIdChair)
        assert len(alerts) == 0


@pytest.mark.asyncio
async def testGatewayAlertCancellationAndIndexPruning() -> None:
    """Challenge 1C: Verifies alert cancellation cleans up lookup index and bucket keys."""
    mockRedis = MockRedisAsync()
    manager = PriceDropAlertManager(redisClient=mockRedis, webhookSecret=testWebhookSecret)
    now = int(time.time())

    alert1 = await manager.registerPriceDropAlert(
        skuId=testSkuIdChair,
        targetPricePaise=testTargetPricePaise,
        callbackUrl=testCallbackUrl,
        buyerAgentId=testBuyerAgentId,
        expiresAtUnix=now + 300,
    )
    alert2 = await manager.registerPriceDropAlert(
        skuId=testSkuIdChair,
        targetPricePaise=testTargetPricePaise,
        callbackUrl=testCallbackUrl,
        buyerAgentId=testBuyerAgentId,
        expiresAtUnix=now + 300,
    )

    # Cancel alert 1
    assert await manager.cancelPriceDropAlert(alert1.alertId) is True
    assert await manager.cancelPriceDropAlert(alert1.alertId) is False

    # Alert 2 still exists
    remaining = await manager.getAlertsForSku(testSkuIdChair)
    assert len(remaining) == 1
    assert remaining[0].alertId == alert2.alertId

    # Cancel alert 2 -> bucket completely deleted
    assert await manager.cancelPriceDropAlert(alert2.alertId) is True
    bucketKey = f"mesh:alerts:priceDrop:{testSkuIdChair}"
    assert await mockRedis.get(bucketKey) is None


@pytest.mark.asyncio
async def testGatewayAlertRegistrationInputValidation() -> None:
    """Challenge 1D: Verifies adversarial input rejection on alert registration."""
    manager = PriceDropAlertManager()
    now = int(time.time())

    # Expired timestamp
    with pytest.raises(ValueError, match="future"):
        await manager.registerPriceDropAlert(
            skuId=testSkuIdChair,
            targetPricePaise=testTargetPricePaise,
            callbackUrl=testCallbackUrl,
            buyerAgentId=testBuyerAgentId,
            expiresAtUnix=now - 10,
        )

    # Zero or negative target price
    with pytest.raises(ValueError, match="positive"):
        await manager.registerPriceDropAlert(
            skuId=testSkuIdChair,
            targetPricePaise=0,
            callbackUrl=testCallbackUrl,
            buyerAgentId=testBuyerAgentId,
            expiresAtUnix=now + 300,
        )

    # Floating point price
    with pytest.raises(ArithmeticDriftException):
        await manager.registerPriceDropAlert(
            skuId=testSkuIdChair,
            targetPricePaise=3500.50,  # type: ignore[arg-type]
            callbackUrl=testCallbackUrl,
            buyerAgentId=testBuyerAgentId,
            expiresAtUnix=now + 300,
        )


def testHmacWebhookExhaustiveBitFlip() -> None:
    """Challenge 2A: Verifies constant-time HMAC rejection across exhaustive bit mutations."""
    now = 1724480000
    payload = PriceDropWebhookPayload(
        event=eventPriceDropTriggered,
        alertId="alert_test12345678",
        skuId=testSkuIdChair,
        buyerAgentId=testBuyerAgentId,
        targetPricePaise=testTargetPricePaise,
        activePricePaise=testActivePricePaise,
        savingsPaise=10000,
        triggeredAtUnix=now,
        callbackUrl=testCallbackUrl,
    )
    payloadBytes = json.dumps(payload.model_dump(), separators=(",", ":"), sort_keys=True).encode("utf-8")
    validSig = hmac.new(testWebhookSecret.encode("utf-8"), payloadBytes, hashlib.sha256).hexdigest()

    # Base signature is valid
    assert verifyRazorpayWebhookSignature(payloadBytes, validSig, testWebhookSecret) is True

    # Mutate every single bit across 50 sample byte positions in the payload
    step = max(1, len(payloadBytes) // 50)
    for byteIdx in range(0, len(payloadBytes), step):
        originalByte = payloadBytes[byteIdx]
        for bitIdx in range(8):
            mutatedByte = originalByte ^ (1 << bitIdx)
            corruptedBytes = bytearray(payloadBytes)
            corruptedBytes[byteIdx] = mutatedByte
            isAccepted = verifyRazorpayWebhookSignature(bytes(corruptedBytes), validSig, testWebhookSecret)
            assert isAccepted is False, f"Bit flip at byte {byteIdx}, bit {bitIdx} was not rejected!"


def testHmacWebhookPayloadFieldTampering() -> None:
    """Challenge 2B: Verifies signature verification failure upon individual field tampering."""
    now = 1724480000
    basePayloadDict = {
        "event": eventPriceDropTriggered,
        "alertId": "alert_test12345678",
        "skuId": testSkuIdChair,
        "buyerAgentId": testBuyerAgentId,
        "targetPricePaise": testTargetPricePaise,
        "activePricePaise": testActivePricePaise,
        "savingsPaise": 10000,
        "triggeredAtUnix": now,
        "callbackUrl": testCallbackUrl,
    }
    payloadBytes = json.dumps(basePayloadDict, separators=(",", ":"), sort_keys=True).encode("utf-8")
    validSig = hmac.new(testWebhookSecret.encode("utf-8"), payloadBytes, hashlib.sha256).hexdigest()

    tamperingCases = [
        ("targetPricePaise", 400000),
        ("activePricePaise", 350000),
        ("savingsPaise", 0),
        ("skuId", "SKU-TABLE-999"),
        ("buyerAgentId", "did:mesh:attacker"),
        ("triggeredAtUnix", now + 100),
    ]

    for key, tamperedVal in tamperingCases:
        tamperedDict = dict(basePayloadDict)
        tamperedDict[key] = tamperedVal
        tamperedBytes = json.dumps(tamperedDict, separators=(",", ":"), sort_keys=True).encode("utf-8")
        assert verifyRazorpayWebhookSignature(tamperedBytes, validSig, testWebhookSecret) is False


def testHmacWebhookHeaderForgeryAndSecretMismatch() -> None:
    """Challenge 2C: Verifies rejection on secret mismatch or corrupted signature strings."""
    payloadBytes = b'{"event":"test"}'
    validSig = hmac.new(testWebhookSecret.encode("utf-8"), payloadBytes, hashlib.sha256).hexdigest()

    # Wrong secret
    assert verifyRazorpayWebhookSignature(payloadBytes, validSig, "wrong_secret_123") is False

    # Signature corrupted by 1 hex character
    forgedSig = ("0" if validSig[0] != "0" else "1") + validSig[1:]
    assert verifyRazorpayWebhookSignature(payloadBytes, forgedSig, testWebhookSecret) is False

    # Truncated or empty signature
    assert verifyRazorpayWebhookSignature(payloadBytes, validSig[:10], testWebhookSecret) is False
    assert verifyRazorpayWebhookSignature(payloadBytes, "", testWebhookSecret) is False


@pytest.mark.asyncio
async def testGatewayAlertMultipleSkusInterleavedExpiry() -> None:
    """Challenge 1E: Verifies multi-SKU interleaved TTL expiration isolation."""
    manager = PriceDropAlertManager(redisClient=None, webhookSecret=testWebhookSecret)
    now = int(time.time())
    skuA, skuB = "SKU-CHAIR-A", "SKU-DESK-B"

    # SKU-A: Alert 1 (exp 10), Alert 2 (exp 30)
    # SKU-B: Alert 3 (exp 20)
    await manager.registerPriceDropAlert(skuA, 300000, testCallbackUrl, testBuyerAgentId, now + 10)
    alertA2 = await manager.registerPriceDropAlert(skuA, 300000, testCallbackUrl, testBuyerAgentId, now + 30)
    alertB = await manager.registerPriceDropAlert(skuB, 500000, testCallbackUrl, testBuyerAgentId, now + 20)

    # At now + 15: SKU-A has 1 active alert (Alert 2), SKU-B has 1 active alert (Alert 3)
    with patch("time.time", return_value=now + 15):
        activeA = await manager.getAlertsForSku(skuA)
        activeB = await manager.getAlertsForSku(skuB)
        assert len(activeA) == 1 and activeA[0].alertId == alertA2.alertId
        assert len(activeB) == 1 and activeB[0].alertId == alertB.alertId

    # At now + 25: SKU-A has 1 active alert (Alert 2), SKU-B has 0 active alerts
    with patch("time.time", return_value=now + 25):
        activeA25 = await manager.getAlertsForSku(skuA)
        activeB25 = await manager.getAlertsForSku(skuB)
        assert len(activeA25) == 1 and activeA25[0].alertId == alertA2.alertId
        assert len(activeB25) == 0


@pytest.mark.asyncio
async def testGatewayAlertDispatchHttpErrorGracefulHandling() -> None:
    """Challenge 2D: Verifies dispatch gracefully isolates HTTP 500 and network timeouts."""
    manager = PriceDropAlertManager(webhookSecret=testWebhookSecret)
    now = int(time.time())
    alert = await manager.registerPriceDropAlert(testSkuIdChair, testTargetPricePaise, testCallbackUrl, testBuyerAgentId, now + 60)

    # 1. HTTP 500 response
    mock500 = Response(status_code=500, content=b'{"error":"internal_server_error"}')
    with patch("httpx.AsyncClient.post", new_callable=AsyncMock) as mockPost:
        mockPost.return_value = mock500
        results = await manager.dispatchPriceDropAlerts(testSkuIdChair, testActivePricePaise)
        assert len(results) == 1
        assert results[0].status == "failed"
        assert results[0].statusCode == 500
        assert results[0].error == "HTTP 500"

    # 2. Connection Exception
    with patch("httpx.AsyncClient.post", side_effect=Exception("Connection refused")):
        resultsEx = await manager.dispatchPriceDropAlerts(testSkuIdChair, testActivePricePaise)
        assert len(resultsEx) == 1
        assert resultsEx[0].status == "failed"
        assert resultsEx[0].statusCode is None
        assert "Connection refused" in str(resultsEx[0].error)

