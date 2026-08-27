"""Tests for RazorpayRouteClient error translations and adversarial edge cases (Adversarial Suite)."""

import httpx
from pydantic import ValidationError
import pytest

from razoragentMesh.packages.mandateEngine.settlement.razorpayRouteClient import (
    RazorpayRouteClient,
    RouteTransferRequest,
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
async def testMockModeSimulatedFailureAndMissingLedger() -> None:
    """Verifies simulated account failures and non-existent transfer reversal rejections."""
    client = RazorpayRouteClient(
        apiKey=mockApiKey,
        apiSecret=mockApiSecret,
        isMockMode=True,
    )
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
async def testLiveHttp400BadRequestTranslation() -> None:
    """Verifies HTTP 400 bad request error translation into MandateEngineException."""
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
async def testLiveHttp401UnauthorizedTranslation() -> None:
    """Verifies HTTP 401 unauthorized credentials error translation."""
    def handleAuthError(request: httpx.Request) -> httpx.Response:
        return httpx.Response(
            status_code=401,
            json={
                "error": {
                    "code": "BAD_REQUEST_ERROR",
                    "description": "Authentication failed: invalid key",
                }
            },
        )

    mockTransport = httpx.MockTransport(handleAuthError)
    async with httpx.AsyncClient(transport=mockTransport) as httpClient:
        client = RazorpayRouteClient(isMockMode=False, httpClient=httpClient)
        with pytest.raises(MandateEngineException) as excInfo:
            await client.capturePayment(mockPaymentId, mockAmountPaise)
        assert "Authentication failed" in str(excInfo.value)


@pytest.mark.asyncio
async def testLiveHttp500GatewayErrorTranslation() -> None:
    """Verifies HTTP 500 downstream gateway failure handling."""
    def handleGatewayError(request: httpx.Request) -> httpx.Response:
        return httpx.Response(
            status_code=500,
            json={
                "error": {
                    "code": "GATEWAY_ERROR",
                    "description": "Downstream banking network failure",
                }
            },
        )

    mockTransport = httpx.MockTransport(handleGatewayError)
    async with httpx.AsyncClient(transport=mockTransport) as httpClient:
        client = RazorpayRouteClient(isMockMode=False, httpClient=httpClient)
        transferReq = RouteTransferRequest(account=mockMerchantAccount, amount=mockTransferPaise)
        with pytest.raises(MandateEngineException) as excInfo:
            await client.createTransfer(transferReq)
        assert "Downstream banking network failure" in str(excInfo.value)


@pytest.mark.asyncio
async def testLiveNetworkTimeoutHandling() -> None:
    """Verifies network read timeout handling with descriptive error messages."""
    def handleTimeout(request: httpx.Request) -> httpx.Response:
        raise httpx.ReadTimeout("Socket timeout on route gateway", request=request)

    mockTransport = httpx.MockTransport(handleTimeout)
    async with httpx.AsyncClient(transport=mockTransport) as httpClient:
        client = RazorpayRouteClient(isMockMode=False, httpClient=httpClient)
        with pytest.raises(MandateEngineException) as excInfo:
            await client.capturePayment(mockPaymentId, mockAmountPaise)
        assert "timed out" in str(excInfo.value)


def testRouteTransferAccountValidation() -> None:
    """Verifies schema validation on RouteTransferRequest fields."""
    with pytest.raises(ValidationError):
        RouteTransferRequest(account="", amount=1000)

    with pytest.raises(ValidationError):
        RouteTransferRequest(account=mockMerchantAccount, amount=0)

    with pytest.raises(ValidationError):
        RouteTransferRequest(account=mockMerchantAccount, amount=-500)

    validReq = RouteTransferRequest(account="acc_vendor_42", amount=50000)
    assert validReq.account == "acc_vendor_42"
    assert validReq.amount == 50000
