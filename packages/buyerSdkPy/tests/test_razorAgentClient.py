"""Unit tests for RazorAgentClient async HTTP client using mock transport."""

import httpx
import pytest
from razoragent_buyer_sdk import (
    AgentKeyManager,
    CartMandate,
    Http402RequiredError,
    IntentMandate,
    RazorAgentClient,
    SettlementError,
    createExecutionMandate,
)


@pytest.mark.asyncio
async def testClientDiscoveryQuote(agentKeyManager: AgentKeyManager) -> None:
    """Verifies live SKU quote fetching and parsing."""
    sampleQuoteData = {
        "skuId": "SKU-001", "availableStock": 25, "baseUnitPricePaise": 420000,
        "offeredUnitPricePaise": 420000, "finalUnitPricePaise": 420000, "quantity": 1,
        "currency": "INR", "hsnCode": "8504", "gstRatePercent": 18,
        "taxableSubtotalPaise": 420000,
        "taxBreakdown": {"cgstPaise": 37800, "sgstPaise": 37800, "igstPaise": 0, "totalTaxPaise": 75600},
        "quoteExpiryTimestamp": 1700000060, "quoteHash": "a5f82c64hexhash",
        "appliedDiscounts": [], "totalSavingsPaise": 0, "upcomingPromotions": [],
    }

    def handler(request: httpx.Request) -> httpx.Response:
        # Route, verb and query parameters all as the MCP HTTP adapter declares them. The old
        # version asserted "/api/v1/quotes/live", a route nothing serves, which is how the client
        # stayed broken through 1,200 passing tests.
        assert request.url.path == "/api/v1/quote"
        assert request.method == "GET"
        assert request.url.params["skuId"] == "SKU-001"
        assert request.url.params["deliveryPincode"] == "560001"
        return httpx.Response(200, json=sampleQuoteData)

    transport = httpx.MockTransport(handler)
    async with httpx.AsyncClient(transport=transport, base_url="http://testserver") as httpClient:
        client = RazorAgentClient(keyManager=agentKeyManager, httpClient=httpClient)
        quote = await client.getLiveSkuQuote("SKU-001", "560001", quantity=1)
        assert quote.sku_id == "SKU-001"
        assert quote.offered_unit_price_paise == 420000


@pytest.mark.asyncio
async def testClientInventoryLockHappyPath(agentKeyManager: AgentKeyManager) -> None:
    """Verifies 200 OK inventory lock reservation."""
    sampleLockData = {
        "lockToken": "9b1deb4d-3b7d-4bad-9bdd-2b0d7b3dcb6d", "fencingToken": 142,
        "skuId": "SKU-001", "quantityLocked": 1, "expiresAtUnixMs": 1700000060000,
        "lockSignature": "base64_signature_here",
    }

    def handler(request: httpx.Request) -> httpx.Response:
        assert request.url.path == "/api/v1/lock"
        return httpx.Response(200, json=sampleLockData)

    transport = httpx.MockTransport(handler)
    async with httpx.AsyncClient(transport=transport, base_url="http://testserver") as httpClient:
        client = RazorAgentClient(keyManager=agentKeyManager, httpClient=httpClient)
        lock = await client.reserveInventoryLock("SKU-001", "qh_test", quantity=1)
        assert lock.lock_token == "9b1deb4d-3b7d-4bad-9bdd-2b0d7b3dcb6d"
        assert lock.fencing_token == 142


@pytest.mark.asyncio
async def testClientInventoryLock402AutoResolution(agentKeyManager: AgentKeyManager) -> None:
    """Verifies automatic HTTP 402 challenge detection, PoW solving, and retry."""
    callCount = 0

    def handler(request: httpx.Request) -> httpx.Response:
        nonlocal callCount
        callCount += 1
        assert request.url.path == "/api/v1/lock"
        if callCount == 1:
            return httpx.Response(
                402,
                json={"statusCode": 402, "challengeToken": "test_auto_pow_challenge", "powDifficultyZeros": 2},
            )
        assert "X-Mesh-Pow-Challenge" in request.headers
        assert "X-Mesh-Pow-Solution" in request.headers
        return httpx.Response(
            200,
            json={
                "lockToken": "lock_after_pow_solved", "fencingToken": 143, "skuId": "SKU-001",
                "quantityLocked": 1, "expiresAtUnixMs": 1700000060000, "lockSignature": "valid_sig",
            },
        )

    transport = httpx.MockTransport(handler)
    async with httpx.AsyncClient(transport=transport, base_url="http://testserver") as httpClient:
        client = RazorAgentClient(keyManager=agentKeyManager, httpClient=httpClient)
        lock = await client.reserveInventoryLock("SKU-001", "qh_test", quantity=1)
        assert lock.lock_token == "lock_after_pow_solved"
        assert callCount == 2


@pytest.mark.asyncio
async def testClientInventoryLock402WithoutAutoSolve(agentKeyManager: AgentKeyManager) -> None:
    """Verifies raising Http402RequiredError when autoSolvePow is disabled."""
    def handler(request: httpx.Request) -> httpx.Response:
        return httpx.Response(402, json={"challengeToken": "challenge_token_123", "powDifficultyZeros": 4})

    transport = httpx.MockTransport(handler)
    async with httpx.AsyncClient(transport=transport, base_url="http://testserver") as httpClient:
        client = RazorAgentClient(keyManager=agentKeyManager, httpClient=httpClient)
        with pytest.raises(Http402RequiredError) as excInfo:
            await client.reserveInventoryLock("SKU-001", "qh_test", autoSolvePow=False)
        assert excInfo.value.challengeToken == "challenge_token_123"
        assert excInfo.value.difficulty == 4


