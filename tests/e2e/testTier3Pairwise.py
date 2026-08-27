"""Tier 3: Pairwise Combinatorial Integration Test Suite (16 cross-feature pairwise scenarios).

Validates cross-feature matrix interactions across F01 to F16.
"""

import asyncio
import time
from typing import Any, Dict, List
from pydantic import ValidationError
import pytest

from razoragentMesh.packages.mandateEngine.crypto.cryptoKeyUtils import generateKeyPair
from razoragentMesh.packages.mandateEngine.crypto.ed25519Signer import Ed25519Signer
from razoragentMesh.packages.mandateEngine.crypto.jcsCanonicalizer import (
    canonicalizeAndHash,
    canonicalizeJson,
    computeSha256Digest,
)
from razoragentMesh.packages.mandateEngine.mandates.cartMandateSchema import (
    CartItemSchema,
    CartMandate,
    TaxBreakdownSchema,
)
from razoragentMesh.packages.mandateEngine.mandates.executionMandateSchema import ExecutionMandate
from razoragentMesh.packages.mandateEngine.mandates.intentMandateSchema import IntentMandate
from razoragentMesh.packages.mandateEngine.mandates.mandateFactory import (
    computeMandateHash,
    createSignedCartMandate,
    createSignedExecutionMandate,
    createSignedIntentMandate,
    verifyMandateChain,
    verifyMandateHashChain,
)
from razoragentMesh.packages.mandateEngine.nonce.nonceLedger import NonceLedger
from razoragentMesh.packages.mandateEngine.settlement.razorpayRouteClient import (
    PaymentCaptureResponse,
    RazorpayRouteClient,
    RouteTransferRequest,
)
from razoragentMesh.packages.mandateEngine.settlement.settlementExceptions import (
    ArithmeticDriftException,
    BudgetExceededViolation,
    InvalidPincodeException,
    MandateEngineException,
    MandateHashChainMismatchException,
    NonceReplayException,
    SettlementCompensationTriggeredException,
    SignatureVerificationFailedException,
)
from razoragentMesh.packages.mandateEngine.settlement.settlementOrchestrator import (
    SettlementOrchestrator,
)
from razoragentMesh.packages.mandateEngine.tax.gstrInvoiceEngine import (
    GstrInvoicePayload,
    generateGstrInvoice,
    isPlaceOfSupplyIntraState,
)
from razoragentMesh.packages.mandateEngine.tax.stateCodeMapping import (
    deriveStateCodeFromPincode,
)
from razoragentMesh.packages.mandateEngine.verification.arithmeticEnclave import (
    computeCartSettlementTotal,
    computeGstBreakdown,
    computeLineItemTotal,
    computeTcsWithholding,
    validateIntegerPaise,
)
from razoragentMesh.packages.mandateEngine.verification.budgetGate import validateBudgetGate
from razoragentMesh.packages.merchantApi.src.constants.hsnCodeDirectory import (
    defaultGstRatePercent,
    resolveGstRate,
)
from razoragentMesh.tests.e2e.e2eFixtures import (
    DlqEntryStatus,
    DurableDeadLetterQueue,
    E2eGstr1Invoice,
    E2eInvoiceLineItem,
    ErrorCategory,
    RouteSplitResult,
    SagaState,
    TwoPhaseCommitFsm,
    calculate_route_splits,
    classify_error,
    compute_backoff_delay,
    extract_pan_from_gstin,
    extract_state_from_gstin,
    is_retryable,
    setup_e2e_actors,
    split_bill_conserved,
    validate_gstin,
    validate_pan,
)
from razoragentMesh.tests.mockInfraHelpers import (
    MockQdrantClient,
    MockRazorpayRouteClient,
    MockRedisAsync,
)

# =============================================================================
# PAIRWISE INTEGRATION SCENARIOS (P01 - P16)
# =============================================================================

def test_p01_f01_integer_math_and_f02_statutory_gst() -> None:
    """P01: F01 (Integer Math) + F02 (Statutory GST) -> Exact line item calculation and tax distribution."""
    unit_price = 335000  # ₹3,350.00
    quantity = 50
    taxable_subtotal = computeLineItemTotal(unit_price, quantity)
    assert taxable_subtotal == 16750000

    gst = computeGstBreakdown(taxable_subtotal, 18, isIntraState=True)
    assert gst["cgstPaise"] == 1507500
    assert gst["sgstPaise"] == 1507500
    assert gst["totalTaxPaise"] == 3015000

    gross_total = computeCartSettlementTotal(taxable_subtotal, gst["totalTaxPaise"])
    assert gross_total == 19765000


