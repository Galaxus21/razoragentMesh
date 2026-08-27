"""Unit and integration tests for PriceDropAlertManager dispatch and HMAC signatures."""

import json
import time
import pytest
from httpx import Response

from razoragentMesh.packages.mandateEngine.settlement.webhookVerifier import verifyRazorpayWebhookSignature
from razoragentMesh.packages.x402Gateway import (
    PriceDropAlertManager,
)

defaultTestSecret: str = "rzp_test_secret_key_price_drop_alerts"
testSkuId: str = "SKU-CHAIR-001"
testBuyerDid: str = "did:agent:buyer-procurement-01"
testCallbackUrl: str = "https://buyer.agent.internal/webhooks/price-drop"


class MockHttpClient:
    """Mock HTTP client recording POST requests and responses."""

    def __init__(self, statusCode: int = 200) -> None:
        self.statusCode = statusCode
        self.dispatchedRequests: list[dict[str, object]] = []

    async def post(self, url: str, content: bytes, headers: dict[str, str], timeout: float = 5.0) -> Response:
        self.dispatchedRequests.append({"url": url, "content": content, "headers": headers, "timeout": timeout})
        if self.statusCode >= 500:
            return Response(status_code=self.statusCode, content=b"Internal Server Error")
        return Response(status_code=self.statusCode, content=b'{"status":"received"}')


class FailingHttpClient:
    """Mock HTTP client simulating network connection failures."""

    async def post(self, url: str, content: bytes, headers: dict[str, str], timeout: float = 5.0) -> Response:
        raise ConnectionResetError("Connection reset by peer")


@pytest.mark.asyncio
async def testAlertDispatchAndHmacSignature() -> None:
    """Verifies dispatch condition, HMAC-SHA256 signature headers, and payload."""
    mockHttp = MockHttpClient()
    manager = PriceDropAlertManager(webhookSecret=defaultTestSecret, httpClient=mockHttp)
    now = int(time.time())

    alertHigh = await manager.registerPriceDropAlert(
        skuId=testSkuId, targetPricePaise=350000, callbackUrl=testCallbackUrl, buyerAgentId=testBuyerDid, expiresAtUnix=now + 3600,
    )
    await manager.registerPriceDropAlert(
        skuId=testSkuId, targetPricePaise=300000, callbackUrl="https://buyer2.agent/callback", buyerAgentId="did:agent:buyer-02", expiresAtUnix=now + 3600,
    )

    results = await manager.dispatchPriceDropAlerts(testSkuId, activePricePaise=320000)
    assert len(results) == 1 and results[0].alertId == alertHigh.alertId and results[0].status == "dispatched"

    assert len(mockHttp.dispatchedRequests) == 1
    dispatched = mockHttp.dispatchedRequests[0]
    payloadBytes, headers = dispatched["content"], dispatched["headers"]
    assert headers["X-Mesh-Signature"] == headers["X-Razorpay-Signature"]
    assert verifyRazorpayWebhookSignature(payloadBytes, headers["X-Razorpay-Signature"], defaultTestSecret) is True

    payloadDict = json.loads(payloadBytes.decode("utf-8"))
    assert payloadDict["event"] == "mesh.price_drop.triggered"
    assert payloadDict["alertId"] == alertHigh.alertId
    assert payloadDict["targetPricePaise"] == 350000 and payloadDict["activePricePaise"] == 320000


@pytest.mark.asyncio
async def testAlertDispatchFaultIsolation() -> None:
    """Verifies that failed webhooks return failed status without crashing dispatcher."""
    failingHttp = FailingHttpClient()
    manager = PriceDropAlertManager(webhookSecret=defaultTestSecret, httpClient=failingHttp)
    now = int(time.time())

    await manager.registerPriceDropAlert(
        skuId=testSkuId, targetPricePaise=400000, callbackUrl="https://offline.receiver/webhook", buyerAgentId=testBuyerDid, expiresAtUnix=now + 3600,
    )
    results = await manager.dispatchPriceDropAlerts(testSkuId, activePricePaise=350000)
    assert len(results) == 1 and results[0].status == "failed" and results[0].statusCode is None
    assert "Connection reset by peer" in str(results[0].error)
