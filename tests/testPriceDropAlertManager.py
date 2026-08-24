"""Comprehensive unit and integration tests for PriceDropAlertManager and alertsRoute."""

import json
import time
import pytest
from httpx import ASGITransport, AsyncClient, Response

from razoragentMesh.packages.mandateEngine.settlement.settlementExceptions import ArithmeticDriftException
from razoragentMesh.packages.mandateEngine.settlement.webhookVerifier import verifyRazorpayWebhookSignature
from razoragentMesh.packages.x402Gateway import (
    PriceDropAlertManager,
    app,
)
from razoragentMesh.tests.mockInfraHelpers import MockRedisAsync

defaultTestSecret: str = "rzp_test_secret_key_price_drop_alerts"
testSkuId: str = "SKU-CHAIR-001"
testBuyerDid: str = "did:agent:buyer-procurement-01"
testCallbackUrl: str = "https://buyer.agent.internal/webhooks/price-drop"


class MockHttpClient:
    """Mock HTTP client recording POST requests and responses."""

    def __init__(self, statusCode: int = 200) -> None:
        self.statusCode = statusCode
        self.dispatchedRequests: list[dict[str, object]] = []

    async def post(
        self,
        url: str,
        content: bytes,
        headers: dict[str, str],
        timeout: float = 5.0,
    ) -> Response:
        self.dispatchedRequests.append({
            "url": url,
            "content": content,
            "headers": headers,
            "timeout": timeout,
        })
        if self.statusCode >= 500:
            return Response(status_code=self.statusCode, content=b"Internal Server Error")
        return Response(status_code=self.statusCode, content=b'{"status":"received"}')


class FailingHttpClient:
    """Mock HTTP client simulating network connection failures."""

    async def post(
        self,
        url: str,
        content: bytes,
        headers: dict[str, str],
        timeout: float = 5.0,
    ) -> Response:
        raise ConnectionResetError("Connection reset by peer")


@pytest.mark.asyncio
async def testAlertRegistrationAndValidationInMemory() -> None:
    """Verifies in-memory alert registration, input validation, and rejection cases."""
    manager = PriceDropAlertManager(webhookSecret=defaultTestSecret)
    now = int(time.time())
    futureExpiry = now + 3600

    # 1. Successful registration
    alert = await manager.registerPriceDropAlert(
        skuId=testSkuId,
        targetPricePaise=350000,
        callbackUrl=testCallbackUrl,
        buyerAgentId=testBuyerDid,
        expiresAtUnix=futureExpiry,
    )
    assert alert.skuId == testSkuId
    assert alert.targetPricePaise == 350000
    assert alert.status == "active"
    assert alert.alertId.startswith("alert_")

    # 2. Rejection on past expiry timestamp
    with pytest.raises(ValueError, match="Alert expiry timestamp must be in the future"):
        await manager.registerPriceDropAlert(
            skuId=testSkuId,
            targetPricePaise=350000,
            callbackUrl=testCallbackUrl,
            buyerAgentId=testBuyerDid,
            expiresAtUnix=now - 100,
        )

    # 3. Rejection on zero or negative price
    with pytest.raises(ValueError, match="Target price must be positive"):
        await manager.registerPriceDropAlert(
            skuId=testSkuId,
            targetPricePaise=0,
            callbackUrl=testCallbackUrl,
            buyerAgentId=testBuyerDid,
            expiresAtUnix=futureExpiry,
        )

    # 4. Rejection on float price
    with pytest.raises(ArithmeticDriftException):
        await manager.registerPriceDropAlert(
            skuId=testSkuId,
            targetPricePaise=3500.50,  # type: ignore
            callbackUrl=testCallbackUrl,
            buyerAgentId=testBuyerDid,
            expiresAtUnix=futureExpiry,
        )


