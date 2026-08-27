"""Milestone 2 Challenger: Budget Gate, FastAPI Routes, and HTML Invoice Stress.

Tests:
1. AP2 Budget Gate validations, ceilings, and drifts
2. FastAPI Route Initialization, Endpoints, & Settlement
3. GSTR-1 HTML Invoice Rendering, Multi-Line Items, & XSS Sanitization
"""

import time
import fakeredis.aioredis
from fastapi.testclient import TestClient
import pytest

from razoragentMesh.packages.mandateEngine.crypto.cryptoKeyUtils import generateKeyPair
from razoragentMesh.packages.mandateEngine.crypto.ed25519Signer import Ed25519Signer
from razoragentMesh.packages.mandateEngine.mandateApp import (
    createMandateApp,
    endpointHealth,
    endpointSettlementExecute,
    endpointTelemetryEvents,
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
from razoragentMesh.packages.mandateEngine.settlement.settlementExceptions import (
    ArithmeticEnclaveMismatchException,
    BudgetExceededViolation,
    CategoryNotAuthorizedException,
    MandateExpiredException,
    SingleTransactionLimitExceededException,
)
from razoragentMesh.packages.mandateEngine.settlement.settlementOrchestrator import (
    SettlementOrchestrator,
)
from razoragentMesh.packages.mandateEngine.tax.gstrInvoiceEngine import (
    GstrInvoicePayload,
    GstrLineItem,
)
from razoragentMesh.packages.mandateEngine.tax.gstrInvoiceHtmlRenderer import (
    formatPaiseToInr,
    renderGstrInvoiceHtml,
)
from razoragentMesh.packages.mandateEngine.telemetryEmitter import (
    TelemetryEventModel,
)
from razoragentMesh.packages.mandateEngine.verification.budgetGate import (
    validateBudgetGate,
)


def _buildBudgetGateFixtures():
    userSigner = Ed25519Signer(generateKeyPair()[0])
    merchantSigner = Ed25519Signer(generateKeyPair()[0])
    agentSigner = Ed25519Signer(generateKeyPair()[0])
    ts = int(time.time())

    intent = createSignedIntentMandate(
        mandateId="M-I-BG-01", userSigner=userSigner,
        delegatedAgentDid=agentSigner.getAgentDid(), maxBudgetPaise=300000,
        upiCircleDelegationToken="tok_upi", singleTransactionLimitPaise=200000,
        authorizedCategories=["electronics", "apparel"], validUntilTimestamp=ts + 3600,
    )
    items = [
        CartItemSchema(
            skuId="SKU-01", quantity=1, unitPricePaise=100000,
            hsnCode="8517", gstRatePercent=18, lineTotalPaise=100000,
        )
    ]
    cart = createSignedCartMandate(
        cartId="M-C-BG-01", merchantSigner=merchantSigner,
        merchantGstin="29ABCDE1234F1ZW", merchantStateCode="29",
        buyerDeliveryPincode="560001", buyerDeliveryStateCode="29",
        items=items, taxableSubtotalPaise=100000,
        taxBreakdown=TaxBreakdownSchema(cgstPaise=9000, sgstPaise=9000, igstPaise=0, totalTaxPaise=18000),
        shippingPaise=0, discountPaise=0, totalPaise=118000,
        inventoryLockToken="lock_tok", inventoryLockExpiresAt=ts + 900,
    )
    execution = createSignedExecutionMandate(
        executionId="M-E-BG-01", buyerAgentSigner=agentSigner,
        intentMandate=intent, cartMandate=cart, settlementAmountPaise=118000,
        upiCircleToken="tok_upi",
    )
    return intent, cart, execution, userSigner, agentSigner, ts


class TestBudgetGateStress:
    """Stress tests AP2 Budget Gate validations, ceilings, and drifts."""

    def testBudgetGateNominalAndBudgetBreach(self) -> None:
        intent, cart, execution, userSigner, agentSigner, _ = _buildBudgetGateFixtures()
        assert validateBudgetGate(intent, cart, execution, skuCategories=["electronics"]) is True

        overBudgetIntent = createSignedIntentMandate(
            mandateId="M-I-BG-OVER", userSigner=userSigner,
            delegatedAgentDid=agentSigner.getAgentDid(), maxBudgetPaise=50000,
            upiCircleDelegationToken="tok_upi", singleTransactionLimitPaise=200000,
        )
        with pytest.raises(BudgetExceededViolation):
            validateBudgetGate(overBudgetIntent, cart, execution)

    def testBudgetGateSingleLimitAndExpiry(self) -> None:
        _, cart, execution, userSigner, agentSigner, ts = _buildBudgetGateFixtures()
        overSingleIntent = createSignedIntentMandate(
            mandateId="M-I-BG-SINGLE", userSigner=userSigner,
            delegatedAgentDid=agentSigner.getAgentDid(), maxBudgetPaise=500000,
            upiCircleDelegationToken="tok_upi", singleTransactionLimitPaise=100000,
        )
        with pytest.raises(SingleTransactionLimitExceededException):
            validateBudgetGate(overSingleIntent, cart, execution)

        expiredIntent = createSignedIntentMandate(
            mandateId="M-I-BG-EXPIRED", userSigner=userSigner,
            delegatedAgentDid=agentSigner.getAgentDid(), maxBudgetPaise=500000,
            upiCircleDelegationToken="tok_upi", singleTransactionLimitPaise=500000,
            validUntilTimestamp=ts - 100,
        )
        with pytest.raises(MandateExpiredException):
            validateBudgetGate(expiredIntent, cart, execution, currentTimestamp=ts)

    def testBudgetGateCategoryAndDrift(self) -> None:
        intent, cart, execution, _, _, _ = _buildBudgetGateFixtures()
        with pytest.raises(CategoryNotAuthorizedException):
            validateBudgetGate(intent, cart, execution, skuCategories=["luxury_jewelry"])

        driftExec = execution.model_copy(update={"settlementAmountPaise": 119000})
        with pytest.raises(ArithmeticEnclaveMismatchException):
            validateBudgetGate(intent, cart, driftExec)


def _setupFastApiClient():
    app = createMandateApp()
    fakeRedis = fakeredis.aioredis.FakeRedis()
    app.state.redis = fakeRedis
    app.state.nonceLedger = NonceLedger(fakeRedis)
    app.state.routeClient = RazorpayRouteClient(isMockMode=True)
    app.state.settlementOrchestrator = SettlementOrchestrator(
        routeClient=app.state.routeClient, nonceLedger=app.state.nonceLedger,
        protocolFeeAccount="acc_protocol_fees", protocolFeePaise=500,
        logisticsAccount="acc_logistics_partner",
    )
    return TestClient(app)


def _buildFastApiPayload(fixedTs: int):
    userSigner = Ed25519Signer(generateKeyPair()[0])
    merchantSigner = Ed25519Signer(generateKeyPair()[0])
    agentSigner = Ed25519Signer(generateKeyPair()[0])
    intent = createSignedIntentMandate(
        mandateId="M-I-FASTAPI-01", userSigner=userSigner,
        delegatedAgentDid=agentSigner.getAgentDid(), maxBudgetPaise=200000,
        upiCircleDelegationToken="tok_upi", singleTransactionLimitPaise=200000,
        timestamp=fixedTs,
    )
    items = [
        CartItemSchema(
            skuId="SKU-01", quantity=1, unitPricePaise=100000,
            hsnCode="8517", gstRatePercent=18, lineTotalPaise=100000,
        )
    ]
    cart = createSignedCartMandate(
        cartId="M-C-FASTAPI-01", merchantSigner=merchantSigner,
        merchantGstin="29ABCDE1234F1ZW", merchantStateCode="29",
        buyerDeliveryPincode="560001", buyerDeliveryStateCode="29",
        items=items, taxableSubtotalPaise=100000,
        taxBreakdown=TaxBreakdownSchema(cgstPaise=9000, sgstPaise=9000, igstPaise=0, totalTaxPaise=18000),
        shippingPaise=0, discountPaise=0, totalPaise=118000,
        inventoryLockToken="lock_tok", inventoryLockExpiresAt=fixedTs + 900,
        timestamp=fixedTs,
    )
    execution = createSignedExecutionMandate(
        executionId="M-E-FASTAPI-01", buyerAgentSigner=agentSigner,
        intentMandate=intent, cartMandate=cart, settlementAmountPaise=118000,
        upiCircleToken="tok_upi", timestamp=fixedTs,
    )
    return {
        "intentMandate": intent.model_dump(), "cartMandate": cart.model_dump(),
        "executionMandate": execution.model_dump(), "merchantAccount": "acc_merchant_123",
        "paymentId": "pay_fastapi_001", "serverTime": fixedTs,
    }


class TestFastApiMandateApp:
    """Stress tests FastAPI route registration, endpoints, and error handling."""

    def testAppRoutesHealthAndTelemetry(self) -> None:
        client = _setupFastApiClient()
        res = client.get(endpointHealth)
        assert res.status_code == 200 and res.json()["status"] == "healthy"

        event = TelemetryEventModel(
            eventId="evt_001", eventType="SYSTEM_PING",
            timestampMs=int(time.time() * 1000), sessionId="sess_001",
            payload={"ok": True},
        )
        res = client.post(endpointTelemetryEvents, json=event.model_dump())
        assert res.status_code == 200 and res.json()["status"] == "broadcasted"

    def testAppSettlementExecutionAndReplay(self) -> None:
        client = _setupFastApiClient()
        fixedTs = int(time.time())
        payload = _buildFastApiPayload(fixedTs)
        res = client.post(endpointSettlementExecute, json=payload)
        assert res.status_code == 200 and res.json()["status"] == "captured"
        assert res.json()["amountPaise"] == 118000
        assert client.post(endpointSettlementExecute, json=payload).status_code == 409


def _buildMultiLineInvoice() -> tuple[GstrInvoicePayload, int]:
    lineItems, totalTaxable, totalCgst, totalSgst = [], 0, 0, 0
    for i in range(5):
        rate = [0, 5, 12, 18, 28][i]
        unitPrice, qty = 10000 * (i + 1), 2
        taxable = unitPrice * qty
        cgst = (taxable * (rate // 2)) // 100
        sgst = ((taxable * rate) // 100) - cgst
        lineItems.append(GstrLineItem(
            skuId=f"SKU-ITEM-{i:02d}", hsnCode=f"850{i}", quantity=qty,
            unitPricePaise=unitPrice, taxableAmountPaise=taxable, gstRatePercent=rate,
            cgstPaise=cgst, sgstPaise=sgst, igstPaise=0, totalLinePaise=taxable + cgst + sgst,
        ))
        totalTaxable += taxable
        totalCgst += cgst
        totalSgst += sgst
    totTax = totalCgst + totalSgst
    invoice = GstrInvoicePayload(
        invoiceNumber="INV-STRESS-HTML-01", invoiceDate="2026-08-24T18:00:00Z",
        sellerGstin="29AAAAA0000A1ZY", merchantStateCode="29", placeOfSupplyStateCode="29",
        isIntraState=True, lineItems=lineItems, taxableAmountPaise=totalTaxable,
        totalCgstPaise=totalCgst, totalSgstPaise=totalSgst, totalIgstPaise=0,
        totalTaxPaise=totTax, totalTcsPaise=(totalTaxable * 100) // 10000,
        shippingPaise=5000, discountPaise=2500,
        grandTotalPaise=totalTaxable + totTax + 5000 - 2500, cryptographicAuditHash="b" * 64,
    )
    return invoice, totalTaxable


class TestHtmlInvoiceRendererStress:
    """Stress tests GSTR HTML rendering, security escaping, and formatting."""

    def testMultiLineItemAndXssEscaping(self) -> None:
        invoice, totalTaxable = _buildMultiLineInvoice()
        renderedHtml = renderGstrInvoiceHtml(
            invoice,
            merchantLegalName='Safe Merchant <script>alert("xss")</script>',
            buyerLegalName='Agent Buyer " onclick="malicious()',
        )
        assert "<!DOCTYPE html>" in renderedHtml and "INV-STRESS-HTML-01" in renderedHtml
        assert "<script>" not in renderedHtml and 'onclick="malicious()' not in renderedHtml
        assert "Safe Merchant &lt;script&gt;" in renderedHtml
        assert "Agent Buyer &quot; onclick=&quot;" in renderedHtml
        assert formatPaiseToInr(totalTaxable) in renderedHtml
        assert invoice.cryptographicAuditHash in renderedHtml
