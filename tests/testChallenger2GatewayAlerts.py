"""Empirical Challenger 2 Test Suite: Gateway Alerts TTL, Cancellation and HTTP Isolation."""

import time
from unittest.mock import AsyncMock, patch
from httpx import Response
import pytest

from razoragentMesh.packages.mandateEngine.settlement.settlementExceptions import (
    ArithmeticDriftException,
)
from razoragentMesh.packages.x402Gateway.src.alerts.priceDropAlertManager import (
    PriceDropAlertManager,
)
from razoragentMesh.tests.mockInfraHelpers import MockRedisAsync

testSkuIdChair: str = "SKU-CHAIR-001"
testTargetPricePaise: int = 350000
testActivePricePaise: int = 340000
testBuyerAgentId: str = "did:mesh:buyer_challenger2"
testCallbackUrl: str = "https://buyer-agent.mesh/api/v1/webhook"
testWebhookSecret: str = "whsec_adversarial_test_secret_2026"


@pytest.mark.asyncio
async def testGatewayAlertTtlPruningInMemory() -> None:
    """Challenge 1A: Verifies alert expiry filtering and automatic pruning in memory."""
    manager = PriceDropAlertManager(redisClient=None, webhookSecret=testWebhookSecret)
    now = int(time.time())

    alertA = await manager.registerPriceDropAlert(
        skuId=testSkuIdChair, targetPricePaise=testTargetPricePaise,
        callbackUrl=testCallbackUrl, buyerAgentId=testBuyerAgentId, expiresAtUnix=now + 10,
    )
    alertB = await manager.registerPriceDropAlert(
        skuId=testSkuIdChair, targetPricePaise=testTargetPricePaise,
        callbackUrl=testCallbackUrl, buyerAgentId=testBuyerAgentId, expiresAtUnix=now + 100,
    )
    assert len(await manager.getAlertsForSku(testSkuIdChair)) == 2

    with patch("time.time", return_value=now + 20):
        activeAfter = await manager.getAlertsForSku(testSkuIdChair)
        assert len(activeAfter) == 1 and activeAfter[0].alertId == alertB.alertId
        mockResponse = Response(status_code=200, content=b'{"status":"ok"}')
        with patch("httpx.AsyncClient.post", new_callable=AsyncMock) as mockPost:
            mockPost.return_value = mockResponse
            results = await manager.dispatchPriceDropAlerts(testSkuIdChair, testActivePricePaise)
            assert len(results) == 1 and results[0].alertId == alertB.alertId

    with patch("time.time", return_value=now + 200):
        assert len(await manager.getAlertsForSku(testSkuIdChair)) == 0
        assert len(await manager.dispatchPriceDropAlerts(testSkuIdChair, testActivePricePaise)) == 0


@pytest.mark.asyncio
async def testGatewayAlertTtlPruningMockRedis() -> None:
    """Challenge 1B: Verifies alert expiry filtering and Redis bucket TTL isolation."""
    mockRedis = MockRedisAsync()
    manager = PriceDropAlertManager(redisClient=mockRedis, webhookSecret=testWebhookSecret)
    now = int(time.time())

    alert = await manager.registerPriceDropAlert(
        skuId=testSkuIdChair, targetPricePaise=testTargetPricePaise,
        callbackUrl=testCallbackUrl, buyerAgentId=testBuyerAgentId, expiresAtUnix=now + 30,
    )
    assert alert.alertId.startswith("alert_")
    bucketKey = f"mesh:alerts:priceDrop:{testSkuIdChair}"
    assert await mockRedis.get(bucketKey) is not None

    with patch("time.time", return_value=now + 50):
        assert len(await manager.getAlertsForSku(testSkuIdChair)) == 0