@pytest.mark.asyncio
async def testAlertQueryAndExpiryFiltering() -> None:
    """Verifies that getAlertsForSku filters out expired alerts."""
    manager = PriceDropAlertManager(webhookSecret=defaultTestSecret)
    now = int(time.time())

    # Register active alert
    alertActive = await manager.registerPriceDropAlert(
        skuId="SKU-TABLE-001",
        targetPricePaise=500000,
        callbackUrl=testCallbackUrl,
        buyerAgentId=testBuyerDid,
        expiresAtUnix=now + 1800,
    )

    # Manually inject expired alert into in-memory store
    manager._inMemoryAlerts["SKU-TABLE-001"].append({
        "alertId": "alert_expired_test",
        "skuId": "SKU-TABLE-001",
        "targetPricePaise": 480000,
        "callbackUrl": testCallbackUrl,
        "buyerAgentId": testBuyerDid,
        "expiresAtUnix": now - 10,
        "createdAtUnix": now - 3600,
        "status": "active",
    })

    alerts = await manager.getAlertsForSku("SKU-TABLE-001")
    assert len(alerts) == 1
    assert alerts[0].alertId == alertActive.alertId


@pytest.mark.asyncio
async def testAlertCancellationInMemory() -> None:
    """Verifies alert cancellation and secondary lookup cleanup."""
    manager = PriceDropAlertManager(webhookSecret=defaultTestSecret)
    now = int(time.time())

    alert = await manager.registerPriceDropAlert(
        skuId=testSkuId,
        targetPricePaise=300000,
        callbackUrl=testCallbackUrl,
        buyerAgentId=testBuyerDid,
        expiresAtUnix=now + 3600,
    )

    # Cancel existing
    assert await manager.cancelPriceDropAlert(alert.alertId) is True
    # Double cancel returns False
    assert await manager.cancelPriceDropAlert(alert.alertId) is False
    # Non-existent returns False
    assert await manager.cancelPriceDropAlert("alert_unknown_999") is False

    # Check alert list is empty
    alerts = await manager.getAlertsForSku(testSkuId)
    assert len(alerts) == 0


@pytest.mark.asyncio
async def testAlertDispatchAndHmacSignature() -> None:
    """Verifies dispatch condition, HMAC-SHA256 signature headers, and payload."""
    mockHttp = MockHttpClient()
    manager = PriceDropAlertManager(webhookSecret=defaultTestSecret, httpClient=mockHttp)
    now = int(time.time())

    # Register 2 alerts: target ₹3,500 and target ₹3,000
    alertHigh = await manager.registerPriceDropAlert(
        skuId=testSkuId,
        targetPricePaise=350000,
        callbackUrl=testCallbackUrl,
        buyerAgentId=testBuyerDid,
        expiresAtUnix=now + 3600,
    )
    await manager.registerPriceDropAlert(
        skuId=testSkuId,
        targetPricePaise=300000,
        callbackUrl="https://buyer2.agent/callback",
        buyerAgentId="did:agent:buyer-02",
        expiresAtUnix=now + 3600,
    )

    # Active price drops to ₹3,200 (320000 paise)
    # alertHigh (350000 >= 320000) matches; alertLow (300000 < 320000) does not match
    results = await manager.dispatchPriceDropAlerts(testSkuId, activePricePaise=320000)
    assert len(results) == 1
    assert results[0].alertId == alertHigh.alertId
    assert results[0].status == "dispatched"
    assert results[0].statusCode == 200

    # Verify HTTP request was dispatched
    assert len(mockHttp.dispatchedRequests) == 1
    dispatched = mockHttp.dispatchedRequests[0]
    payloadBytes = dispatched["content"]
    assert isinstance(payloadBytes, bytes)
    headers = dispatched["headers"]
    assert isinstance(headers, dict)

    # Verify HMAC signatures in headers match raw payload
    meshSig = headers["X-Mesh-Signature"]
    rzpSig = headers["X-Razorpay-Signature"]
    assert meshSig == rzpSig
    assert verifyRazorpayWebhookSignature(payloadBytes, rzpSig, defaultTestSecret) is True

    # Parse and verify payload
    payloadDict = json.loads(payloadBytes.decode("utf-8"))
    assert payloadDict["event"] == "mesh.price_drop.triggered"
    assert payloadDict["alertId"] == alertHigh.alertId
    assert payloadDict["skuId"] == testSkuId
    assert payloadDict["targetPricePaise"] == 350000
    assert payloadDict["activePricePaise"] == 320000
    assert payloadDict["savingsPaise"] == 30000


