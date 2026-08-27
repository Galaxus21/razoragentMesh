"""Tests for RazorpayRouteClient nominal operations and HTTP lifecycle (Core Suite)."""

import json
from typing import Any, Dict
import httpx
import pytest

from razoragentMesh.packages.mandateEngine.settlement.razorpayRouteClient import (
    PaymentCaptureResponse,
    RazorpayRouteClient,
    RouteTransferRequest,
    RouteTransferResponse,
    TransferReversalResponse,
)

mockApiKey: str = "rzp_test_mock_123"
mockApiSecret: str = "secret_xyz"
mockMerchantAccount: str = "acc_merchant_prime_01"
mockPaymentId: str = "pay_test_capture_001"
mockAmountPaise: int = 118000
mockTransferPaise: int = 100000

mockPaymentPayload: Dict[str, Any] = {
    "id": mockPaymentId,
    "entity": "payment",
    "amount": mockAmountPaise,
    "currency": "INR",
    "status": "captured",
    "method": "upi",
    "captured": True,
    "created_at": 1700000000,
}

mockTransferPayload: Dict[str, Any] = {
    "id": "trf_live_12345678",
    "entity": "transfer",
    "account": mockMerchantAccount,
    "amount": mockTransferPaise,
    "currency": "INR",
    "status": "processed",
    "created_at": 1700000000,
}

mockReversalPayload: Dict[str, Any] = {
    "id": "rev_live_99887766",
    "entity": "reversal",
    "transfer_id": "trf_live_to_reverse",
    "amount": mockTransferPaise,
    "currency": "INR",
    "status": "processed",
    "created_at": 1700000000,
}


@pytest.mark.asyncio
async def testMockModePaymentCaptureAndTransfers() -> None:
    """Verifies default in-memory ledger operations for capture, transfer, and reversal."""
    client = RazorpayRouteClient(apiKey=mockApiKey, apiSecret=mockApiSecret, isMockMode=True)
    assert client.isMockMode is True

    captureRes = await client.capturePayment(mockPaymentId, mockAmountPaise)
    assert isinstance(captureRes, PaymentCaptureResponse)
    assert captureRes.id == mockPaymentId and captureRes.amount == mockAmountPaise
    assert captureRes.status == "captured" and captureRes.captured is True
    assert mockPaymentId in client._capturedPayments

    transferReq = RouteTransferRequest(
        account=mockMerchantAccount,
        amount=mockTransferPaise,
        notes={"purpose": "merchant_net_settlement"},
    )
    transferRes = await client.createTransfer(transferReq)
    assert isinstance(transferRes, RouteTransferResponse)
    assert transferRes.account == mockMerchantAccount and transferRes.amount == mockTransferPaise
    assert transferRes.id in client._transfers

    reversalRes = await client.reverseTransfer(transferRes.id, mockTransferPaise)
    assert isinstance(reversalRes, TransferReversalResponse)
    assert reversalRes.transferId == transferRes.id and reversalRes.amount == mockTransferPaise
    assert reversalRes.id in client._reversals


@pytest.mark.asyncio
async def testLivePaymentCaptureSuccess() -> None:
    """Verifies live HTTP POST /v1/payments/{id}/capture over httpx MockTransport."""
    def handleCaptureRequest(request: httpx.Request) -> httpx.Response:
        assert request.headers.get("authorization", "").startswith("Basic ")
        assert request.method == "POST"
        assert request.url.path == f"/v1/payments/{mockPaymentId}/capture"
        payload = json.loads(request.content.decode("utf-8"))
        assert payload["amount"] == mockAmountPaise and payload["currency"] == "INR"
        return httpx.Response(status_code=200, json=mockPaymentPayload)

    mockTransport = httpx.MockTransport(handleCaptureRequest)
    async with httpx.AsyncClient(transport=mockTransport) as httpClient:
        client = RazorpayRouteClient(
            apiKey=mockApiKey, apiSecret=mockApiSecret,
            baseUrl="https://api.razorpay.com/v1", isMockMode=False, httpClient=httpClient,
        )
        res = await client.capturePayment(mockPaymentId, mockAmountPaise)
        assert res.id == mockPaymentId and res.amount == mockAmountPaise
        assert res.status == "captured" and mockPaymentId in client._capturedPayments


@pytest.mark.asyncio
async def testLiveCreateTransferSuccess() -> None:
    """Verifies live HTTP POST /v1/transfers over httpx MockTransport."""
    def handleTransferRequest(request: httpx.Request) -> httpx.Response:
        assert request.method == "POST" and request.url.path == "/v1/transfers"
        payload = json.loads(request.content.decode("utf-8"))
        assert payload["account"] == mockMerchantAccount and payload["amount"] == mockTransferPaise
        assert payload["notes"]["purpose"] == "merchant_net_settlement"
        return httpx.Response(status_code=200, json=mockTransferPayload)

    mockTransport = httpx.MockTransport(handleTransferRequest)
    async with httpx.AsyncClient(transport=mockTransport) as httpClient:
        client = RazorpayRouteClient(apiKey=mockApiKey, apiSecret=mockApiSecret, isMockMode=False, httpClient=httpClient)
        transferReq = RouteTransferRequest(
            account=mockMerchantAccount, amount=mockTransferPaise, notes={"purpose": "merchant_net_settlement"},
        )
        res = await client.createTransfer(transferReq)
        assert res.id == "trf_live_12345678" and res.amount == mockTransferPaise
        assert res.account == mockMerchantAccount and "trf_live_12345678" in client._transfers


@pytest.mark.asyncio
async def testLiveReverseTransferSuccess() -> None:
    """Verifies live HTTP POST /v1/transfers/{id}/reversals compensation."""
    targetTransferId: str = "trf_live_to_reverse"

    def handleReversalRequest(request: httpx.Request) -> httpx.Response:
        assert request.method == "POST" and request.url.path == f"/v1/transfers/{targetTransferId}/reversals"
        payload = json.loads(request.content.decode("utf-8"))
        assert payload["amount"] == mockTransferPaise
        return httpx.Response(status_code=200, json=mockReversalPayload)

    mockTransport = httpx.MockTransport(handleReversalRequest)
    async with httpx.AsyncClient(transport=mockTransport) as httpClient:
        client = RazorpayRouteClient(apiKey=mockApiKey, apiSecret=mockApiSecret, isMockMode=False, httpClient=httpClient)
        res = await client.reverseTransfer(targetTransferId, mockTransferPaise)
        assert res.id == "rev_live_99887766" and res.transferId == targetTransferId
        assert res.amount == mockTransferPaise and "rev_live_99887766" in client._reversals


@pytest.mark.asyncio
async def testRouteClientContextManagerLifecycle() -> None:
    """Verifies async context manager initialization and clean shutdown."""
    def handleEcho(request: httpx.Request) -> httpx.Response:
        return httpx.Response(status_code=200, json={"status": "ok"})

    mockTransport = httpx.MockTransport(handleEcho)
    async with httpx.AsyncClient(transport=mockTransport) as httpClient:
        async with RazorpayRouteClient(
            apiKey=mockApiKey, apiSecret=mockApiSecret, isMockMode=False, httpClient=httpClient,
        ) as routeClient:
            assert routeClient.apiKey == mockApiKey
            assert routeClient.isMockMode is False
