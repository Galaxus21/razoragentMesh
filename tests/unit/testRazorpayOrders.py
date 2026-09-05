"""Unit tests for Razorpay Orders API decoupling and settlement saga evidence."""

import json
import pytest
import httpx

from razoragentMesh.packages.mandateEngine.config import MandateEngineSettings
from razoragentMesh.packages.mandateEngine.settlement.razorpayRouteClient import (
    RazorpayRouteClient,
    RouteTransferRequest,
    minRazorpayOrderAmountPaise,
)
from razoragentMesh.packages.mandateEngine.settlement.routeClientFactory import buildRouteClient
from razoragentMesh.packages.mandateEngine.settlement.settlementExceptions import MandateEngineException


@pytest.mark.asyncio
async def testCreateOrderMockMode() -> None:
    """Verifies createOrder in mock mode returns an order_mock_ prefix and makes zero HTTP calls."""
    httpCallsMade = 0

    def mockHandler(request: httpx.Request) -> httpx.Response:
        nonlocal httpCallsMade
        httpCallsMade += 1
        return httpx.Response(status_code=200, json={})

    mockTransport = httpx.MockTransport(mockHandler)
    async with httpx.AsyncClient(transport=mockTransport) as httpClient:
        client = RazorpayRouteClient(isMockMode=True, ordersLive=False, httpClient=httpClient)
        res = await client.createOrder(
            amountPaise=19900000,
            receipt="mandate_exec_12345678",
            currency="INR",
            notes={"executionId": "mandate_exec_12345678", "cartHash": "hash123"},
        )
        assert res.id.startswith("order_mock_")
        assert res.amount == 19900000
        assert res.currency == "INR"
        assert res.receipt == "mandate_exec_12345678"
        assert res.status == "created"
        assert httpCallsMade == 0


@pytest.mark.asyncio
async def testCreateOrderLiveMode() -> None:
    """Verifies createOrder in live mode sends POST /v1/orders with expected body and headers."""
    capturedRequest: dict = {}

    def mockHandler(request: httpx.Request) -> httpx.Response:
        capturedRequest["method"] = request.method
        capturedRequest["url"] = str(request.url)
        capturedRequest["headers"] = dict(request.headers)
        capturedRequest["body"] = json.loads(request.content.decode("utf-8"))
        return httpx.Response(
            status_code=200,
            json={
                "id": "order_live_998877",
                "entity": "order",
                "amount": 250000,
                "currency": "INR",
                "receipt": "mandate_exec_abc",
                "status": "created",
                "created_at": 1700000000,
            },
        )

    mockTransport = httpx.MockTransport(mockHandler)
    async with httpx.AsyncClient(transport=mockTransport) as httpClient:
        client = RazorpayRouteClient(
            apiKey="rzp_test_realKey123",
            apiSecret="realSecret456",
            isMockMode=True,
            ordersLive=True,
            httpClient=httpClient,
        )
        res = await client.createOrder(
            amountPaise=250000,
            receipt="mandate_exec_abc",
            currency="INR",
            notes={"executionId": "mandate_exec_abc", "buyerAgentDid": "did:mesh:buyer1"},
        )
        assert res.id == "order_live_998877"
        assert res.status == "created"
        assert capturedRequest["method"] == "POST"
        assert capturedRequest["url"] == "https://api.razorpay.com/v1/orders"
        assert capturedRequest["headers"]["authorization"].startswith("Basic ")
        assert capturedRequest["body"]["amount"] == 250000
        assert capturedRequest["body"]["currency"] == "INR"
        assert capturedRequest["body"]["receipt"] == "mandate_exec_abc"
        assert capturedRequest["body"]["notes"]["executionId"] == "mandate_exec_abc"


@pytest.mark.asyncio
async def testCreateOrderMinimumAmountValidation() -> None:
    """Verifies that createOrder enforces minimum amount of 100 paise."""
    client = RazorpayRouteClient(isMockMode=True, ordersLive=False)
    with pytest.raises(MandateEngineException) as excInfo:
        await client.createOrder(amountPaise=99, receipt="test")
    assert "at least 100 paise" in str(excInfo.value)


@pytest.mark.asyncio
async def testRegressionCaptureAndTransfersStayMockedWhenRouteLiveFalse() -> None:
    """CRITICAL REGRESSION: hasRazorpayCredentials=True with routeTransportLive=False

    Ensures capturePayment and createTransfer execute purely locally without HTTP requests.
    """
    httpCallsMade = 0

    def mockHandler(request: httpx.Request) -> httpx.Response:
        nonlocal httpCallsMade
        httpCallsMade += 1
        return httpx.Response(status_code=500, json={"error": "Should not be called"})

    mockTransport = httpx.MockTransport(mockHandler)
    async with httpx.AsyncClient(transport=mockTransport) as httpClient:
        settings = MandateEngineSettings(
            razorpayKeyId="rzp_test_RealCredentialsKey",
            razorpayKeySecret="RealSecret12345",
            routeTransportLive=False,
        )
        assert settings.hasRazorpayCredentials is True
        assert settings.routeTransportLive is False

        client = buildRouteClient(settings)
        client._httpClient = httpClient

        assert client.ordersLive is True
        assert client.isMockMode is True

        # capturePayment should be mock and make 0 HTTP calls
        captureRes = await client.capturePayment("pay_test_123", 50000)
        assert captureRes.id == "pay_test_123"
        assert captureRes.status == "captured"

        # createTransfer should be mock and make 0 HTTP calls
        transferReq = RouteTransferRequest(
            account="acc_demoMerchantRazorAgent",
            amount=45000,
            currency="INR",
            notes={},
        )
        transferRes = await client.createTransfer(transferReq)
        assert transferRes.account == "acc_demoMerchantRazorAgent"
        assert transferRes.amount == 45000
        assert transferRes.status == "processed"

        assert httpCallsMade == 0


def testRouteClientFactoryTransportSelection() -> None:
    """Verifies buildRouteClient configures isMockMode and ordersLive accurately across configs."""
    # 1. No credentials
    noCreds = MandateEngineSettings(razorpayKeyId="", razorpayKeySecret="")
    client1 = buildRouteClient(noCreds)
    assert client1.isMockMode is True
    assert client1.ordersLive is False

    # 2. Real credentials, routeTransportLive=False
    credsRouteMock = MandateEngineSettings(
        razorpayKeyId="rzp_test_realKey",
        razorpayKeySecret="sec",
        routeTransportLive=False,
    )
    client2 = buildRouteClient(credsRouteMock)
    assert client2.isMockMode is True
    assert client2.ordersLive is True

    # 3. Real credentials, routeTransportLive=True
    credsRouteLive = MandateEngineSettings(
        razorpayKeyId="rzp_test_realKey",
        razorpayKeySecret="sec",
        routeTransportLive=True,
    )
    client3 = buildRouteClient(credsRouteLive)
    assert client3.isMockMode is False
    assert client3.ordersLive is True
