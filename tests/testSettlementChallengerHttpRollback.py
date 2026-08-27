"""Challenger: Live HTTP Client Error Translations and 2PC LIFO Rollback.

Tests:
1. RazorpayRouteClient error translations (400, 401, 404, 500, 502, malformed JSON, network failures)
2. RazorpayRouteClient Basic Auth header formatting
3. TwoPhaseCommitSaga live HTTP LIFO rollback ordering
"""

import base64
import json
import fakeredis.aioredis
import httpx
import pytest

from razoragentMesh.packages.mandateEngine.crypto.cryptoKeyUtils import generateKeyPair
from razoragentMesh.packages.mandateEngine.crypto.ed25519Signer import Ed25519Signer
from razoragentMesh.packages.mandateEngine.mandates.cartMandateSchema import (
    CartItemSchema,
    TaxBreakdownSchema,
)
from razoragentMesh.packages.mandateEngine.mandates.mandateFactory import (
    createSignedCartMandate,
    createSignedExecutionMandate,
    createSignedIntentMandate,
)
from razoragentMesh.packages.mandateEngine.nonce.nonceLedger import NonceLedger
from razoragentMesh.packages.mandateEngine.settlement.razorpayRouteClient import (
    RazorpayRouteClient,
    RouteTransferRequest,
)
from razoragentMesh.packages.mandateEngine.settlement.settlementExceptions import (
    MandateEngineException,
    SettlementCompensationTriggeredException,
)
from razoragentMesh.packages.mandateEngine.settlement.settlementOrchestrator import (
    SettlementOrchestrator,
)

testApiKey: str = "rzp_live_key_999"
testApiSecret: str = "sec_test_secret_abc123"
testMerchantAcc: str = "acc_merchant_prime"
testProtocolAcc: str = "acc_protocol_fees"
testLogisticsAcc: str = "acc_logistics_speed"
testServerTime: int = 1700000000


def _buildMandateChain(
    amountPaise: int = 120000,
    shippingPaise: int = 2000,
    maxBudgetPaise: int = 200000,
    nonce: str = "nonce_challenger_001",
) -> tuple:
    uSigner = Ed25519Signer(generateKeyPair()[0])
    mSigner = Ed25519Signer(generateKeyPair()[0])
    aSigner = Ed25519Signer(generateKeyPair()[0])
    taxable = 100000
    total = (taxable + 18000 + shippingPaise) if amountPaise == 120000 else amountPaise

    intentM = createSignedIntentMandate(
        mandateId=f"M-I-{nonce}", userSigner=uSigner, delegatedAgentDid=aSigner.getAgentDid(),
        maxBudgetPaise=maxBudgetPaise, upiCircleDelegationToken="upi_token_cfo",
        singleTransactionLimitPaise=200000, validUntilTimestamp=2000000000, timestamp=testServerTime,
    )
    item = CartItemSchema(
        skuId="SKU-CHALLENGER-1", quantity=1, unitPricePaise=taxable,
        hsnCode="84713010", gstRatePercent=18, lineTotalPaise=taxable,
    )
    cartM = createSignedCartMandate(
        cartId=f"M-C-{nonce}", merchantSigner=mSigner,
        merchantGstin="29AAAAA0000A1ZY", merchantStateCode="29",
        buyerDeliveryPincode="560001", buyerDeliveryStateCode="29",
        items=[item], taxableSubtotalPaise=taxable,
        taxBreakdown=TaxBreakdownSchema(cgstPaise=9000, sgstPaise=9000, igstPaise=0, totalTaxPaise=18000),
        shippingPaise=shippingPaise, discountPaise=0, totalPaise=total,
        inventoryLockToken="lock_tok_chal", inventoryLockExpiresAt=2000000000, timestamp=testServerTime,
    )
    execM = createSignedExecutionMandate(
        executionId=f"M-E-{nonce}", buyerAgentSigner=aSigner,
        intentMandate=intentM, cartMandate=cartM, settlementAmountPaise=total,
        upiCircleToken="upi_token_cfo", timestamp=testServerTime, nonce=nonce,
    )
    return intentM, cartM, execM


