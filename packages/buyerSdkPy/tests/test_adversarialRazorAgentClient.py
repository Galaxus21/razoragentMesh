"""Adversarial stress tests for RazorAgentClient async transport, retry loops, and error paths."""

import httpx
import pytest
from razoragent_buyer_sdk import (
    AgentKeyManager,
    CartMandate,
    Http402RequiredError,
    IntentMandate,
    MandateValidationError,
    MeshSlaConfig,
    NetworkClientError,
    RazorAgentClient,
    SettlementError,
    createExecutionMandate,
)


@pytest.mark.asyncio
async def testQuoteDiscoveryErrorHandling(agentKeyManager: AgentKeyManager) -> None:
    """Stress tests live SKU quote error responses (404, 500)."""
    def notFoundHandler(request: httpx.Request) -> httpx.Response:
        return httpx.Response(404, json={"detail": "SkuNotFound"})

    async with httpx.AsyncClient(transport=httpx.MockTransport(notFoundHandler), base_url="http://testserver") as httpCli:
        client = RazorAgentClient(keyManager=agentKeyManager, httpClient=httpCli)
        with pytest.raises(NetworkClientError) as exc404:
            await client.getLiveSkuQuote("SKU-NON-EXISTENT", "560001")
        assert exc404.value.statusCode == 404

    def serverErrorHandler(request: httpx.Request) -> httpx.Response:
        return httpx.Response(500, text="Internal Catalog Error")

    async with httpx.AsyncClient(transport=httpx.MockTransport(serverErrorHandler), base_url="http://testserver") as httpCli:
        client = RazorAgentClient(keyManager=agentKeyManager, httpClient=httpCli)
        with pytest.raises(NetworkClientError) as exc500:
            await client.getLiveSkuQuote("SKU-001", "560001")
        assert exc500.value.statusCode == 500


@pytest.mark.asyncio
async def testInventoryLockRepeated402(agentKeyManager: AgentKeyManager) -> None:
    """Verifies that client does not get trapped in an infinite loop on continuous 402s."""
    callCount = 0

    def persistent402Handler(request: httpx.Request) -> httpx.Response:
        nonlocal callCount
        callCount += 1
        return httpx.Response(
            402,
            json={"statusCode": 402, "challengeToken": f"ch_{callCount}", "powDifficultyZeros": 2},
        )

    async with httpx.AsyncClient(transport=httpx.MockTransport(persistent402Handler), base_url="http://testserver") as httpCli:
        client = RazorAgentClient(keyManager=agentKeyManager, httpClient=httpCli)
        with pytest.raises(Http402RequiredError) as excInfo:
            await client.reserveInventoryLock("SKU-001", "qh_test", quantity=1)
        assert callCount == 2
        assert excInfo.value.challengeToken == "ch_2"


@pytest.mark.asyncio
async def testSettlementClientSideValidationGuard(
    agentKeyManager: AgentKeyManager,
    sampleIntentMandate: IntentMandate,
    sampleCartMandate: CartMandate,
) -> None:
    """Verifies that executeSettlement performs client-side pre-validation and prevents network dispatch."""
    networkCalled = False

    def trapHandler(request: httpx.Request) -> httpx.Response:
        nonlocal networkCalled
        networkCalled = True
        return httpx.Response(200, json={})

    # Create invalid execution mandate with mismatched settlement amount
    invalidExecution = createExecutionMandate(
        executionId="M-E-BAD",
        buyerKeyManager=agentKeyManager,
        intentMandate=sampleIntentMandate,
        cartMandate=sampleCartMandate,
        settlementAmountPaise=sampleCartMandate.totalPaise,
        upiCircleToken="tok",
    )
    mismatchedCart = sampleCartMandate.model_copy(update={"totalPaise": sampleCartMandate.totalPaise + 500})

    async with httpx.AsyncClient(transport=httpx.MockTransport(trapHandler), base_url="http://testserver") as httpCli:
        client = RazorAgentClient(keyManager=agentKeyManager, httpClient=httpCli)
        with pytest.raises(MandateValidationError):
            await client.executeSettlement(
                intentMandate=sampleIntentMandate,
                cartMandate=mismatchedCart,
                executionMandate=invalidExecution,
                merchantAccount="acc_01",
                paymentId="pay_01",
            )
        assert networkCalled is False


