"""Tests for RazorpayRouteClient live HTTP transport and mock mode ledgers."""

import json
import httpx
import pytest

from razoragentMesh.packages.mandateEngine.settlement.razorpayRouteClient import (
    PaymentCaptureResponse,
    RazorpayRouteClient,
    RouteTransferRequest,
    RouteTransferResponse,
    TransferReversalResponse,
)
from razoragentMesh.packages.mandateEngine.settlement.settlementExceptions import (
    MandateEngineException,
)

mockApiKey: str = "rzp_test_mock_123"
mockApiSecret: str = "secret_xyz"
mockMerchantAccount: str = "acc_merchant_prime_01"
mockPaymentId: str = "pay_test_capture_001"
mockAmountPaise: int = 118000
mockTransferPaise: int = 100000


@pytest.mark.asyncio
async def testMockModePaymentCaptureAndTransfers() -> None:
    """Verifies default in-memory ledger operations for capture, transfer, and reversal."""
    client = RazorpayRouteClient(
        apiKey=mockApiKey,
        apiSecret=mockApiSecret,
        isMockMode=True,
    )
    assert client.isMockMode is True

    # 1. Payment Capture
    captureRes = await client.capturePayment(mockPaymentId, mockAmountPaise)
    assert isinstance(captureRes, PaymentCaptureResponse)
    assert captureRes.id == mockPaymentId
    assert captureRes.amount == mockAmountPaise
    assert captureRes.status == "captured"
    assert captureRes.captured is True
    assert mockPaymentId in client._capturedPayments

    # 2. Transfer
    transferReq = RouteTransferRequest(
        account=mockMerchantAccount,
        amount=mockTransferPaise,
        notes={"purpose": "merchant_net_settlement"},
    )
    transferRes = await client.createTransfer(transferReq)
    assert isinstance(transferRes, RouteTransferResponse)
    assert transferRes.account == mockMerchantAccount
    assert transferRes.amount == mockTransferPaise
    assert transferRes.status == "processed"
    assert transferRes.id in client._transfers

    # 3. Reversal
    reversalRes = await client.reverseTransfer(transferRes.id, mockTransferPaise)
    assert isinstance(reversalRes, TransferReversalResponse)
    assert reversalRes.transferId == transferRes.id
    assert reversalRes.amount == mockTransferPaise
    assert reversalRes.status == "processed"
    assert reversalRes.id in client._reversals


@pytest.mark.asyncio
async def testMockModeSimulatedFailureAndMissingLedger() -> None:
    """Verifies simulated account failures and non-existent transfer reversal rejections."""
    client = RazorpayRouteClient(isMockMode=True)
    client.simulatedFailureAccount = mockMerchantAccount

    transferReq = RouteTransferRequest(
        account=mockMerchantAccount,
        amount=mockTransferPaise,
    )
    with pytest.raises(MandateEngineException) as excInfo:
        await client.createTransfer(transferReq)
    assert "Simulated Route transfer failure" in str(excInfo.value)

    with pytest.raises(MandateEngineException) as excMissing:
        await client.reverseTransfer("trf_non_existent_id", 1000)
    assert "not found in ledger" in str(excMissing.value)


@pytest.mark.asyncio
async def testLivePaymentCaptureSuccess() -> None:
    """Verifies live HTTP POST /v1/payments/{id}/capture over httpx MockTransport."""
    authHeaderPresent = [False]

    def handleCaptureRequest(request: httpx.Request) -> httpx.Response:
        if request.headers.get("authorization", "").startswith("Basic "):
            authHeaderPresent[0] = True
        assert request.method == "POST" and request.url.path == f"/v1/payments/{mockPaymentId}/capture"
        payload = json.loads(request.content.decode("utf-8"))
        assert payload["amount"] == mockAmountPaise and payload["currency"] == "INR"
        return httpx.Response(200, json={
            "id": mockPaymentId, "entity": "payment", "amount": mockAmountPaise,
            "currency": "INR", "status": "captured", "method": "upi", "captured": True, "created_at": 1700000000,
        })

    mockTransport = httpx.MockTransport(handleCaptureRequest)
    async with httpx.AsyncClient(transport=mockTransport) as httpClient:
        client = RazorpayRouteClient(apiKey=mockApiKey, apiSecret=mockApiSecret, baseUrl="https://api.razorpay.com/v1", isMockMode=False, httpClient=httpClient)
        res = await client.capturePayment(mockPaymentId, mockAmountPaise)
        assert authHeaderPresent[0] is True and res.id == mockPaymentId and res.amount == mockAmountPaise
        assert res.status == "captured" and mockPaymentId in client._capturedPayments