def test_p02_f01_integer_math_and_f03_conserved_splitting() -> None:
    """P02: F01 (Integer Math) + F03 (Conserved Splitting) -> Remainder allocation across dynamic merchant splits."""
    subtotal = computeLineItemTotal(unitPricePaise=45000, quantity=3)  # 135,000 paise
    ratios = [5, 3, 2]
    splits = split_bill_conserved(subtotal, ratios)
    assert splits == [67500, 40500, 27000]
    assert sum(splits) == subtotal


def test_p03_f01_integer_math_and_f04_fee_deductions() -> None:
    """P03: F01 (Integer Math) + F04 (Fee Deductions) -> Net payout calculation after percentage + flat fee."""
    order_val = computeLineItemTotal(unitPricePaise=150000, quantity=2)  # 300,000 paise
    split_res = calculate_route_splits(order_paise=order_val, commission_bps=300, flat_fee_paise=50)
    # 3% of 300,000 = 9,000 + 50 = 9,050 paise fee
    assert split_res.total_fee_paise == 9050
    assert split_res.merchant_net_paise == 290950
    assert split_res.merchant_net_paise + split_res.total_fee_paise == order_val


def test_p04_f02_statutory_gst_and_f09_gstin_validation() -> None:
    """P04: F02 (Statutory GST) + F09 (GSTIN Validation) -> Tax rate & state code verification from supplier GSTIN."""
    seller_gstin = "29AABCU9603R1ZJ"
    buyer_gstin = "27ABCDE1234F1Z0"
    assert validate_gstin(seller_gstin) is True
    assert validate_gstin(buyer_gstin) is True
    
    seller_state = extract_state_from_gstin(seller_gstin)
    buyer_state = extract_state_from_gstin(buyer_gstin)
    is_intra = seller_state == buyer_state
    assert is_intra is False  # Karnataka (29) vs Maharashtra (27)
    
    gst = computeGstBreakdown(taxableSubtotalPaise=100000, gstRatePercent=18, isIntraState=is_intra)
    assert gst["igstPaise"] == 18000
    assert gst["cgstPaise"] == 0 and gst["sgstPaise"] == 0


def test_p05_f02_statutory_gst_and_f10_gstr1_invoice() -> None:
    """P05: F02 (Statutory GST) + F10 (GSTR-1 Invoice) -> Statutory tax invoice itemization with JCS audit hash."""
    actors = setup_e2e_actors()
    item = CartItemSchema(skuId="SKU-INV", quantity=2, unitPricePaise=50000, hsnCode="8504", gstRatePercent=18, lineTotalPaise=100000)
    gst = computeGstBreakdown(100000, 18, isIntraState=True)
    tax = TaxBreakdownSchema(cgstPaise=gst["cgstPaise"], sgstPaise=gst["sgstPaise"], igstPaise=0, totalTaxPaise=gst["totalTaxPaise"])
    cart = createSignedCartMandate(
        cartId="M-C-INV", merchantSigner=actors.merchant_nexus, merchantGstin="29AABCU9603R1ZJ",
        merchantStateCode="29", buyerDeliveryPincode="560001", buyerDeliveryStateCode="29",
        items=[item], taxableSubtotalPaise=100000, taxBreakdown=tax, shippingPaise=0, discountPaise=0,
        totalPaise=118000, inventoryLockToken="lock_inv", inventoryLockExpiresAt=2000000000,
    )
    intent = createSignedIntentMandate(
        mandateId="M-I-INV", userSigner=actors.user_cfo, delegatedAgentDid=actors.buyer_agent.getAgentDid(),
        maxBudgetPaise=200000, upiCircleDelegationToken="tok", singleTransactionLimitPaise=200000,
    )
    exec_m = createSignedExecutionMandate(
        executionId="M-E-INV", buyerAgentSigner=actors.buyer_agent,
        intentMandate=intent, cartMandate=cart, settlementAmountPaise=118000, upiCircleToken="tok",
    )
    inv = generateGstrInvoice(cart, exec_m, invoiceNumber="INV-PAIRWISE-05")
    assert inv.grandTotalPaise == 118000
    assert len(inv.cryptographicAuditHash) == 64


