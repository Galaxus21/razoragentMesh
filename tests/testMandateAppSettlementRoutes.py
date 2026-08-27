"""Tests for FastAPI Mandate Engine application settlement endpoints."""

import fakeredis.aioredis
import httpx
from httpx import ASGITransport
import pytest

from razoragentMesh.packages.mandateEngine.crypto.cryptoKeyUtils import generateKeyPair
from razoragentMesh.packages.mandateEngine.crypto.ed25519Signer import Ed25519Signer
from razoragentMesh.packages.mandateEngine.mandateApp import (
    ExecuteSettlementRequestSchema,
    createMandateApp,
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
from razoragentMesh.packages.mandateEngine.settlement.razorpayRouteClient import RazorpayRouteClient
from razoragentMesh.packages.mandateEngine.settlement.settlementOrchestrator import SettlementOrchestrator
from razoragentMesh.packages.mandateEngine.telemetryEmitter import TelemetryEventEmitter

testMerchantAccountId: str = "acc_merchant_prime_01"
testProtocolFeeAccount: str = "acc_protocol_fees"
testPaymentId: str = "pay_app_test_001"
testServerTime: int = 1700000000


def _buildTestMandateTriplet(amountPaise: int = 118000, maxBudgetPaise: int = 200000, nonceSuffix: str = "01") -> tuple:
    uSigner = Ed25519Signer(generateKeyPair()[0])
    mSigner = Ed25519Signer(generateKeyPair()[0])
    aSigner = Ed25519Signer(generateKeyPair()[0])

    intentM = createSignedIntentMandate(
        mandateId=f"M-I-TEST-{nonceSuffix}", userSigner=uSigner, delegatedAgentDid=aSigner.getAgentDid(),
        maxBudgetPaise=maxBudgetPaise, upiCircleDelegationToken="upi_tok_test",
        singleTransactionLimitPaise=maxBudgetPaise, validUntilTimestamp=2000000000,
    )
    taxable = 100000
    item = CartItemSchema(
        skuId="SKU-TEST-01", quantity=1, unitPricePaise=taxable,
        hsnCode="84713010", gstRatePercent=18, lineTotalPaise=taxable,
    )
    cartM = createSignedCartMandate(
        cartId=f"M-C-TEST-{nonceSuffix}", merchantSigner=mSigner, merchantGstin="29AAAAA0000A1ZY",
        merchantStateCode="29", buyerDeliveryPincode="560001", buyerDeliveryStateCode="29",
        items=[item], taxableSubtotalPaise=taxable,
        taxBreakdown=TaxBreakdownSchema(cgstPaise=9000, sgstPaise=9000, igstPaise=0, totalTaxPaise=18000),
        shippingPaise=0, discountPaise=0, totalPaise=amountPaise,
        inventoryLockToken="lock_test", inventoryLockExpiresAt=2000000000,
    )
    execM = createSignedExecutionMandate(
        executionId=f"M-E-TEST-{nonceSuffix}", buyerAgentSigner=aSigner,
        intentMandate=intentM, cartMandate=cartM, settlementAmountPaise=amountPaise,
        upiCircleToken="upi_tok_test", timestamp=testServerTime,
    )
    return intentM, cartM, execM


def _configureTestApp(routeClient: RazorpayRouteClient | None = None) -> tuple:
    app = createMandateApp()
    fakeRedis = fakeredis.aioredis.FakeRedis()
    nonceLedger = NonceLedger(fakeRedis)
    client = routeClient or RazorpayRouteClient(isMockMode=True)
    orchestrator = SettlementOrchestrator(
        routeClient=client, nonceLedger=nonceLedger, protocolFeeAccount=testProtocolFeeAccount, protocolFeePaise=50,
    )
    telemetryEmitter = TelemetryEventEmitter()
    app.state.redis = fakeRedis
    app.state.nonceLedger = nonceLedger
    app.state.routeClient = client
    app.state.settlementOrchestrator = orchestrator
    app.state.telemetryEmitter = telemetryEmitter
    return app, client, telemetryEmitter


@pytest.mark.asyncio
async def testHealthCheckEndpoint() -> None:
    app, _, _ = _configureTestApp()
    transport = ASGITransport(app=app)
    async with httpx.AsyncClient(transport=transport, base_url="http://test") as client:
        resp = await client.get("/health")
        assert resp.status_code == 200 and resp.json()["status"] == "healthy"


@pytest.mark.asyncio
async def testExecuteSettlementHappyPathWithTelemetry() -> None:
    app, _, _ = _configureTestApp()
    intentM, cartM, execM = _buildTestMandateTriplet(amountPaise=118000, nonceSuffix="HAPPY")
    requestPayload = ExecuteSettlementRequestSchema(
        intentMandate=intentM, cartMandate=cartM, executionMandate=execM,
        merchantAccount=testMerchantAccountId, paymentId=testPaymentId, serverTime=testServerTime,
    )
    transport = ASGITransport(app=app)
    async with httpx.AsyncClient(transport=transport, base_url="http://test") as client:
        resp = await client.post("/api/v1/settlement/execute", json=requestPayload.model_dump())
        assert resp.status_code == 200
        data = resp.json()
        assert data["status"] == "captured" and data["amountPaise"] == 118000


@pytest.mark.asyncio
async def testExecuteSettlementRollbackCompensation502() -> None:
    routeClient = RazorpayRouteClient(isMockMode=True)
    routeClient.simulatedFailureAccount = testProtocolFeeAccount
    app, _, _ = _configureTestApp(routeClient=routeClient)

    intentM, cartM, execM = _buildTestMandateTriplet(amountPaise=118000, nonceSuffix="ROLLBACK")
    requestPayload = ExecuteSettlementRequestSchema(
        intentMandate=intentM, cartMandate=cartM, executionMandate=execM,
        merchantAccount=testMerchantAccountId, paymentId="pay_fail_rollback_001", serverTime=testServerTime,
    )
    transport = ASGITransport(app=app)
    async with httpx.AsyncClient(transport=transport, base_url="http://test") as client:
        resp = await client.post("/api/v1/settlement/execute", json=requestPayload.model_dump())
        assert resp.status_code == 502
        assert len(routeClient._reversals) == 1


@pytest.mark.asyncio
async def testExecuteSettlementNonceReplay409() -> None:
    app, _, _ = _configureTestApp()
    intentM, cartM, execM = _buildTestMandateTriplet(amountPaise=118000, nonceSuffix="REPLAY")
    requestPayload = ExecuteSettlementRequestSchema(
        intentMandate=intentM, cartMandate=cartM, executionMandate=execM,
        merchantAccount=testMerchantAccountId, paymentId="pay_replay_001", serverTime=testServerTime,
    )
    transport = ASGITransport(app=app)
    async with httpx.AsyncClient(transport=transport, base_url="http://test") as client:
        resp1 = await client.post("/api/v1/settlement/execute", json=requestPayload.model_dump())
        assert resp1.status_code == 200
        resp2 = await client.post("/api/v1/settlement/execute", json=requestPayload.model_dump())
        assert resp2.status_code == 409


@pytest.mark.asyncio
async def testExecuteSettlementBudgetBreach400() -> None:
    app, _, _ = _configureTestApp()
    intentM, cartM, execM = _buildTestMandateTriplet(amountPaise=118000, maxBudgetPaise=50000, nonceSuffix="BUDGET")
    requestPayload = ExecuteSettlementRequestSchema(
        intentMandate=intentM, cartMandate=cartM, executionMandate=execM,
        merchantAccount=testMerchantAccountId, paymentId="pay_budget_breach_001", serverTime=testServerTime,
    )
    transport = ASGITransport(app=app)
    async with httpx.AsyncClient(transport=transport, base_url="http://test") as client:
        resp = await client.post("/api/v1/settlement/execute", json=requestPayload.model_dump())
        assert resp.status_code == 400


@pytest.mark.asyncio
async def testExecuteSettlementTamperedSignature400() -> None:
    app, _, _ = _configureTestApp()
    intentM, cartM, execM = _buildTestMandateTriplet(amountPaise=118000, nonceSuffix="TAMPER")
    corruptedExecDict = execM.model_dump()
    corruptedExecDict["agentSignature"] = "00" * 64

    transport = ASGITransport(app=app)
    async with httpx.AsyncClient(transport=transport, base_url="http://test") as client:
        payload = {
            "intentMandate": intentM.model_dump(), "cartMandate": cartM.model_dump(),
            "executionMandate": corruptedExecDict, "merchantAccount": testMerchantAccountId,
            "paymentId": "pay_tamper_001", "serverTime": testServerTime,
        }
        resp = await client.post("/api/v1/settlement/execute", json=payload)
        assert resp.status_code == 400