async def _assertSettlementError(
    handler: Any, keyManager: AgentKeyManager, intent: IntentMandate,
    cart: CartMandate, execM: ExecutionMandate,
) -> SettlementError:
    async with httpx.AsyncClient(transport=httpx.MockTransport(handler), base_url="http://testserver") as httpCli:
        client = RazorAgentClient(keyManager=keyManager, httpClient=httpCli)
        with pytest.raises(SettlementError) as excInfo:
            await client.executeSettlement(
                intentMandate=intent, cartMandate=cart,
                executionMandate=execM, merchantAccount="acc_01",
                paymentId="pay_01", serverTime=1700000000,
            )
        return excInfo.value


@pytest.mark.asyncio
async def testSettlementServerRejectionHandling(
    agentKeyManager: AgentKeyManager,
    sampleIntentMandate: IntentMandate,
    sampleCartMandate: CartMandate,
) -> None:
    """Stress tests SettlementError wrapping and status code / details preservation."""
    validExecution = createExecutionMandate(
        executionId="M-E-001", buyerKeyManager=agentKeyManager,
        intentMandate=sampleIntentMandate, cartMandate=sampleCartMandate,
        settlementAmountPaise=sampleCartMandate.totalPaise,
        upiCircleToken=sampleIntentMandate.upiCircleDelegationToken, timestamp=1700000000,
    )

    json400 = lambda req: httpx.Response(400, headers={"content-type": "application/json"}, json={"error": "BudgetExceeded", "code": 4001})
    err400 = await _assertSettlementError(json400, agentKeyManager, sampleIntentMandate, sampleCartMandate, validExecution)
    assert err400.statusCode == 400
    assert err400.details.get("error") == "BudgetExceeded"

    text503 = lambda req: httpx.Response(503, headers={"content-type": "text/plain"}, text="Bank Gateway Timeout")
    err503 = await _assertSettlementError(text503, agentKeyManager, sampleIntentMandate, sampleCartMandate, validExecution)
    assert err503.statusCode == 503
    assert "Bank Gateway Timeout" in err503.details.get("body", "")



@pytest.mark.asyncio
async def testEscrowAndChallengeEndpoints(agentKeyManager: AgentKeyManager) -> None:
    """Stress tests getPowChallenge, createEscrowSession, and releaseEscrow."""
    def endpointHandler(request: httpx.Request) -> httpx.Response:
        if request.url.path == "/api/v1/mesh/challenge":
            return httpx.Response(200, json={"statusCode": 402, "wwwAuthenticate": "x402-INR", "challengeToken": "c_tok_99", "tokenCostPaise": 50, "powDifficultyZeros": 4})
        if request.url.path == "/api/v1/mesh/escrow":
            return httpx.Response(200, json={"sessionToken": "esc_tok_99", "buyerAgentDid": agentKeyManager.getAgentDid(), "balancePaise": 5000, "expiresAtUnix": 1700000300})
        if request.url.path == "/api/v1/mesh/escrow/release":
            return httpx.Response(200, json={"sessionToken": "esc_tok_99", "refundAmountPaise": 4500, "status": "refunded"})
        return httpx.Response(404)

    async with httpx.AsyncClient(transport=httpx.MockTransport(endpointHandler), base_url="http://testserver") as httpCli:
        client = RazorAgentClient(keyManager=agentKeyManager, httpClient=httpCli)
        
        challenge = await client.getPowChallenge()
        assert challenge.challengeToken == "c_tok_99"
        assert challenge.powDifficultyZeros == 4

        escrow = await client.createEscrowSession(initialHoldPaise=5000)
        assert escrow.sessionToken == "esc_tok_99"
        assert escrow.balancePaise == 5000

        refund = await client.releaseEscrow("esc_tok_99")
        assert refund.refundAmountPaise == 4500
        assert refund.status == "refunded"