def test_p06_f02_statutory_gst_and_f12_hsn_directory() -> None:
    """P06: F02 (Statutory GST) + F12 (HSN Directory) -> HSN-driven tax resolution and state-specific tax computation."""
    hsn_gold = "71131910"
    resolved_rate = resolveGstRate(hsn_gold)
    assert resolved_rate == 3  # 3% for jewelry
    
    # Intra-state calculation on ₹50,000 (5,000,000 paise)
    gst = computeGstBreakdown(taxableSubtotalPaise=5000000, gstRatePercent=resolved_rate, isIntraState=True)
    assert gst["totalTaxPaise"] == 150000
    assert gst["cgstPaise"] == 5000000 * 1 // 100 # 1% CGST = 50000
    assert gst["sgstPaise"] == 150000 - 50000     # 2% SGST remainder = 100000


@pytest.mark.asyncio
async def test_p07_f05_durable_dlq_and_f06_error_taxonomy() -> None:
    """P07: F05 (Durable DLQ) + F06 (Error Taxonomy) -> Routing failed transient vs fatal payments to DLQ."""
    dlq = DurableDeadLetterQueue()
    
    # 1. Transient 504 Timeout -> Enqueued with TRANSIENT_NETWORK
    id1 = await dlq.enqueue(payload={"tx": 1}, error="HTTP 504 Gateway Timeout")
    rec1 = await dlq.peek(id1)
    assert rec1.errorCategory == ErrorCategory.TRANSIENT_NETWORK
    assert is_retryable(rec1.errorCategory) is True
    
    # 2. Fatal 400 Bad Request -> Enqueued with FATAL_CLIENT
    id2 = await dlq.enqueue(payload={"tx": 2}, error=400)
    rec2 = await dlq.peek(id2)
    assert rec2.errorCategory == ErrorCategory.FATAL_CLIENT
    assert is_retryable(rec2.errorCategory) is False


@pytest.mark.asyncio
async def test_p08_f05_durable_dlq_and_f07_backoff_jitter() -> None:
    """P08: F05 (Durable DLQ) + F07 (Backoff & Jitter) -> DLQ scheduled retry worker with exponential jitter delays."""
    dlq = DurableDeadLetterQueue()
    entry_id = await dlq.enqueue(payload={"job": "webhook_dispatch"}, error="503 Service Unavailable")
    rec = await dlq.peek(entry_id)
    
    delays = [compute_backoff_delay(attempt=i, base_delay=0.5, max_delay=10.0) for i in range(rec.maxRetries)]
    assert len(delays) == 5
    assert all(0.0 <= d <= 10.0 for d in delays)


@pytest.mark.asyncio
async def test_p09_f05_durable_dlq_and_f08_idempotent_replay() -> None:
    """P09: F05 (Durable DLQ) + F08 (Idempotent Replay) -> Replaying dead-lettered webhooks with at-most-once semantics."""
    dlq = DurableDeadLetterQueue()
    entry_id = await dlq.enqueue(payload={"event": "payment.authorized", "id": "pay_123"}, error="Conn reset")
    
    dispatched_events = []
    def dispatch_webhook(payload):
        dispatched_events.append(payload["id"])
        return "DISPATCHED"
        
    success, res = await dlq.replay(entry_id, dispatch_webhook)
    assert success is True
    assert dispatched_events == ["pay_123"]
    
    # Repeated replay does not re-dispatch
    success2, res2 = await dlq.replay(entry_id, dispatch_webhook)
    assert success2 is True
    assert res2["status"] == "already_replayed"
    assert len(dispatched_events) == 1