@pytest.mark.asyncio
async def testClientExecuteSettlementSuccess(
    agentKeyManager: AgentKeyManager,
    sampleIntentMandate: IntentMandate,
    sampleCartMandate: CartMandate,
) -> None:
    """Verifies successful 2PC settlement saga execution."""
    executionMandate = createExecutionMandate(
        executionId="M-E-TEST-001", buyerKeyManager=agentKeyManager, intentMandate=sampleIntentMandate,
        cartMandate=sampleCartMandate, settlementAmountPaise=sampleCartMandate.totalPaise,
        upiCircleToken=sampleIntentMandate.upiCircleDelegationToken, nonce="nonce_test_001", timestamp=1700000000,
    )

    sampleSettlementResult = {
        "status": "captured", "paymentId": "pay_live_001", "amountPaise": sampleCartMandate.totalPaise,
        "transfers": [{"id": "trf_01", "entity": "transfer", "account": "acc_01", "amount": sampleCartMandate.totalPaise, "currency": "INR", "status": "processed", "createdAt": 1700000000}],
        "invoice": {
            "invoiceNumber": "INV-001", "invoiceDate": "2023-11-14T22:13:20Z", "sellerGstin": "29AABCU9603R1ZJ",
            "merchantStateCode": "29", "placeOfSupplyStateCode": "29", "isIntraState": True,
            "lineItems": [{"skuId": "SKU-001", "hsnCode": "8504", "quantity": 1, "unitPricePaise": 420000, "taxableAmountPaise": 420000, "gstRatePercent": 18, "cgstPaise": 37800, "sgstPaise": 37800, "igstPaise": 0, "totalLinePaise": 495600}],
            "taxableAmountPaise": 420000, "totalCgstPaise": 37800, "totalSgstPaise": 37800, "totalIgstPaise": 0,
            "totalTaxPaise": 75600, "totalTcsPaise": 4200, "shippingPaise": 0, "discountPaise": 0,
            "grandTotalPaise": 495600, "cryptographicAuditHash": "f" * 64,
        },
        "settledAt": 1700000000,
    }

    def handler(request: httpx.Request) -> httpx.Response:
        assert request.url.path == "/api/v1/settlement/execute"
        return httpx.Response(200, json=sampleSettlementResult)

    transport = httpx.MockTransport(handler)
    async with httpx.AsyncClient(transport=transport, base_url="http://testserver") as httpClient:
        client = RazorAgentClient(keyManager=agentKeyManager, httpClient=httpClient)
        result = await client.executeSettlement(
            intentMandate=sampleIntentMandate, cartMandate=sampleCartMandate,
            executionMandate=executionMandate, merchantAccount="acc_01",
            paymentId="pay_live_001", serverTime=1700000000,
        )
        assert result.status == "captured"
        assert result.amountPaise == sampleCartMandate.totalPaise


@pytest.mark.asyncio
async def testClientExecuteSettlementErrorHandling(
    agentKeyManager: AgentKeyManager,
    sampleIntentMandate: IntentMandate,
    sampleCartMandate: CartMandate,
) -> None:
    """Verifies error handling and SettlementError wrapping on server rejections."""
    executionMandate = createExecutionMandate(
        executionId="M-E-TEST-001", buyerKeyManager=agentKeyManager, intentMandate=sampleIntentMandate,
        cartMandate=sampleCartMandate, settlementAmountPaise=sampleCartMandate.totalPaise,
        upiCircleToken="tok", timestamp=1700000000,
    )

    def handler(request: httpx.Request) -> httpx.Response:
        return httpx.Response(400, json={"detail": "BudgetExceededViolation"})

    transport = httpx.MockTransport(handler)
    async with httpx.AsyncClient(transport=transport, base_url="http://testserver") as httpClient:
        client = RazorAgentClient(keyManager=agentKeyManager, httpClient=httpClient)
        with pytest.raises(SettlementError) as excInfo:
            await client.executeSettlement(
                intentMandate=sampleIntentMandate, cartMandate=sampleCartMandate,
                executionMandate=executionMandate, merchantAccount="acc_01",
                paymentId="pay_live_001", serverTime=1700000000,
            )
        assert excInfo.value.statusCode == 400


@pytest.mark.asyncio
async def testClientPriceDropAlertsLifecycle(agentKeyManager: AgentKeyManager) -> None:
    """Verifies registering and cancelling price drop alerts."""
    def handler(request: httpx.Request) -> httpx.Response:
        if request.method == "POST":
            return httpx.Response(200, json={"alertId": "alert_999", "skuId": "SKU-001", "targetPricePaise": 350000, "status": "active", "expiresAtUnix": 2000000000})
        if request.method == "DELETE":
            return httpx.Response(200, json={"alertId": "alert_999", "status": "cancelled"})
        return httpx.Response(404)

    transport = httpx.MockTransport(handler)
    async with httpx.AsyncClient(transport=transport, base_url="http://testserver") as httpClient:
        client = RazorAgentClient(keyManager=agentKeyManager, httpClient=httpClient)
        reg = await client.registerPriceDropAlert("SKU-001", 350000, "http://callback", 2000000000)
        assert reg.alertId == "alert_999"
        cancel = await client.cancelPriceDropAlert("alert_999")
        assert cancel.status == "cancelled"


@pytest.mark.asyncio
async def testAsyncContextManagerLifecycle() -> None:
    """Verifies async context manager instantiation and teardown."""
    async with RazorAgentClient() as client:
        assert client.getAgentDid().startswith("did:agent:")