@pytest.mark.asyncio
async def testLiveHttpBasicAuthHeaderEncoding() -> None:
    """Empirically verifies live HTTP client sends correct Base64 Basic Auth headers."""
    capturedAuthHeader: list[str] = []

    def handleAuthCheck(request: httpx.Request) -> httpx.Response:
        capturedAuthHeader.append(request.headers.get("authorization", ""))
        return httpx.Response(
            status_code=200,
            json={"id": "pay_auth_test", "entity": "payment", "amount": 1000, "currency": "INR", "status": "captured", "created_at": testServerTime},
        )

    mockTransport = httpx.MockTransport(handleAuthCheck)
    async with httpx.AsyncClient(transport=mockTransport) as httpClient:
        client = RazorpayRouteClient(apiKey=testApiKey, apiSecret=testApiSecret, isMockMode=False, httpClient=httpClient)
        await client.capturePayment("pay_auth_test", 1000)

    assert len(capturedAuthHeader) == 1
    authHeader = capturedAuthHeader[0]
    assert authHeader.startswith("Basic ")
    decodedCreds = base64.b64decode(authHeader.split(" ")[1]).decode("utf-8")
    assert decodedCreds == f"{testApiKey}:{testApiSecret}"


@pytest.mark.asyncio
@pytest.mark.parametrize(
    "statusCode,errorBody,expectedMessageSnippet",
    [
        (400, {"error": {"code": "BAD_REQUEST_ERROR", "description": "Invalid bank IFSC"}}, "Invalid bank IFSC"),
        (401, {"error": {"code": "UNAUTHORIZED_ERROR", "description": "Invalid API Key or Secret"}}, "Invalid API Key or Secret"),
        (404, {"error": {"code": "ENTITY_NOT_FOUND", "description": "Transfer entity not found"}}, "Transfer entity not found"),
        (500, {"error": {"code": "GATEWAY_ERROR", "description": "Internal Razorpay Gateway Failure"}}, "Internal Razorpay Gateway Failure"),
        (502, {"error": "Bad Gateway Upstream"}, "Bad Gateway Upstream"),
    ],
)
async def testLiveHttpErrorTranslationVariations(statusCode: int, errorBody: dict, expectedMessageSnippet: str) -> None:
    """Empirically verifies various HTTP status codes translate to MandateEngineException."""
    def handleHttpError(request: httpx.Request) -> httpx.Response:
        return httpx.Response(status_code=statusCode, json=errorBody)

    mockTransport = httpx.MockTransport(handleHttpError)
    async with httpx.AsyncClient(transport=mockTransport) as httpClient:
        client = RazorpayRouteClient(isMockMode=False, httpClient=httpClient)
        req = RouteTransferRequest(account=testMerchantAcc, amount=5000)
        with pytest.raises(MandateEngineException) as excInfo:
            await client.createTransfer(req)
        assert f"({statusCode})" in str(excInfo.value)
        assert expectedMessageSnippet in str(excInfo.value)


@pytest.mark.asyncio
async def testLiveHttpMalformedJsonAndHtmlErrorPages() -> None:
    """Empirically verifies HTML or malformed non-JSON responses do not crash the engine."""
    def handleHtmlError(request: httpx.Request) -> httpx.Response:
        return httpx.Response(
            status_code=502,
            text="<html><head><title>502 Bad Gateway</title></head><body>Server Unreachable</body></html>",
            headers={"content-type": "text/html"},
        )

    mockTransport = httpx.MockTransport(handleHtmlError)
    async with httpx.AsyncClient(transport=mockTransport) as httpClient:
        client = RazorpayRouteClient(isMockMode=False, httpClient=httpClient)
        with pytest.raises(MandateEngineException) as excInfo:
            await client.capturePayment("pay_html_error", 5000)
        assert "(502)" in str(excInfo.value)
        assert "502 Bad Gateway" in str(excInfo.value) or "Server Unreachable" in str(excInfo.value)


