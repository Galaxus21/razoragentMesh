"""Tier 4: Real-World Benchmark Workload Scenarios Test Suite (Scenarios S01 - S10 = 10 tests).

Covers end-to-end multi-agent financial flows, fault injections, and recovery lifecycles.
"""

import asyncio
import time
from typing import Any, Dict, List, Tuple
import pytest

from razoragentMesh.packages.catalogSanitizer.catalogSanitizer import (
    sanitizeMerchantSkuQuote,
)
from razoragentMesh.packages.mandateEngine.crypto.cryptoKeyUtils import (
    extractPublicKeyFromDid,
    generateKeyPair,
)
from razoragentMesh.packages.mandateEngine.crypto.ed25519Signer import Ed25519Signer
from razoragentMesh.packages.mandateEngine.crypto.ed25519Verifier import Ed25519Verifier
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
    createSignedAmendmentMandate,
    createSignedCartMandate,
    createSignedExecutionMandate,
    createSignedIntentMandate,
    verifyMandateChain,
    verifyMandateHashChain,
)
from razoragentMesh.packages.mandateEngine.nonce.nonceLedger import NonceLedger
from razoragentMesh.packages.mandateEngine.settlement.razorpayRouteClient import (
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
# SCENARIO S01: Autonomous B2B Hardware Purchase with Inter-State IGST
# =============================================================================

@pytest.mark.asyncio
async def test_s01_autonomous_b2b_hardware_purchase_inter_state() -> None:
    """S01: Autonomous B2B Hardware Purchase — Inter-State IGST (Maharashtra 27 -> Karnataka 29) with Mandate Chain."""
    actors = setup_e2e_actors()
    now = int(time.time())
    
    # 1. User CFO creates Intent Mandate (M_I) with ₹50,000 spend limit
    max_budget_paise = 5000000
    intent = createSignedIntentMandate(
        mandateId="M-I-S01", userSigner=actors.user_cfo, delegatedAgentDid=actors.buyer_agent.getAgentDid(),
        maxBudgetPaise=max_budget_paise, upiCircleDelegationToken="upi_tok_b2b", singleTransactionLimitPaise=max_budget_paise,
        authorizedCategories=["industrial_hardware"], timestamp=now,
    )
    
    # 2. Merchant in Maharashtra (27) quotes hardware items for delivery to Karnataka (29) -> Inter-state
    unit_price = 3500000 # ₹35,000
    taxable = computeLineItemTotal(unit_price, 1)
    gst = computeGstBreakdown(taxable, 18, isIntraState=False)
    assert gst.igstPaise == 630000 and gst.cgstPaise == 0 and gst.sgstPaise == 0
    total_paise = computeCartSettlementTotal(taxable, gst.totalTaxPaise, shippingPaise=10000, discountPaise=0)
    assert total_paise == 4140000

    item = CartItemSchema(skuId="SKU-B2B-01", quantity=1, unitPricePaise=unit_price, hsnCode="8471", gstRatePercent=18, lineTotalPaise=taxable, category="industrial_hardware")
    tax_breakdown = TaxBreakdownSchema(cgstPaise=0, sgstPaise=0, igstPaise=gst.igstPaise, totalTaxPaise=gst.totalTaxPaise)
    
    cart = createSignedCartMandate(
        cartId="M-C-S01", merchantSigner=actors.merchant_nexus, merchantGstin="27ABCDE1234F1Z0",
        merchantStateCode="27", buyerDeliveryPincode="560001", buyerDeliveryStateCode="29",
        items=[item], taxableSubtotalPaise=taxable, taxBreakdown=tax_breakdown, shippingPaise=10000, discountPaise=0,
        totalPaise=total_paise, inventoryLockToken="lock_s01", inventoryLockExpiresAt=now + 60, timestamp=now,
    )
    
    # 3. Buyer Agent signs Execution Mandate (M_E)
    exec_m = createSignedExecutionMandate(
        executionId="M-E-S01", buyerAgentSigner=actors.buyer_agent,
        intentMandate=intent, cartMandate=cart, settlementAmountPaise=total_paise, upiCircleToken="upi_tok_b2b", timestamp=now,
    )
    
    # 4. Invariant Verification
    assert verifyMandateHashChain(intent, cart, exec_m) is True
    assert validateBudgetGate(
        intent, cart, exec_m, serverTime=now,
        skuCategories=[cart_item.category for cart_item in cart.items],
    ) is True
    
    # 5. Settlement Execution & GSTR-1 Generation
    redis = MockRedisAsync()
    orchestrator = SettlementOrchestrator(
        routeClient=RazorpayRouteClient(apiKey="k", apiSecret="s"),
        nonceLedger=NonceLedger(redis),
    )
    res = await orchestrator.executeSettlementSaga(
        intentMandate=intent, cartMandate=cart, executionMandate=exec_m,
        merchantAccount="acc_merchant_nexus_01", paymentId="pay_s01", serverTime=now,
    )
    assert res.status == "captured"
    assert res.amountPaise == total_paise
    assert res.invoice.isIntraState is False
    assert res.invoice.totalIgstPaise == 630000

# =============================================================================
# SCENARIO S02: Multi-Merchant Cart with Conserved Remainder Bill Splitting
# =============================================================================

@pytest.mark.asyncio
async def test_s02_multi_merchant_cart_conserved_bill_splitting() -> None:
    """S02: Multi-Merchant Cart — Conserved 3-way split with platform fee deductions and zero penny loss."""
    total_order_paise = 15000000  # ₹1,50,000
    ratios = [5, 3, 2] # 50% merchant A, 30% merchant B, 20% merchant C
    
    splits = split_bill_conserved(total_order_paise, ratios)
    assert splits == [7500000, 4500000, 3000000]
    assert sum(splits) == total_order_paise
    
    # Apply platform fee deductions to each merchant share
    fee_a = calculate_route_splits(order_paise=splits[0], commission_bps=200, flat_fee_paise=50) # 2% + 50p
    fee_b = calculate_route_splits(order_paise=splits[1], commission_bps=250, flat_fee_paise=50) # 2.5% + 50p
    fee_c = calculate_route_splits(order_paise=splits[2], commission_bps=300, flat_fee_paise=50) # 3% + 50p
    
    total_net_payout = fee_a.merchant_net_paise + fee_b.merchant_net_paise + fee_c.merchant_net_paise
    total_platform_commission = fee_a.total_fee_paise + fee_b.total_fee_paise + fee_c.total_fee_paise
    assert total_net_payout + total_platform_commission == total_order_paise

# =============================================================================
# SCENARIO S03: Transient Payment Gateway 504 Timeout Recovery
# =============================================================================

@pytest.mark.asyncio
async def test_s03_transient_gateway_504_timeout_recovery_backoff() -> None:
    """S03: Transient Payment Gateway 504 Timeout — Backoff retry simulation and DLQ resolution."""
    dlq = DurableDeadLetterQueue()
    payload = {"paymentId": "pay_timeout_001", "amountPaise": 500000, "merchantAccount": "acc_merchant"}
    
    # Enqueue failed request
    entry_id = await dlq.enqueue(
        payload=payload, error="HTTP 504 Gateway Timeout: Razorpay Route unreachable",
        category=ErrorCategory.TRANSIENT_NETWORK, idempotency_key="idem_pay_timeout_001",
    )
    record = await dlq.peek(entry_id)
    assert record is not None and record.errorCategory == ErrorCategory.TRANSIENT_NETWORK
    
    # Calculate exponential backoff delays
    delays = [compute_backoff_delay(attempt=i, base_delay=0.5, max_delay=5.0) for i in range(3)]
    assert all(0.0 <= d <= 5.0 for d in delays)
    
    # Simulate successful replay after gateway recovers
    async def recover_payment(p):
        return {"status": "captured", "paymentId": p["paymentId"], "settled": True}
        
    success, res = await dlq.replay(entry_id, recover_payment)
    assert success is True
    assert res["status"] == "captured"
    updated_rec = await dlq.peek(entry_id)
    assert updated_rec is not None and updated_rec.status == DlqEntryStatus.REPLAYED

# =============================================================================
# SCENARIO S04: Poison Pill Webhook Handling and DLQ Isolation
# =============================================================================

@pytest.mark.asyncio
async def test_s04_poison_pill_webhook_dlq_isolation() -> None:
    """S04: Poison Pill Webhook Handling — Corrupted webhook isolated into DLQ without disrupting system."""
    dlq = DurableDeadLetterQueue()
    poison_payload = {"rawBody": "{malformed_json_without_quotes: true, invalid...", "headers": {"sig": "bad"}}
    
    entry_id = await dlq.enqueue(
        payload=poison_payload, error="JSONDecodeError: Expecting property name enclosed in double quotes",
        category=ErrorCategory.POISON_PILL,
    )
    rec = await dlq.peek(entry_id)
    assert rec is not None
    assert rec.errorCategory == ErrorCategory.POISON_PILL
    assert is_retryable(rec.errorCategory) is False  # Poison pills should not be blindly auto-retried

# =============================================================================
# SCENARIO S05: Out-of-Stock Vector Healing with Dynamic Price Recomputation
# =============================================================================

def test_s05_out_of_stock_vector_healing_with_amendment() -> None:
    """S05: Out-of-Stock Vector Healing — Vector similarity substitution and dual-signed Amendment Mandate (M_A)."""
    actors = setup_e2e_actors()
    now = int(time.time())
    
    # 1. Original cart with out-of-stock SKU-A (₹1,000)
    orig_price = 100000
    orig_item = CartItemSchema(skuId="SKU-OOS-A", quantity=1, unitPricePaise=orig_price, hsnCode="8504", gstRatePercent=18, lineTotalPaise=orig_price)
    orig_tax = TaxBreakdownSchema(cgstPaise=9000, sgstPaise=9000, igstPaise=0, totalTaxPaise=18000)
    orig_cart = createSignedCartMandate(
        cartId="M-C-S05-ORIG", merchantSigner=actors.merchant_nexus, merchantGstin="29AABCU9603R1ZJ",
        merchantStateCode="29", buyerDeliveryPincode="560001", buyerDeliveryStateCode="29",
        items=[orig_item], taxableSubtotalPaise=orig_price, taxBreakdown=orig_tax, shippingPaise=0, discountPaise=0,
        totalPaise=118000, inventoryLockToken="lock_orig", inventoryLockExpiresAt=now + 60, timestamp=now,
    )
    
    # 2. Vector search finds substitute SKU-B at ₹1,030 (+3.0% price delta <= 5.0% cap)
    sub_price = 103000
    sub_item = CartItemSchema(skuId="SKU-SUB-B", quantity=1, unitPricePaise=sub_price, hsnCode="8504", gstRatePercent=18, lineTotalPaise=sub_price)
    sub_tax = TaxBreakdownSchema(cgstPaise=9270, sgstPaise=9270, igstPaise=0, totalTaxPaise=18540)
    healed_cart = createSignedCartMandate(
        cartId="M-C-S05-HEALED", merchantSigner=actors.merchant_nexus, merchantGstin="29AABCU9603R1ZJ",
        merchantStateCode="29", buyerDeliveryPincode="560001", buyerDeliveryStateCode="29",
        items=[sub_item], taxableSubtotalPaise=sub_price, taxBreakdown=sub_tax, shippingPaise=0, discountPaise=0,
        totalPaise=121540, inventoryLockToken="lock_healed", inventoryLockExpiresAt=now + 60, timestamp=now,
    )
    
    # 3. Emit dual-signed AmendmentMandate (M_A)
    amendment = createSignedAmendmentMandate(
        amendmentId="M-A-S05", buyerAgentSigner=actors.buyer_agent, merchantSigner=actors.merchant_nexus,
        previousCartMandate=orig_cart, newCartMandate=healed_cart, substitutedSkuMapping={"SKU-OOS-A": "SKU-SUB-B"},
        priceDeltaPaise=3000, amendmentReason="OOS inventory vector substitute", timestamp=now,
    )
    assert amendment.priceDeltaPaise == 3000
    assert amendment.substitutedSkuMapping["SKU-OOS-A"] == "SKU-SUB-B"
    assert amendment.previousCartMandateHash == computeMandateHash(orig_cart)
    assert amendment.newCartMandateHash == computeMandateHash(healed_cart)

# =============================================================================
# SCENARIO S06: Concurrent Double-Spend Prevention with Distributed Locking
# =============================================================================

@pytest.mark.asyncio
async def test_s06_concurrent_double_spend_prevention() -> None:
    """S06: Concurrent Double-Spend Prevention — 10 agents race for 2 units of stock with Redis Lua fencing."""
    redis = MockRedisAsync()
    stock_key = "sku:SKU-LIMITED:stock"
    fence_key = "sku:SKU-LIMITED:fence"
    await redis.set(stock_key, 2)  # Exactly 2 units available
    
    async def agent_attempt_lock(agent_idx: int):
        lock_token = f"token_agent_{agent_idx}"
        res = await redis.eval("", 2, stock_key, fence_key, 1, lock_token, 60)
        return res[0], res[1]  # status, fencing_counter
        
    results = await asyncio.gather(*[agent_attempt_lock(i) for i in range(10)])
    successful_locks = [r for r in results if r[0] == 1]
    rejected_locks = [r for r in results if r[0] == -1]
    
    # Exactly 2 agents secure the locks; 8 are safely rejected
    assert len(successful_locks) == 2
    assert len(rejected_locks) == 8
    final_stock = int(await redis.get(stock_key) or 0)
    assert final_stock == 0  # Zero over-allocation

# =============================================================================
# SCENARIO S07: 2PC Saga Distributed Rollback under Route Transfer Rejection
# =============================================================================

@pytest.mark.asyncio
async def test_s07_2pc_saga_rollback_under_route_rejection() -> None:
    """S07: 2PC Saga Distributed Rollback — Secondary transfer rejection triggers complete LIFO compensation."""
    mock_route = MockRazorpayRouteClient({})
    mock_route.simulateSecondaryTransferFailure = True
    fsm = TwoPhaseCommitFsm(route_client=mock_route)
    fsm.prepare(fencing_token=1)
    
    requests = [
        {"account": "acc_merchant_prime", "amount": 100000},
        {"account": "acc_logistics_partner", "amount": 5000},
    ]
    with pytest.raises(SettlementCompensationTriggeredException) as exc_info:
        await fsm.commit_transfers(requests)
        
    assert fsm.state == SagaState.ABORTED
    assert len(fsm.reversed_transfers) == 1
    assert "2PC Commit failed" in str(exc_info.value)

# =============================================================================
# SCENARIO S08: Malformed GSTIN / PAN Injection Attack Defense
# =============================================================================

def test_s08_malformed_gstin_pan_injection_defense() -> None:
    """S08: Malformed GSTIN / PAN Injection Attack Defense — Injection strings intercepted and rejected."""
    malicious_inputs = [
        "29AABCU9603R1ZM' OR '1'='1",
        "29AABCU9603R1ZM<script>alert(1)</script>",
        "00AABCU9603R1ZM",  # Unallocated state 00
        "29AABCU9603R1Z",   # 14 chars
        "AABCU9603R; DROP TABLE merchants;--",
    ]
    for bad_gstin in malicious_inputs:
        assert validate_gstin(bad_gstin) is False

# =============================================================================
# SCENARIO S09: Multi-Party AP2 Mandate Chain Execution
# =============================================================================

def test_s09_multi_party_ap2_mandate_chain_execution() -> None:
    """S09: Multi-Party AP2 Mandate Chain — Full M_I -> M_C -> M_E -> M_A cryptographic chain execution."""
    actors = setup_e2e_actors()
    now = int(time.time())
    
    # 1. Intent Mandate
    intent = createSignedIntentMandate(
        mandateId="M-I-S09", userSigner=actors.user_cfo, delegatedAgentDid=actors.buyer_agent.getAgentDid(),
        maxBudgetPaise=1000000, upiCircleDelegationToken="tok", singleTransactionLimitPaise=1000000, timestamp=now,
    )
    # 2. Cart Mandate
    item = CartItemSchema(skuId="SKU-1", quantity=1, unitPricePaise=500000, hsnCode="8504", gstRatePercent=18, lineTotalPaise=500000)
    tax = TaxBreakdownSchema(cgstPaise=45000, sgstPaise=45000, igstPaise=0, totalTaxPaise=90000)
    cart = createSignedCartMandate(
        cartId="M-C-S09", merchantSigner=actors.merchant_nexus, merchantGstin="29AABCU9603R1ZJ",
        merchantStateCode="29", buyerDeliveryPincode="560001", buyerDeliveryStateCode="29",
        items=[item], taxableSubtotalPaise=500000, taxBreakdown=tax, shippingPaise=0, discountPaise=0,
        totalPaise=590000, inventoryLockToken="lock_s09", inventoryLockExpiresAt=now + 60, timestamp=now,
    )
    # 3. Execution Mandate
    exec_m = createSignedExecutionMandate(
        executionId="M-E-S09", buyerAgentSigner=actors.buyer_agent,
        intentMandate=intent, cartMandate=cart, settlementAmountPaise=590000, upiCircleToken="tok", timestamp=now,
    )
    
    assert verifyMandateHashChain(intent, cart, exec_m) is True
    assert verifyMandateChain(intent, cart, exec_m) is True

# =============================================================================
# SCENARIO S10: End-to-End Autonomous Commerce Settlement with Audit Trail
# =============================================================================

@pytest.mark.asyncio
async def test_s10_end_to_end_autonomous_commerce_settlement_audit_trail() -> None:
    """S10: Capstone Mega-Scenario — Full F01-F16 lifecycle from prompt sanitization to 2PC capture and GSTR-1 audit trail."""
    actors = setup_e2e_actors()
    now = int(time.time())
    
    # 1. Ingress catalog quote sanitization (strips zero-width chars and HTML)
    raw_quote = {
        "skuId": "SKU-CAPSTONE-01",
        "title": "Industrial Controller Node\u200B",
        "description": "High integrity node <script>alert(1)</script>",
        "availableStock": 20,
        "baseUnitPricePaise": 500000,
        "offeredUnitPricePaise": 500000,
        "currency": "INR",
        "hsnCode": "8504",
        "gstRatePercent": 18,
        "taxBreakdown": {"cgstPaise": 45000, "sgstPaise": 45000, "igstPaise": 0, "totalTaxPaise": 90000},
        "quoteExpiryTimestamp": now + 300,
        "quoteHash": "0"*64,
    }
    sanitized = sanitizeMerchantSkuQuote(raw_quote)
    assert "\u200b" not in sanitized.title
    assert "<script>" not in sanitized.description
    
    # 2. Redis atomic inventory reservation
    redis = MockRedisAsync()
    stock_key = f"sku:{sanitized.skuId}:stock"
    fence_key = f"sku:{sanitized.skuId}:fence"
    await redis.set(stock_key, 20)
    lock_status, fence_token = await redis.eval("", 2, stock_key, fence_key, 1, "lock_capstone", 60)
    assert lock_status == 1 and fence_token >= 1
    
    # 3. AP2 Mandate Chain construction
    intent = createSignedIntentMandate(
        mandateId="M-I-S10", userSigner=actors.user_cfo, delegatedAgentDid=actors.buyer_agent.getAgentDid(),
        maxBudgetPaise=1000000, upiCircleDelegationToken="upi_tok_s10", singleTransactionLimitPaise=1000000,
        authorizedCategories=["industrial_electronics"], timestamp=now,
    )
    item = CartItemSchema(
        skuId=sanitized.skuId, quantity=1, unitPricePaise=sanitized.offeredUnitPricePaise,
        hsnCode=sanitized.hsnCode, gstRatePercent=sanitized.gstRatePercent, lineTotalPaise=sanitized.offeredUnitPricePaise,
        category="industrial_electronics",
    )
    tax_breakdown = TaxBreakdownSchema(cgstPaise=45000, sgstPaise=45000, igstPaise=0, totalTaxPaise=90000)
    cart = createSignedCartMandate(
        cartId="M-C-S10", merchantSigner=actors.merchant_nexus, merchantGstin="29AABCU9603R1ZJ",
        merchantStateCode="29", buyerDeliveryPincode="560001", buyerDeliveryStateCode="29",
        items=[item], taxableSubtotalPaise=500000, taxBreakdown=tax_breakdown, shippingPaise=0, discountPaise=0,
        totalPaise=590000, inventoryLockToken="lock_capstone", inventoryLockExpiresAt=now + 60, timestamp=now,
    )
    exec_m = createSignedExecutionMandate(
        executionId="M-E-S10", buyerAgentSigner=actors.buyer_agent,
        intentMandate=intent, cartMandate=cart, settlementAmountPaise=590000, upiCircleToken="upi_tok_s10",
        timestamp=now,
    )
    
    # 4. Execute 2PC Settlement Saga
    orchestrator = SettlementOrchestrator(
        routeClient=RazorpayRouteClient(apiKey="k", apiSecret="s"),
        nonceLedger=NonceLedger(redis),
    )
    result = await orchestrator.executeSettlementSaga(
        intentMandate=intent, cartMandate=cart, executionMandate=exec_m,
        merchantAccount="acc_merchant_nexus_01", paymentId="pay_capstone_001", serverTime=now,
    )
    
    # 5. Assertions across all architecture layers
    assert result.status == "captured"
    assert result.amountPaise == 590000
    assert len(result.transfers) >= 1
    assert result.invoice.invoiceNumber.startswith("INV-")
    assert len(result.invoice.cryptographicAuditHash) == 64
    assert result.invoice.grandTotalPaise == 590000
    
    # 6. DLQ health verification (0 pending errors)
    dlq = DurableDeadLetterQueue(redis_client=redis)
    assert len(dlq.list_entries(status=DlqEntryStatus.PENDING)) == 0