@pytest.mark.asyncio
async def testGatewayAlertCancellationAndIndexPruning() -> None:
    """Challenge 1C: Verifies alert cancellation cleans up lookup index and bucket keys."""
    mockRedis = MockRedisAsync()
    manager = PriceDropAlertManager(redisClient=mockRedis, webhookSecret=testWebhookSecret)
    now = int(time.time())

    alert1 = await manager.registerPriceDropAlert(testSkuIdChair, testTargetPricePaise, testCallbackUrl, testBuyerAgentId, now + 300)
    alert2 = await manager.registerPriceDropAlert(testSkuIdChair, testTargetPricePaise, testCallbackUrl, testBuyerAgentId, now + 300)

    assert await manager.cancelPriceDropAlert(alert1.alertId) is True
    assert await manager.cancelPriceDropAlert(alert1.alertId) is False

    remaining = await manager.getAlertsForSku(testSkuIdChair)
    assert len(remaining) == 1 and remaining[0].alertId == alert2.alertId

    assert await manager.cancelPriceDropAlert(alert2.alertId) is True
    assert await mockRedis.get(f"mesh:alerts:priceDrop:{testSkuIdChair}") is None


@pytest.mark.asyncio
async def testGatewayAlertRegistrationInputValidation() -> None:
    """Challenge 1D: Verifies adversarial input rejection on alert registration."""
    manager = PriceDropAlertManager()
    now = int(time.time())

    with pytest.raises(ValueError, match="future"):
        await manager.registerPriceDropAlert(testSkuIdChair, testTargetPricePaise, testCallbackUrl, testBuyerAgentId, now - 10)

    with pytest.raises(ValueError, match="positive"):
        await manager.registerPriceDropAlert(testSkuIdChair, 0, testCallbackUrl, testBuyerAgentId, now + 300)

    with pytest.raises(ArithmeticDriftException):
        await manager.registerPriceDropAlert(testSkuIdChair, 3500.50, testCallbackUrl, testBuyerAgentId, now + 300)  # type: ignore[arg-type]


@pytest.mark.asyncio
async def testGatewayAlertMultipleSkusInterleavedExpiry() -> None:
    """Challenge 1E: Verifies multi-SKU interleaved TTL expiration isolation."""
    manager = PriceDropAlertManager(redisClient=None, webhookSecret=testWebhookSecret)
    now = int(time.time())
    skuA, skuB = "SKU-CHAIR-A", "SKU-DESK-B"

    await manager.registerPriceDropAlert(skuA, 300000, testCallbackUrl, testBuyerAgentId, now + 10)
    alertA2 = await manager.registerPriceDropAlert(skuA, 300000, testCallbackUrl, testBuyerAgentId, now + 30)
    alertB = await manager.registerPriceDropAlert(skuB, 500000, testCallbackUrl, testBuyerAgentId, now + 20)

    with patch("time.time", return_value=now + 15):
        activeA = await manager.getAlertsForSku(skuA)
        activeB = await manager.getAlertsForSku(skuB)
        assert len(activeA) == 1 and activeA[0].alertId == alertA2.alertId
        assert len(activeB) == 1 and activeB[0].alertId == alertB.alertId

    with patch("time.time", return_value=now + 25):
        assert len(await manager.getAlertsForSku(skuA)) == 1
        assert len(await manager.getAlertsForSku(skuB)) == 0


@pytest.mark.asyncio
async def testGatewayAlertDispatchHttpErrorGracefulHandling() -> None:
    """Challenge 2D: Verifies dispatch gracefully isolates HTTP 500 and network timeouts."""
    manager = PriceDropAlertManager(webhookSecret=testWebhookSecret)
    now = int(time.time())
    await manager.registerPriceDropAlert(testSkuIdChair, testTargetPricePaise, testCallbackUrl, testBuyerAgentId, now + 60)

    mock500 = Response(status_code=500, content=b'{"error":"internal_server_error"}')
    with patch("httpx.AsyncClient.post", new_callable=AsyncMock) as mockPost:
        mockPost.return_value = mock500
        results = await manager.dispatchPriceDropAlerts(testSkuIdChair, testActivePricePaise)
        assert len(results) == 1 and results[0].status == "failed" and results[0].statusCode == 500

    with patch("httpx.AsyncClient.post", side_effect=Exception("Connection refused")):
        resultsEx = await manager.dispatchPriceDropAlerts(testSkuIdChair, testActivePricePaise)
        assert len(resultsEx) == 1 and resultsEx[0].status == "failed" and "Connection refused" in str(resultsEx[0].error)
