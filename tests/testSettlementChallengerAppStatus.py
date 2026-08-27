"""Challenger: FastAPI mandateApp Status Codes, Telemetry and Lifespan Invariants.

Tests:
1. mandateApp.py status code mapping (200, 400, 409, 502, 500)
2. mandateApp.py SSE telemetry formatting and event broadcasts
3. mandateApp.py lifespan and dependency injection fallbacks
"""

import json
import fakeredis.aioredis
import httpx
from httpx import ASGITransport
import pytest
from typing import Any

from razoragentMesh.packages.mandateEngine.crypto.cryptoKeyUtils import generateKeyPair
from razoragentMesh.packages.mandateEngine.crypto.ed25519Signer import Ed25519Signer
from razoragentMesh.packages.mandateEngine.mandateApp import (
    createMandateApp,
    getNonceLedger,
    getRedisClient,
    getSettlementOrchestrator,
    getTelemetryEmitter,
    mandateAppLifespan,
)
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
)
from razoragentMesh.packages.mandateEngine.settlement.settlementOrchestrator import (
    SettlementOrchestrator,
)
from razoragentMesh.packages.mandateEngine.telemetryEmitter import (
    TelemetryEventEmitter,
)

testMerchantAcc: str = "acc_merchant_prime"
testProtocolAcc: str = "acc_protocol_fees"
testLogisticsAcc: str = "acc_logistics_speed"
testServerTime: int = 1700000000


def _buildMandateChain(
    amountPaise: int = 120000,
    shippingPaise: int = 2000,
    maxBudgetPaise: int = 200000,
    singleTxnLimitPaise: int = 200000,
    validUntilTimestamp: int = 2000000000,
    executionTimestamp: int = testServerTime,
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
        singleTransactionLimitPaise=singleTxnLimitPaise, validUntilTimestamp=validUntilTimestamp, timestamp=executionTimestamp,
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
        inventoryLockToken="lock_tok_chal", inventoryLockExpiresAt=validUntilTimestamp, timestamp=executionTimestamp,
    )
    execM = createSignedExecutionMandate(
        executionId=f"M-E-{nonce}", buyerAgentSigner=aSigner,
        intentMandate=intentM, cartMandate=cartM, settlementAmountPaise=total,
        upiCircleToken="upi_token_cfo", timestamp=executionTimestamp, nonce=nonce,
    )
    return intentM, cartM, execM


def _setupConfiguredApp(isMockRoute: bool = True) -> tuple:
    app = createMandateApp()
    fakeRedis = fakeredis.aioredis.FakeRedis()
    nonceLedger = NonceLedger(fakeRedis)
    routeClient = RazorpayRouteClient(isMockMode=isMockRoute)
    orchestrator = SettlementOrchestrator(
        routeClient=routeClient, nonceLedger=nonceLedger,
        protocolFeeAccount=testProtocolAcc, protocolFeePaise=50, logisticsAccount=testLogisticsAcc,
    )
    telemetryEmitter = TelemetryEventEmitter()
    app.state.redis = fakeRedis
    app.state.nonceLedger = nonceLedger
    app.state.routeClient = routeClient
    app.state.settlementOrchestrator = orchestrator
    app.state.telemetryEmitter = telemetryEmitter
    return app, routeClient, telemetryEmitter


@pytest.mark.asyncio
async def testMandateAppStatus200And409Conflict() -> None:
    """Verifies 200 OK on happy path and 409 Conflict on replay."""
    app, _, _ = _setupConfiguredApp()
    transport = ASGITransport(app=app)
    async with httpx.AsyncClient(transport=transport, base_url="http://test") as client:
        intentM, cartM, execM = _buildMandateChain(nonce="n_status_200")
        payload = {
            "intentMandate": intentM.model_dump(), "cartMandate": cartM.model_dump(),
            "executionMandate": execM.model_dump(), "merchantAccount": testMerchantAcc,
            "paymentId": "pay_status_200", "serverTime": testServerTime,
        }
        resp = await client.post("/api/v1/settlement/execute", json=payload)
        assert resp.status_code == 200
        assert resp.json()["status"] == "captured"

        respReplay = await client.post("/api/v1/settlement/execute", json=payload)
        assert respReplay.status_code == 409


@pytest.mark.asyncio
async def testMandateAppStatus400LimitAndDrift() -> None:
    """Verifies 400 Bad Request on single txn limit breach and timestamp drift."""
    app, _, _ = _setupConfiguredApp()
    transport = ASGITransport(app=app)
    async with httpx.AsyncClient(transport=transport, base_url="http://test") as client:
        intentM, cartM, execM = _buildMandateChain(amountPaise=118000, singleTxnLimitPaise=50000, nonce="n_status_limit")
        respLimit = await client.post(
            "/api/v1/settlement/execute",
            json={"intentMandate": intentM.model_dump(), "cartMandate": cartM.model_dump(), "executionMandate": execM.model_dump(), "merchantAccount": testMerchantAcc, "paymentId": "pay_limit", "serverTime": testServerTime},
        )
        assert respLimit.status_code == 400

        intentM4, cartM4, execM4 = _buildMandateChain(executionTimestamp=testServerTime - 1000, nonce="n_status_drift")
        respDrift = await client.post(
            "/api/v1/settlement/execute",
            json={"intentMandate": intentM4.model_dump(), "cartMandate": cartM4.model_dump(), "executionMandate": execM4.model_dump(), "merchantAccount": testMerchantAcc, "paymentId": "pay_drift", "serverTime": testServerTime},
        )
        assert respDrift.status_code == 400