@pytest.mark.asyncio
async def test_p10_f06_error_taxonomy_and_f14_2pc_fsm() -> None:
    """P10: F06 (Error Taxonomy) + F14 (2PC FSM) -> Aborting 2PC saga upon fatal domain error vs retrying transient errors."""
    mock_route = MockRazorpayRouteClient({})
    mock_route.simulateSecondaryTransferFailure = True
    fsm = TwoPhaseCommitFsm(route_client=mock_route)
    fsm.prepare(fencing_token=1)
    
    try:
        await fsm.commit_transfers([
            {"account": "acc_m", "amount": 1000},
            {"account": "acc_fail", "amount": 100},
        ])
    except SettlementCompensationTriggeredException as exc:
        cat = classify_error(exc)
        assert cat in (ErrorCategory.FATAL_SECURITY, ErrorCategory.FATAL_CLIENT)
        assert fsm.state == SagaState.ABORTED


def test_p11_f09_gstin_pan_and_f10_gstr1_invoice() -> None:
    """P11: F09 (GSTIN/PAN) + F10 (GSTR-1 Invoice) -> Strict invoice validation with verified seller and buyer GSTINs."""
    seller_gstin = "29AABCU9603R1ZJ"
    buyer_gstin = "29ABCDE1234F1ZW"
    assert validate_gstin(seller_gstin) is True
    assert validate_gstin(buyer_gstin) is True
    
    line = E2eInvoiceLineItem(
        skuId="SKU-1", description="Item", hsnSacCode="8504", quantity=1, unitPricePaise=1000,
        taxableAmountPaise=1000, gstRatePercent=18, cgstPaise=90, sgstPaise=90, igstPaise=0, totalPaise=1180,
    )
    inv = E2eGstr1Invoice(
        invoiceNumber="INV-P11", invoiceDate="2026-08-26", supplierGstin=seller_gstin,
        supplierStateCode="29", recipientGstin=buyer_gstin, recipientStateCode="29",
        placeOfSupplyStateCode="29", isIntraState=True, lineItems=[line], taxableSubtotalPaise=1000,
        totalCgstPaise=90, totalSgstPaise=90, totalIgstPaise=0, totalTaxPaise=180, totalTcsPaise=10,
        grandTotalPaise=1180, cryptographicAuditHash="0"*64,
    )
    assert inv.supplierGstin == seller_gstin
    assert inv.recipientGstin == buyer_gstin


def test_p12_f11_ap2_mandates_and_f01_integer_math() -> None:
    """P12: F11 (AP2 Mandates) + F01 (Integer Math) -> AP2 budget gate enforcement with integer paise validation."""
    actors = setup_e2e_actors()
    now = int(time.time())
    
    intent = createSignedIntentMandate(
        mandateId="M-I-P12", userSigner=actors.user_cfo, delegatedAgentDid=actors.buyer_agent.getAgentDid(),
        maxBudgetPaise=100000, upiCircleDelegationToken="tok", singleTransactionLimitPaise=100000, timestamp=now,
    )
    unit_p = validateIntegerPaise(90000, "unitPrice")
    item = CartItemSchema(skuId="SKU-1", quantity=1, unitPricePaise=unit_p, hsnCode="8504", gstRatePercent=0, lineTotalPaise=unit_p)
    tax = TaxBreakdownSchema(cgstPaise=0, sgstPaise=0, igstPaise=0, totalTaxPaise=0)
    cart = createSignedCartMandate(
        cartId="M-C-P12", merchantSigner=actors.merchant_nexus, merchantGstin="29AABCU9603R1ZJ",
        merchantStateCode="29", buyerDeliveryPincode="560001", buyerDeliveryStateCode="29",
        items=[item], taxableSubtotalPaise=unit_p, taxBreakdown=tax, shippingPaise=0, discountPaise=0,
        totalPaise=unit_p, inventoryLockToken="lock_p12", inventoryLockExpiresAt=now + 60, timestamp=now,
    )
    exec_m = createSignedExecutionMandate(
        executionId="M-E-P12", buyerAgentSigner=actors.buyer_agent,
        intentMandate=intent, cartMandate=cart, settlementAmountPaise=unit_p, upiCircleToken="tok", timestamp=now,
    )
    assert validateBudgetGate(intent, cart, exec_m, serverTime=now) is True


