"""Unit and integration tests for PriceDropAlertManager registration, cancellation, and REST routes."""

import time
import pytest
from httpx import ASGITransport, AsyncClient

from razoragentMesh.packages.mandateEngine.settlement.settlementExceptions import ArithmeticDriftException
from razoragentMesh.packages.x402Gateway import (
    PriceDropAlertManager,
    app,
)
from razoragentMesh.tests.mockInfraHelpers import MockRedisAsync

defaultTestSecret: str = "rzp_test_secret_key_price_drop_alerts"
testSkuId: str = "SKU-CHAIR-001"
testBuyerDid: str = "did:agent:buyer-procurement-01"
testCallbackUrl: str = "https://buyer.agent.internal/webhooks/price-drop"


@pytest.mark.asyncio
async def testAlertRegistrationAndValidationInMemory() -> None:
    """Verifies in-memory alert registration, input validation, and rejection cases."""
    manager = PriceDropAlertManager(webhookSecret=defaultTestSecret)
    now = int(time.time())
    futureExpiry = now + 3600

    alert = await manager.registerPriceDropAlert(
        skuId=testSkuId, targetPricePaise=350000,
        callbackUrl=testCallbackUrl, buyerAgentId=testBuyerDid, expiresAtUnix=futureExpiry,
    )
    assert alert.skuId == testSkuId and alert.targetPricePaise == 350000
    assert alert.status == "active" and alert.alertId.startswith("alert_")

    with pytest.raises(ValueError, match="Alert expiry timestamp must be in the future"):
        await manager.registerPriceDropAlert(
            skuId=testSkuId, targetPricePaise=350000,
            callbackUrl=testCallbackUrl, buyerAgentId=testBuyerDid, expiresAtUnix=now - 100,
        )

    with pytest.raises(ValueError, match="Target price must be positive"):
        await manager.registerPriceDropAlert(
            skuId=testSkuId, targetPricePaise=0,
            callbackUrl=testCallbackUrl, buyerAgentId=testBuyerDid, expiresAtUnix=futureExpiry,
        )

    with pytest.raises(ArithmeticDriftException):
        await manager.registerPriceDropAlert(
            skuId=testSkuId, targetPricePaise=3500.50,  # type: ignore
            callbackUrl=testCallbackUrl, buyerAgentId=testBuyerDid, expiresAtUnix=futureExpiry,
        )


@pytest.mark.asyncio
async def testAlertQueryAndExpiryFiltering() -> None:
    """Verifies that getAlertsForSku filters out expired alerts."""
    manager = PriceDropAlertManager(webhookSecret=defaultTestSecret)
    now = int(time.time())

    alertActive = await manager.registerPriceDropAlert(
        skuId="SKU-TABLE-001", targetPricePaise=500000,
        callbackUrl=testCallbackUrl, buyerAgentId=testBuyerDid, expiresAtUnix=now + 1800,
    )
    manager._inMemoryAlerts["SKU-TABLE-001"].append({
        "alertId": "alert_expired_test", "skuId": "SKU-TABLE-001", "targetPricePaise": 480000,
        "callbackUrl": testCallbackUrl, "buyerAgentId": testBuyerDid, "expiresAtUnix": now - 10,
        "createdAtUnix": now - 3600, "status": "active",
    })
    alerts = await manager.getAlertsForSku("SKU-TABLE-001")
    assert len(alerts) == 1 and alerts[0].alertId == alertActive.alertId


@pytest.mark.asyncio
async def testAlertCancellationInMemory() -> None:
    """Verifies alert cancellation and secondary lookup cleanup."""
    manager = PriceDropAlertManager(webhookSecret=defaultTestSecret)
    now = int(time.time())
    alert = await manager.registerPriceDropAlert(
        skuId=testSkuId, targetPricePaise=300000,
        callbackUrl=testCallbackUrl, buyerAgentId=testBuyerDid, expiresAtUnix=now + 3600,
    )
    assert await manager.cancelPriceDropAlert(alert.alertId) is True
    assert await manager.cancelPriceDropAlert(alert.alertId) is False
    assert await manager.cancelPriceDropAlert("alert_unknown_999") is False
    assert len(await manager.getAlertsForSku(testSkuId)) == 0


@pytest.mark.asyncio
async def testAlertManagerWithMockRedis() -> None:
    """Verifies PriceDropAlertManager operations with MockRedisAsync."""
    mockRedis = MockRedisAsync()
    manager = PriceDropAlertManager(redisClient=mockRedis, webhookSecret=defaultTestSecret)
    now = int(time.time())

    alert = await manager.registerPriceDropAlert(
        skuId="SKU-REDIS-001", targetPricePaise=250000,
        callbackUrl=testCallbackUrl, buyerAgentId=testBuyerDid, expiresAtUnix=now + 3600,
    )
    skuBucket = await mockRedis.get("mesh:alerts:priceDrop:SKU-REDIS-001")
    assert skuBucket is not None and alert.alertId in skuBucket
    assert await mockRedis.get(f"mesh:alerts:lookup:{alert.alertId}") == "SKU-REDIS-001"

    alerts = await manager.getAlertsForSku("SKU-REDIS-001")
    assert len(alerts) == 1 and alerts[0].alertId == alert.alertId

    assert await manager.cancelPriceDropAlert(alert.alertId) is True
    assert await mockRedis.get(f"mesh:alerts:lookup:{alert.alertId}") is None


@pytest.mark.asyncio
async def testGatewayAlertsRestRoutes() -> None:
    """Integration test for FastAPI /api/v1/alerts endpoints."""
    transport = ASGITransport(app=app)
    async with AsyncClient(transport=transport, base_url="http://testserver") as client:
        now = int(time.time())
        reqPayload = {
            "skuId": "SKU-DESK-001", "targetPricePaise": 850000,
            "callbackUrl": "https://buyer-desk.internal/hook",
            "buyerAgentId": "did:agent:buyer-desk", "expiresAtUnix": now + 7200,
        }
        respCreate = await client.post("/api/v1/alerts/price-drop", json=reqPayload)
        assert respCreate.status_code == 201
        data = respCreate.json()
        assert data["skuId"] == "SKU-DESK-001" and data["targetPricePaise"] == 850000
        alertId = data["alertId"]

        respFail = await client.post("/api/v1/alerts/price-drop", json={**reqPayload, "expiresAtUnix": now - 100})
        assert respFail.status_code == 400

        respCancel = await client.delete(f"/api/v1/alerts/price-drop/{alertId}")
        assert respCancel.status_code == 200 and respCancel.json()["cancelled"] is True

        respNotFound = await client.delete(f"/api/v1/alerts/price-drop/{alertId}")
        assert respNotFound.status_code == 404
