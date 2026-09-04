"""Unit tests for Workstream D: Human Checkout order creation and HMAC verification endpoints."""

import hashlib
import hmac
import pytest
from fastapi.testclient import TestClient

from razoragentMesh.packages.mandateEngine.config import MandateEngineSettings
from razoragentMesh.packages.mandateEngine.mandateApp import createMandateApp
from razoragentMesh.packages.mandateEngine.settlement.razorpayRouteClient import (
    RazorpayOrderResponse,
    RazorpayRouteClient,
)


@pytest.fixture
def checkoutApp():
    """Builds a test FastAPI application instance with mocked Route client."""
    app = createMandateApp()
    return app


def testVerifyAcceptsValidSignature(checkoutApp, monkeypatch: pytest.MonkeyPatch) -> None:
    """Requirement 1: verify accepts a correct signature computed with the test secret."""
    testKeySecret = "test_secret_for_hmac_verification_12345"
    testKeyId = "rzp_test_testKeyId12345"
    testOrderId = "order_rzp_99887766"
    testPaymentId = "pay_rzp_55443322"

    testSettings = MandateEngineSettings(
        razorpayKeyId=testKeyId,
        razorpayKeySecret=testKeySecret,
    )
    monkeypatch.setattr(
        "razoragentMesh.packages.mandateEngine.checkout.checkoutRoute.getMandateEngineSettings",
        lambda: testSettings,
    )

    validSignature = hmac.new(
        testKeySecret.encode("utf-8"),
        f"{testOrderId}|{testPaymentId}".encode("utf-8"),
        hashlib.sha256,
    ).hexdigest()

    client = TestClient(checkoutApp, raise_server_exceptions=False)
    response = client.post(
        "/api/v1/checkout/verify",
        json={
            "razorpayOrderId": testOrderId,
            "razorpayPaymentId": testPaymentId,
            "razorpaySignature": validSignature,
        },
    )

    assert response.status_code == 200
    data = response.json()
    assert data["verified"] is True
    assert data["orderId"] == testOrderId
    assert data["paymentId"] == testPaymentId


def testVerifyRejectsTamperedSignature(checkoutApp, monkeypatch: pytest.MonkeyPatch) -> None:
    """Requirement 2: verify rejects a tampered signature with 400 and verified: false."""
    testKeySecret = "test_secret_for_hmac_verification_12345"
    testKeyId = "rzp_test_testKeyId12345"
    testOrderId = "order_rzp_99887766"
    testPaymentId = "pay_rzp_55443322"

    testSettings = MandateEngineSettings(
        razorpayKeyId=testKeyId,
        razorpayKeySecret=testKeySecret,
    )
    monkeypatch.setattr(
        "razoragentMesh.packages.mandateEngine.checkout.checkoutRoute.getMandateEngineSettings",
        lambda: testSettings,
    )

    tamperedSignature = "bad_signature_0000000000000000000000000000000000000000000000000000"

    client = TestClient(checkoutApp, raise_server_exceptions=False)
    response = client.post(
        "/api/v1/checkout/verify",
        json={
            "razorpayOrderId": testOrderId,
            "razorpayPaymentId": testPaymentId,
            "razorpaySignature": tamperedSignature,
        },
    )

    assert response.status_code == 400
    data = response.json()
    assert data["verified"] is False


def testVerifyRejectsMissingFieldsWith400(checkoutApp, monkeypatch: pytest.MonkeyPatch) -> None:
    """Requirement 3: verify rejects missing fields with 400."""
    testSettings = MandateEngineSettings(
        razorpayKeyId="rzp_test_validKey",
        razorpayKeySecret="validSecret",
    )
    monkeypatch.setattr(
        "razoragentMesh.packages.mandateEngine.checkout.checkoutRoute.getMandateEngineSettings",
        lambda: testSettings,
    )

    client = TestClient(checkoutApp, raise_server_exceptions=False)

    # Missing signature
    resp1 = client.post(
        "/api/v1/checkout/verify",
        json={"razorpayOrderId": "order_123", "razorpayPaymentId": "pay_123"},
    )
    assert resp1.status_code == 400

    # Missing paymentId
    resp2 = client.post(
        "/api/v1/checkout/verify",
        json={"razorpayOrderId": "order_123", "razorpaySignature": "sig_123"},
    )
    assert resp2.status_code == 400

    # Empty payload
    resp3 = client.post("/api/v1/checkout/verify", json={})
    assert resp3.status_code == 400


def testCreateOrderReturns400BelowMinimumAmount(checkoutApp, monkeypatch: pytest.MonkeyPatch) -> None:
    """Requirement 4: createOrder endpoint returns 400 for amountPaise < 100."""
    testSettings = MandateEngineSettings(
        razorpayKeyId="rzp_test_validKey",
        razorpayKeySecret="validSecret",
    )
    monkeypatch.setattr(
        "razoragentMesh.packages.mandateEngine.checkout.checkoutRoute.getMandateEngineSettings",
        lambda: testSettings,
    )

    client = TestClient(checkoutApp, raise_server_exceptions=False)
    response = client.post(
        "/api/v1/checkout/order",
        json={"amountPaise": 99, "receipt": "rcpt_test_001"},
    )
    assert response.status_code == 400
    assert "at least 100 paise" in response.text


def testCreateOrderReturns503WhenCredentialsAbsent(checkoutApp, monkeypatch: pytest.MonkeyPatch) -> None:
    """Requirement 5: createOrder endpoint returns 503 when credentials are absent."""
    testSettings = MandateEngineSettings(razorpayKeyId="", razorpayKeySecret="")
    monkeypatch.setattr(
        "razoragentMesh.packages.mandateEngine.checkout.checkoutRoute.getMandateEngineSettings",
        lambda: testSettings,
    )

    client = TestClient(checkoutApp, raise_server_exceptions=False)
    response = client.post(
        "/api/v1/checkout/order",
        json={"amountPaise": 500000, "receipt": "rcpt_test_002"},
    )
    assert response.status_code == 503
    assert "requires Razorpay test-mode credentials" in response.text


def testCreateOrderSuccessWithMockTransport(checkoutApp, monkeypatch: pytest.MonkeyPatch) -> None:
    """Verifies successful order creation through the checkout endpoint."""
    testKeyId = "rzp_test_validKey123"
    testSettings = MandateEngineSettings(
        razorpayKeyId=testKeyId,
        razorpayKeySecret="validSecret456",
    )
    monkeypatch.setattr(
        "razoragentMesh.packages.mandateEngine.checkout.checkoutRoute.getMandateEngineSettings",
        lambda: testSettings,
    )

    async def mockCreateOrder(amountPaise: int, receipt: str, notes=None):
        return RazorpayOrderResponse(
            id="order_test_created_123",
            entity="order",
            amount=amountPaise,
            currency="INR",
            receipt=receipt,
            status="created",
            createdAt=1700000000,
        )

    mockRouteClient = RazorpayRouteClient(isMockMode=True, ordersLive=False)
    monkeypatch.setattr(mockRouteClient, "createOrder", mockCreateOrder)
    checkoutApp.state.routeClient = mockRouteClient

    client = TestClient(checkoutApp, raise_server_exceptions=False)
    response = client.post(
        "/api/v1/checkout/order",
        json={"amountPaise": 19900000, "receipt": "rcpt_human_001"},
    )
    assert response.status_code == 200
    data = response.json()
    assert data["orderId"] == "order_test_created_123"
    assert data["amountPaise"] == 19900000
    assert data["currency"] == "INR"
    assert data["keyId"] == testKeyId