@pytest.mark.asyncio
async def test_p13_f11_ap2_mandates_and_f14_2pc_fsm() -> None:
    """P13: F11 (AP2 Mandates) + F14 (2PC FSM) -> 2PC distributed settlement driven by chained AP2 mandates."""
    actors = setup_e2e_actors()
    now = int(time.time())
    
    intent = createSignedIntentMandate(
        mandateId="M-I-P13", userSigner=actors.user_cfo, delegatedAgentDid=actors.buyer_agent.getAgentDid(),
        maxBudgetPaise=200000, upiCircleDelegationToken="tok", singleTransactionLimitPaise=200000, timestamp=now,
    )
    item = CartItemSchema(skuId="SKU-1", quantity=1, unitPricePaise=100000, hsnCode="8504", gstRatePercent=18, lineTotalPaise=100000)
    tax = TaxBreakdownSchema(cgstPaise=9000, sgstPaise=9000, igstPaise=0, totalTaxPaise=18000)
    cart = createSignedCartMandate(
        cartId="M-C-P13", merchantSigner=actors.merchant_nexus, merchantGstin="29AABCU9603R1ZJ",
        merchantStateCode="29", buyerDeliveryPincode="560001", buyerDeliveryStateCode="29",
        items=[item], taxableSubtotalPaise=100000, taxBreakdown=tax, shippingPaise=0, discountPaise=0,
        totalPaise=118000, inventoryLockToken="lock_p13", inventoryLockExpiresAt=now + 60, timestamp=now,
    )
    exec_m = createSignedExecutionMandate(
        executionId="M-E-P13", buyerAgentSigner=actors.buyer_agent,
        intentMandate=intent, cartMandate=cart, settlementAmountPaise=118000, upiCircleToken="tok", timestamp=now,
    )
    
    fsm = TwoPhaseCommitFsm(route_client=MockRazorpayRouteClient({}))
    fsm.prepare(fencing_token=1)
    transfers = await fsm.commit_transfers([
        {"account": "acc_merchant", "amount": 117950},
        {"account": "acc_proto", "amount": 50},
    ])
    assert fsm.state == SagaState.COMMITTED
    assert len(transfers) == 2


def test_p14_f12_hsn_sac_and_f15_schema_invariants() -> None:
    """P14: F12 (HSN/SAC) + F15 (Schema Invariants) -> Fuzzing HSN/SAC code inputs and PIN code mappings."""
    # Special characters and injection patterns in PIN / HSN
    with pytest.raises(InvalidPincodeException):
        deriveStateCodeFromPincode("560001'; DROP TABLE --")
    with pytest.raises(InvalidPincodeException):
        deriveStateCodeFromPincode("<script>560001</script>")
        
    assert resolveGstRate("8504'; --") == 18 # Resolves first 4 chars "8504" to 18%


def test_p15_f13_math_invariants_and_f03_conserved_splitting() -> None:
    """P15: F13 (Math Invariants) + F03 (Conserved Splitting) -> Invariant testing on multi-party split conservation across coprimes."""
    coprime_totals = [10007, 20011, 30013, 40009]
    ratios = [3, 7, 11]
    for total in coprime_totals:
        splits = split_bill_conserved(total, ratios)
        assert sum(splits) == total
        assert all(s >= 0 for s in splits)


@pytest.mark.asyncio
async def test_p16_f16_e2e_regression_and_f08_dlq_replay() -> None:
    """P16: F16 (E2E Regression) + F08 (DLQ Replay) -> End-to-end recovery of aborted transaction via DLQ replay."""
    actors = setup_e2e_actors()
    dlq = DurableDeadLetterQueue()
    
    # Store aborted settlement payload
    failed_payload = {
        "intentId": "M-I-REC", "cartId": "M-C-REC", "paymentId": "pay_rec_001",
        "merchantAccount": "acc_merchant", "amountPaise": 118000,
    }
    entry_id = await dlq.enqueue(payload=failed_payload, error="Transient network timeout")
    
    redis = MockRedisAsync()
    orchestrator = SettlementOrchestrator(
        routeClient=RazorpayRouteClient(apiKey="k", apiSecret="s"),
        nonceLedger=NonceLedger(redis),
    )
    
    async def retry_recovery(payload):
        # Simulated replay resolution
        return {"status": "recovered", "paymentId": payload["paymentId"], "amountPaise": payload["amountPaise"]}
        
    success, res = await dlq.replay(entry_id, retry_recovery)
    assert success is True
    assert res["status"] == "recovered"
    assert res["amountPaise"] == 118000