@pytest.mark.asyncio
async def testLiveHttpMalformedJsonOn200Ok() -> None:
    """Empirically verifies malformed JSON on HTTP 200 OK raises MandateEngineException."""
    def handleCorrupt200(request: httpx.Request) -> httpx.Response:
        return httpx.Response(status_code=200, text="corrupted_json{id:123", headers={"content-type": "application/json"})

    mockTransport = httpx.MockTransport(handleCorrupt200)
    async with httpx.AsyncClient(transport=mockTransport) as httpClient:
        client = RazorpayRouteClient(isMockMode=False, httpClient=httpClient)
        with pytest.raises(MandateEngineException) as excInfo:
            await client.capturePayment("pay_corrupt_200", 5000)
        assert "Invalid JSON response" in str(excInfo.value)


@pytest.mark.asyncio
async def testLiveHttpConnectionErrorsAndNetworkFailures() -> None:
    """Empirically verifies network connection resets and host unreachable errors map to MandateEngineException."""
    def handleConnectError(request: httpx.Request) -> httpx.Response:
        raise httpx.ConnectError("Connection refused to api.razorpay.com", request=request)

    mockTransport = httpx.MockTransport(handleConnectError)
    async with httpx.AsyncClient(transport=mockTransport) as httpClient:
        client = RazorpayRouteClient(isMockMode=False, httpClient=httpClient)
        with pytest.raises(MandateEngineException) as excInfo:
            await client.capturePayment("pay_conn_err", 5000)
        assert "Razorpay API connection error" in str(excInfo.value)


def _createLiveSagaHandler(transferCallOrder: list[str], reversalCallOrder: list[str]):
    def handleLiveSaga(request: httpx.Request) -> httpx.Response:
        path = request.url.path
        if path == "/v1/payments/pay_live_saga_01/capture":
            return httpx.Response(status_code=200, json={"id": "pay_live_saga_01", "status": "captured", "amount": 120000})
        if path == "/v1/transfers":
            body = json.loads(request.content.decode("utf-8"))
            acc = body["account"]
            transferCallOrder.append(acc)
            if acc == testMerchantAcc:
                return httpx.Response(status_code=200, json={"id": "trf_merchant_01", "account": acc, "amount": body["amount"]})
            if acc == testProtocolAcc:
                return httpx.Response(status_code=200, json={"id": "trf_protocol_02", "account": acc, "amount": body["amount"]})
            if acc == testLogisticsAcc:
                return httpx.Response(status_code=500, json={"error": {"code": "LOGISTICS_FAIL", "description": "Logistics node down"}})
        if "/reversals" in path:
            transferId = path.split("/")[3]
            reversalCallOrder.append(transferId)
            return httpx.Response(status_code=200, json={"id": f"rev_{transferId}", "transfer_id": transferId, "status": "processed"})
        return httpx.Response(status_code=404, json={"error": "Not Found"})
    return handleLiveSaga


@pytest.mark.asyncio
async def testTwoPhaseCommitSagaLiveHttpLifoRollback() -> None:
    """Empirically verifies 2PC Saga executes strict LIFO reversal over live HTTP transport."""
    transferCallOrder: list[str] = []
    reversalCallOrder: list[str] = []
    handler = _createLiveSagaHandler(transferCallOrder, reversalCallOrder)
    mockTransport = httpx.MockTransport(handler)

    async with httpx.AsyncClient(transport=mockTransport) as httpClient:
        liveClient = RazorpayRouteClient(isMockMode=False, httpClient=httpClient)
        orchestrator = SettlementOrchestrator(
            routeClient=liveClient, nonceLedger=NonceLedger(fakeredis.aioredis.FakeRedis()),
            protocolFeeAccount=testProtocolAcc, protocolFeePaise=50, logisticsAccount=testLogisticsAcc,
        )
        intentM, cartM, execM = _buildMandateChain(amountPaise=120000, shippingPaise=2000, nonce="nonce_live_lifo_01")
        with pytest.raises(SettlementCompensationTriggeredException) as excInfo:
            await orchestrator.executeSettlementSaga(
                intentMandate=intentM, cartMandate=cartM, executionMandate=execM,
                merchantAccount=testMerchantAcc, paymentId="pay_live_saga_01", serverTime=testServerTime,
            )
        assert "triggered rollback" in str(excInfo.value)
        assert transferCallOrder == [testMerchantAcc, testProtocolAcc, testLogisticsAcc]
        assert reversalCallOrder == ["trf_protocol_02", "trf_merchant_01"]