@pytest.mark.asyncio
async def testLiveCreateTransferSuccess() -> None:
    """Verifies live HTTP POST /v1/transfers over httpx MockTransport."""
    def handleTransferRequest(request: httpx.Request) -> httpx.Response:
        assert request.method == "POST" and request.url.path == "/v1/transfers"
        payload = json.loads(request.content.decode("utf-8"))
        assert payload["account"] == mockMerchantAccount and payload["amount"] == mockTransferPaise
        assert payload["notes"]["purpose"] == "merchant_net_settlement"
        return httpx.Response(200, json={
            "id": "trf_live_12345678", "entity": "transfer", "account": mockMerchantAccount,
            "amount": mockTransferPaise, "currency": "INR", "status": "processed", "created_at": 1700000000,
        })

    mockTransport = httpx.MockTransport(handleTransferRequest)
    async with httpx.AsyncClient(transport=mockTransport) as httpClient:
        client = RazorpayRouteClient(apiKey=mockApiKey, apiSecret=mockApiSecret, isMockMode=False, httpClient=httpClient)
        transferReq = RouteTransferRequest(account=mockMerchantAccount, amount=mockTransferPaise, notes={"purpose": "merchant_net_settlement"})
        res = await client.createTransfer(transferReq)
        assert res.id == "trf_live_12345678" and res.amount == mockTransferPaise
        assert res.account == mockMerchantAccount and "trf_live_12345678" in client._transfers



@pytest.mark.asyncio
async def testLiveReverseTransferSuccess() -> None:
    """Verifies live HTTP POST /v1/transfers/{id}/reversals compensation."""
    targetTransferId: str = "trf_live_to_reverse"

    def handleReversalRequest(request: httpx.Request) -> httpx.Response:
        assert request.method == "POST"
        assert request.url.path == f"/v1/transfers/{targetTransferId}/reversals"
        payload = json.loads(request.content.decode("utf-8"))
        assert payload["amount"] == mockTransferPaise

        return httpx.Response(
            status_code=200,
            json={
                "id": "rev_live_99887766",
                "entity": "reversal",
                "transfer_id": targetTransferId,
                "amount": mockTransferPaise,
                "currency": "INR",
                "status": "processed",
                "created_at": 1700000000,
            },
        )

    mockTransport = httpx.MockTransport(handleReversalRequest)
    async with httpx.AsyncClient(transport=mockTransport) as httpClient:
        client = RazorpayRouteClient(
            apiKey=mockApiKey,
            apiSecret=mockApiSecret,
            isMockMode=False,
            httpClient=httpClient,
        )
        res = await client.reverseTransfer(targetTransferId, mockTransferPaise)
        assert res.id == "rev_live_99887766"
        assert res.transferId == targetTransferId
        assert res.amount == mockTransferPaise
        assert "rev_live_99887766" in client._reversals


@pytest.mark.asyncio
async def testLiveHttpErrorTranslations() -> None:
    """Verifies HTTP 400, 401, 500 error translation into MandateEngineException."""
    def handleApiError(request: httpx.Request) -> httpx.Response:
        return httpx.Response(
            status_code=400,
            json={
                "error": {
                    "code": "BAD_REQUEST_ERROR",
                    "description": "Linked vendor account is suspended",
                }
            },
        )

    mockTransport = httpx.MockTransport(handleApiError)
    async with httpx.AsyncClient(transport=mockTransport) as httpClient:
        client = RazorpayRouteClient(isMockMode=False, httpClient=httpClient)
        transferReq = RouteTransferRequest(account=mockMerchantAccount, amount=mockTransferPaise)
        with pytest.raises(MandateEngineException) as excInfo:
            await client.createTransfer(transferReq)
        assert "Linked vendor account is suspended" in str(excInfo.value)


@pytest.mark.asyncio
async def testLiveNetworkTimeoutAndContextLifecycle() -> None:
    """Verifies network timeouts and async context manager lifecycle."""
    def handleTimeout(request: httpx.Request) -> httpx.Response:
        raise httpx.ReadTimeout("Socket timeout on route gateway", request=request)

    mockTransport = httpx.MockTransport(handleTimeout)
    async with httpx.AsyncClient(transport=mockTransport) as httpClient:
        async with RazorpayRouteClient(isMockMode=False, httpClient=httpClient) as client:
            with pytest.raises(MandateEngineException) as excInfo:
                await client.capturePayment(mockPaymentId, mockAmountPaise)
            assert "timed out" in str(excInfo.value)