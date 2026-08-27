"""Challenger 2: Live Route Client, 2PC LIFO Saga Reversals, and End-to-End Settlement App.

Tests:
1. Live HTTP Transport Basic Auth & Headers
2. Two-Phase Commit Saga LIFO Reversals
3. Mandate App End-to-End Execution via FastAPI
"""

import time
import fakeredis.aioredis
import httpx
from httpx import ASGITransport
import pytest

from razoragentMesh.packages.mandateEngine import (
    CartItemSchema,
    ExecuteSettlementRequestSchema,
    NonceLedger,
    RazorpayRouteClient,
    SettlementCompensationTriggeredException,
    SettlementOrchestrator,
    SplitTransferManifest,
    TaxBreakdownSchema,
    TwoPhaseCommitSaga,
    createMandateApp,
    createSignedCartMandate,
    createSignedExecutionMandate,
    createSignedIntentMandate,
)
from razoragentMesh.packages.mandateEngine.crypto.cryptoKeyUtils import generateKeyPair
from razoragentMesh.packages.mandateEngine.crypto.ed25519Signer import Ed25519Signer


@pytest.mark.asyncio
async def testRazorpayRouteClientLiveBasicAuthAndHeaderAudit() -> None:
    """Verifies live HTTP client constructs RFC-compliant Basic Auth and Content-Type headers."""
    capturedHeaders: dict[str, str] = {}

    def mockHandler(request: httpx.Request) -> httpx.Response:
        nonlocal capturedHeaders
        capturedHeaders = dict(request.headers)
        return httpx.Response(status_code=200, json={"id": "pay_live_test", "amount": 5000, "status": "captured"})

    mockTransport = httpx.MockTransport(mockHandler)
    async with httpx.AsyncClient(transport=mockTransport) as httpClient:
        client = RazorpayRouteClient(apiKey="rzp_live_test_key", apiSecret="super_secret_token", isMockMode=False, httpClient=httpClient)
        res = await client.capturePayment("pay_live_test", 5000)
        assert res.id == "pay_live_test"
        assert capturedHeaders["authorization"].startswith("Basic ")
        assert capturedHeaders["content-type"] == "application/json"
        assert capturedHeaders["accept"] == "application/json"


@pytest.mark.asyncio
async def testTwoPhaseCommitSagaLifoCompensatingReversals() -> None:
    """Verifies that when a transfer fails during split phase, previous transfers reverse in LIFO order."""
    client = RazorpayRouteClient(isMockMode=True)
    client.simulatedFailureAccount = "acc_logistics_fail"
    saga = TwoPhaseCommitSaga(routeClient=client, nonceLedger=NonceLedger(fakeredis.aioredis.FakeRedis()))

    manifest = SplitTransferManifest(
        merchantAccount="acc_merchant_1", merchantAmountPaise=10000,
        protocolFeeAccount="acc_protocol_1", protocolFeePaise=50,
        logisticsAccount="acc_logistics_fail", logisticsAmountPaise=500, totalPaise=10550,
    )
    requests = saga.buildTransferRequests(manifest, "pay_saga_lifo_test")
    assert len(requests) == 3

    with pytest.raises(SettlementCompensationTriggeredException) as excInfo:
        await saga.executeSplitPhase(requests)

    assert "triggered rollback of 2 transfers" in str(excInfo.value)
    assert len(client._reversals) == 2
    reversalList = list(client._reversals.values())
    assert reversalList[0].amount == 50
    assert reversalList[1].amount == 10000


def _buildEndToEndPayload() -> tuple[ExecuteSettlementRequestSchema, int]:
    uSigner = Ed25519Signer(generateKeyPair()[0])
    mSigner = Ed25519Signer(generateKeyPair()[0])
    aSigner = Ed25519Signer(generateKeyPair()[0])

    intentM = createSignedIntentMandate(
        mandateId="M-I-E2E-CHALLENGER", userSigner=uSigner, delegatedAgentDid=aSigner.getAgentDid(),
        maxBudgetPaise=100000, upiCircleDelegationToken="upi_tok_test",
        singleTransactionLimitPaise=100000, validUntilTimestamp=2000000000,
    )
    item = CartItemSchema(
        skuId="SKU-E2E", quantity=1, unitPricePaise=50000,
        hsnCode="84713010", gstRatePercent=18, lineTotalPaise=50000,
    )
    cartM = createSignedCartMandate(
        cartId="M-C-E2E-CHALLENGER", merchantSigner=mSigner, merchantGstin="29AAAAA0000A1ZY",
        merchantStateCode="29", buyerDeliveryPincode="560001", buyerDeliveryStateCode="29",
        items=[item], taxableSubtotalPaise=50000,
        taxBreakdown=TaxBreakdownSchema(cgstPaise=4500, sgstPaise=4500, igstPaise=0, totalTaxPaise=9000),
        shippingPaise=0, discountPaise=0, totalPaise=59000,
        inventoryLockToken="lock_tok", inventoryLockExpiresAt=2000000000,
    )
    execM = createSignedExecutionMandate(
        executionId="M-E-E2E-CHALLENGER", buyerAgentSigner=aSigner,
        intentMandate=intentM, cartMandate=cartM, settlementAmountPaise=59000,
        upiCircleToken="upi_tok_test", timestamp=int(time.time()),
    )
    return ExecuteSettlementRequestSchema(
        intentMandate=intentM, cartMandate=cartM, executionMandate=execM,
        merchantAccount="acc_merchant_e2e", paymentId="pay_e2e_001",
    ), 59000


@pytest.mark.asyncio
async def testMandateAppEndToEndExecutionViaFastApi() -> None:
    """Verifies FastAPI endpoint POST /api/v1/settlement/execute full lifecycle."""
    app = createMandateApp()
    fakeRedis = fakeredis.aioredis.FakeRedis()
    nonceLedger = NonceLedger(fakeRedis)
    routeClient = RazorpayRouteClient(isMockMode=True)
    orchestrator = SettlementOrchestrator(
        routeClient=routeClient, nonceLedger=nonceLedger,
        protocolFeeAccount="acc_proto", protocolFeePaise=50, logisticsAccount="acc_logistics",
    )
    app.state.redis = fakeRedis
    app.state.nonceLedger = nonceLedger
    app.state.routeClient = routeClient
    app.state.settlementOrchestrator = orchestrator

    reqPayload, total = _buildEndToEndPayload()
    transport = ASGITransport(app=app)
    async with httpx.AsyncClient(transport=transport, base_url="http://test") as client:
        resp = await client.post("/api/v1/settlement/execute", json=reqPayload.model_dump())
        assert resp.status_code == 200
        data = resp.json()
        assert data["status"] == "captured" and data["amountPaise"] == total
        assert data["paymentId"] == "pay_e2e_001"
        assert data["invoice"]["sellerGstin"] == "29AAAAA0000A1ZY"
        assert data["invoice"]["grandTotalPaise"] == total