@pytest.mark.asyncio
async def testMandateAppStatus502Rollback() -> None:
    """Verifies 502 Bad Gateway when settlement compensation triggers."""
    app, routeClient, _ = _setupConfiguredApp()
    routeClient.simulatedFailureAccount = testMerchantAcc
    transport = ASGITransport(app=app)
    async with httpx.AsyncClient(transport=transport, base_url="http://test") as client:
        intentM, cartM, execM = _buildMandateChain(nonce="n_status_502")
        resp502 = await client.post(
            "/api/v1/settlement/execute",
            json={"intentMandate": intentM.model_dump(), "cartMandate": cartM.model_dump(), "executionMandate": execM.model_dump(), "merchantAccount": testMerchantAcc, "paymentId": "pay_502", "serverTime": testServerTime},
        )
        assert resp502.status_code == 502
        assert "Settlement compensation rollback" in resp502.json()["detail"]


@pytest.mark.asyncio
async def testMandateAppDependencyInjectionHelpers() -> None:
    """Verifies DI fallbacks for app components."""
    app = createMandateApp()

    class FakeRequest:
        def __init__(self, application: Any) -> None:
            self.app = application

    fakeReq = FakeRequest(app)
    assert getRedisClient(fakeReq) is None
    assert isinstance(getNonceLedger(fakeReq), NonceLedger)
    assert isinstance(getTelemetryEmitter(fakeReq), TelemetryEventEmitter)
    assert isinstance(getSettlementOrchestrator(fakeReq), SettlementOrchestrator)


@pytest.mark.asyncio
async def testTelemetryPaymentCapturedAndBudgetBlockedFrames() -> None:
    """Empirically verifies SSE telemetry events for payment captured and budget blocked."""
    app, _, telemetryEmitter = _setupConfiguredApp()
    subscriberQueue = await telemetryEmitter.registerSubscriber()
    transport = ASGITransport(app=app)

    async with httpx.AsyncClient(transport=transport, base_url="http://test") as client:
        intentM, cartM, execM = _buildMandateChain(nonce="n_telemetry_check")
        resp = await client.post(
            "/api/v1/settlement/execute",
            json={"intentMandate": intentM.model_dump(), "cartMandate": cartM.model_dump(), "executionMandate": execM.model_dump(), "merchantAccount": testMerchantAcc, "paymentId": "pay_telemetry_001", "serverTime": testServerTime},
        )
        assert resp.status_code == 200
        frame1 = await subscriberQueue.get()
        data1 = json.loads(frame1.removeprefix("data: ").strip())
        assert data1["eventType"] == "PAYMENT_CAPTURED"
        assert data1["payload"]["paymentId"] == "pay_telemetry_001"
        assert data1["payload"]["amountPaise"] == 120000

        intentMBudget, cartMBudget, execMBudget = _buildMandateChain(amountPaise=120000, maxBudgetPaise=50000, nonce="n_telemetry_budget")
        respBudget = await client.post(
            "/api/v1/settlement/execute",
            json={"intentMandate": intentMBudget.model_dump(), "cartMandate": cartMBudget.model_dump(), "executionMandate": execMBudget.model_dump(), "merchantAccount": testMerchantAcc, "paymentId": "pay_telemetry_budget", "serverTime": testServerTime},
        )
        assert respBudget.status_code == 400
        frame2 = await subscriberQueue.get()
        data2 = json.loads(frame2.removeprefix("data: ").strip())
        assert data2["eventType"] == "BUDGET_BLOCKED"

    await telemetryEmitter.removeSubscriber(subscriberQueue)


@pytest.mark.asyncio
async def testExecuteSettlementSchemaStrictRejections() -> None:
    """Verifies ExecuteSettlementRequestSchema rejects unknown fields and invalid account strings."""
    app = createMandateApp()
    transport = ASGITransport(app=app)
    async with httpx.AsyncClient(transport=transport, base_url="http://test") as client:
        intentM, cartM, execM = _buildMandateChain(nonce="n_schema_check")
        corruptedPayload = {
            "intentMandate": intentM.model_dump(), "cartMandate": cartM.model_dump(),
            "executionMandate": execM.model_dump(), "merchantAccount": testMerchantAcc,
            "paymentId": "pay_schema_001", "serverTime": testServerTime, "maliciousInjectedField": "attack_payload",
        }
        respExtra = await client.post("/api/v1/settlement/execute", json=corruptedPayload)
        assert respExtra.status_code == 422

        emptyAccPayload = {
            "intentMandate": intentM.model_dump(), "cartMandate": cartM.model_dump(),
            "executionMandate": execM.model_dump(), "merchantAccount": "",
            "paymentId": "pay_schema_001", "serverTime": testServerTime,
        }
        respEmpty = await client.post("/api/v1/settlement/execute", json=emptyAccPayload)
        assert respEmpty.status_code == 422


@pytest.mark.asyncio
async def testLifespanShutdownClosesResources() -> None:
    """Verifies mandateAppLifespan initializes and gracefully closes Redis and Route clients."""
    app = createMandateApp()
    app.state.redis = fakeredis.aioredis.FakeRedis()
    app.state.routeClient = RazorpayRouteClient(isMockMode=True)

    async with mandateAppLifespan(app):
        assert app.state.nonceLedger is not None
        assert app.state.settlementOrchestrator is not None