@pytest.mark.asyncio
async def testAlertDispatchFaultIsolation() -> None:
    """Verifies that failed webhooks return failed status without crashing dispatcher."""
    failingHttp = FailingHttpClient()
    manager = PriceDropAlertManager(webhookSecret=defaultTestSecret, httpClient=failingHttp)
    now = int(time.time())

    await manager.registerPriceDropAlert(
        skuId=testSkuId,
        targetPricePaise=400000,
        callbackUrl="https://offline.receiver/webhook",
        buyerAgentId=testBuyerDid,
        expiresAtUnix=now + 3600,
    )

    results = await manager.dispatchPriceDropAlerts(testSkuId, activePricePaise=350000)
    assert len(results) == 1
    assert results[0].status == "failed"
    assert results[0].statusCode is None
    assert "Connection reset by peer" in str(results[0].error)


@pytest.mark.asyncio
async def testAlertManagerWithMockRedis() -> None:
    """Verifies PriceDropAlertManager operations with MockRedisAsync."""
    mockRedis = MockRedisAsync()
    manager = PriceDropAlertManager(redisClient=mockRedis, webhookSecret=defaultTestSecret)
    now = int(time.time())

    alert = await manager.registerPriceDropAlert(
        skuId="SKU-REDIS-001",
        targetPricePaise=250000,
        callbackUrl=testCallbackUrl,
        buyerAgentId=testBuyerDid,
        expiresAtUnix=now + 3600,
    )

    # Verify Redis keys
    skuBucket = await mockRedis.get("mesh:alerts:priceDrop:SKU-REDIS-001")
    assert skuBucket is not None
    assert alert.alertId in skuBucket

    lookupVal = await mockRedis.get(f"mesh:alerts:lookup:{alert.alertId}")
    assert lookupVal == "SKU-REDIS-001"

    # Query alerts via manager
    alerts = await manager.getAlertsForSku("SKU-REDIS-001")
    assert len(alerts) == 1
    assert alerts[0].alertId == alert.alertId

    # Cancel alert via manager
    cancelled = await manager.cancelPriceDropAlert(alert.alertId)
    assert cancelled is True

    # Lookup key should be purged
    assert await mockRedis.get(f"mesh:alerts:lookup:{alert.alertId}") is None


@pytest.mark.asyncio
async def testGatewayAlertsRestRoutes() -> None:
    """Integration test for FastAPI /api/v1/alerts endpoints."""
    transport = ASGITransport(app=app)
    async with AsyncClient(transport=transport, base_url="http://testserver") as client:
        now = int(time.time())

        # 1. Register alert via POST /api/v1/alerts/price-drop -> 201 Created
        reqPayload = {
            "skuId": "SKU-DESK-001",
            "targetPricePaise": 850000,
            "callbackUrl": "https://buyer-desk.internal/hook",
            "buyerAgentId": "did:agent:buyer-desk",
            "expiresAtUnix": now + 7200,
        }
        respCreate = await client.post("/api/v1/alerts/price-drop", json=reqPayload)
        assert respCreate.status_code == 201
        data = respCreate.json()
        assert data["skuId"] == "SKU-DESK-001"
        assert data["targetPricePaise"] == 850000
        assert data["status"] == "active"
        alertId = data["alertId"]

        # 2. Register alert with past expiry -> 400 Bad Request
        respFail = await client.post(
            "/api/v1/alerts/price-drop",
            json={**reqPayload, "expiresAtUnix": now - 100},
        )
        assert respFail.status_code == 400

        # 3. Cancel alert via DELETE /api/v1/alerts/price-drop/{alertId} -> 200 OK
        respCancel = await client.delete(f"/api/v1/alerts/price-drop/{alertId}")
        assert respCancel.status_code == 200
        assert respCancel.json()["cancelled"] is True

        # 4. Cancel non-existent alert -> 404 Not Found
        respNotFound = await client.delete(f"/api/v1/alerts/price-drop/{alertId}")
        assert respNotFound.status_code == 404
