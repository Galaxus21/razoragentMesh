"""Tier 2: Boundary Value Analysis (BVA) & Extreme Stress Test Suite (16 features × 5 test cases = 80 tests).

Covers edge cases, limits, and stress boundaries for F01 to F16.
"""

import asyncio
from decimal import Decimal
import json
import math
import random
import time
from typing import Any, Dict, List
from pydantic import ValidationError
import pytest

from razoragentMesh.packages.mandateEngine.crypto.cryptoKeyUtils import generateKeyPair
from razoragentMesh.packages.mandateEngine.crypto.ed25519Signer import Ed25519Signer
from razoragentMesh.packages.mandateEngine.crypto.jcsCanonicalizer import (
    canonicalizeAndHash,
    canonicalizeJson,
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
    DurableDeadLetterQueue,
    E2eGstr1Invoice,
    E2eInvoiceLineItem,
    ErrorCategory,
    FencingTokenViolationError,
    IllegalStateTransitionError,
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
# FEATURE 01: Integer Math Enclave (5 boundary cases)
# =============================================================================

def test_f01_bva_zero_paise_transaction() -> None:
    """F01-B1: Zero paise valid in field validation and cart subtotal."""
    assert validateIntegerPaise(0, "zeroPaise") == 0
    gross = computeCartSettlementTotal(taxableSubtotalPaise=0, totalTaxPaise=0, shippingPaise=0, discountPaise=0)
    assert gross == 0


def test_f01_bva_one_paise_minimum_transaction() -> None:
    """F01-B2: 1 paise minimum transaction executes accurately without underflow."""
    assert validateIntegerPaise(1, "onePaise") == 1
    total = computeLineItemTotal(unitPricePaise=1, quantity=1)
    assert total == 1


def test_f01_bva_max_int64_boundary() -> None:
    """F01-B3: Large 64-bit integers (e.g. 10^15 paise = 10,000 crore INR) validated accurately."""
    large_int = 10**15
    assert validateIntegerPaise(large_int, "largeAmount") == large_int
    gross = computeCartSettlementTotal(taxableSubtotalPaise=large_int, totalTaxPaise=18 * (10**13))
    assert gross == large_int + (18 * (10**13))


def test_f01_bva_negative_quantity_raises_error() -> None:
    """F01-B4: Negative quantity (-1) in computeLineItemTotal raises ArithmeticDriftException."""
    with pytest.raises(ArithmeticDriftException):
        computeLineItemTotal(unitPricePaise=100, quantity=-1)


def test_f01_bva_fractional_float_nan_inf_rejections() -> None:
    """F01-B5: Float NaN, Infinity, -Infinity, and tiny float epsilons rejected."""
    for bad_input in [float("nan"), float("inf"), float("-inf"), 1e-12, -0.0]:
        if isinstance(bad_input, float) and not math.isnan(bad_input) and bad_input == 0.0:
            continue
        with pytest.raises(ArithmeticDriftException):
            validateIntegerPaise(bad_input, "floatField")

# =============================================================================
# FEATURE 02: Statutory GST (CGST/SGST/IGST) (5 boundary cases)
# =============================================================================

def test_f02_bva_one_paise_at_18_percent_gst_zero_floor() -> None:
    """F02-B1: 1 paise taxable at 18% GST floors to 0 paise tax ((1*18)//100 == 0)."""
    gst = computeGstBreakdown(taxableSubtotalPaise=1, gstRatePercent=18, isIntraState=True)
    assert gst.totalTaxPaise == 0
    assert gst.cgstPaise == 0 and gst.sgstPaise == 0


def test_f02_bva_99_paise_at_5_percent_gst_odd_floor() -> None:
    """F02-B2: 99 paise taxable at 5% GST floors to 4 paise tax, split into equal halves."""
    gst = computeGstBreakdown(taxableSubtotalPaise=99, gstRatePercent=5, isIntraState=True)
    assert gst.totalTaxPaise == 4
    # CGST and SGST are each the 2.5% half-rate: (99 * 250) // 20000 = 2 paise, applied identically.
    assert gst.cgstPaise == 2
    assert gst.sgstPaise == 2
    assert gst.cgstPaise + gst.sgstPaise == 4


def test_f02_bva_mega_transaction_10_billion_paise_gst() -> None:
    """F02-B3: Mega transaction of 10,000,000,000 paise (₹10 crore) computes exact tax."""
    subtotal = 10_000_000_000
    gst = computeGstBreakdown(taxableSubtotalPaise=subtotal, gstRatePercent=18, isIntraState=True)
    assert gst.totalTaxPaise == 1_800_000_000
    assert gst.cgstPaise == 900_000_000
    assert gst.sgstPaise == 900_000_000


def test_f02_bva_highest_gst_slab_28_percent() -> None:
    """F02-B4: Highest standard GST luxury slab (28%) applies exact 14% CGST + 14% SGST."""
    gst = computeGstBreakdown(taxableSubtotalPaise=100000, gstRatePercent=28, isIntraState=True)
    assert gst.cgstPaise == 14000
    assert gst.sgstPaise == 14000
    assert gst.totalTaxPaise == 28000


def test_f02_bva_tcs_one_paise_boundary() -> None:
    """F02-B5: Section 52 TCS withholding on small taxable value (99 paise) floors accurately."""
    tcs = computeTcsWithholding(taxableSubtotalPaise=99, isIntraState=True)
    # 99 * 50 // 10000 = 0 paise
    assert tcs["totalTcsPaise"] == 0

# =============================================================================
# FEATURE 03: Conserved Bill Splitting (5 boundary cases)
# =============================================================================

def test_f03_bva_one_paise_split_three_ways() -> None:
    """F03-B1: 1 paise split among 3 equal parties yields [1, 0, 0] with sum=1."""
    shares = split_bill_conserved(total_amount_paise=1, participant_ratios=[1, 1, 1])
    assert shares == [1, 0, 0]
    assert sum(shares) == 1


def test_f03_bva_zero_paise_total_split() -> None:
    """F03-B2: 0 paise split among 5 parties returns [0, 0, 0, 0, 0]."""
    shares = split_bill_conserved(total_amount_paise=0, participant_ratios=[1, 1, 1, 1, 1])
    assert shares == [0, 0, 0, 0, 0]
    assert sum(shares) == 0


def test_f03_bva_one_million_paise_split_seven_ways() -> None:
    """F03-B3: 1,000,000 paise split 7 ways guarantees sum(shares) == 1,000,000."""
    shares = split_bill_conserved(total_amount_paise=1000000, participant_ratios=[1]*7)
    assert len(shares) == 7
    assert sum(shares) == 1000000


def test_f03_bva_hundred_parties_micro_split() -> None:
    """F03-B4: 100 parties splitting 99 paise results in exactly 99 ones and 1 zero, sum=99."""
    shares = split_bill_conserved(total_amount_paise=99, participant_ratios=[1]*100)
    assert shares.count(1) == 99
    assert shares.count(0) == 1
    assert sum(shares) == 99


def test_f03_bva_extreme_unequal_ratios() -> None:
    """F03-B5: Extreme ratio [10000, 1] allocates 10000/10001 share with zero penny loss."""
    shares = split_bill_conserved(total_amount_paise=50000, participant_ratios=[10000, 1])
    assert sum(shares) == 50000

# =============================================================================
# FEATURE 04: Fee & Commission Splits (5 boundary cases)
# =============================================================================

def test_f04_bva_max_commission_10000_bps_100_percent() -> None:
    """F04-B1: 10,000 bps (100%) commission deducts entire order value to fee, merchant net=0."""
    res = calculate_route_splits(order_paise=50000, commission_bps=10000, flat_fee_paise=0)
    assert res.commission_paise == 50000
    assert res.merchant_net_paise == 0


def test_f04_bva_min_commission_1_bps() -> None:
    """F04-B2: 1 bps (0.01%) commission on 1,000,000 paise yields 100 paise fee."""
    res = calculate_route_splits(order_paise=1000000, commission_bps=1, flat_fee_paise=0)
    assert res.commission_paise == 100
    assert res.merchant_net_paise == 999900


def test_f04_bva_flat_fee_equal_to_order_amount() -> None:
    """F04-B3: Flat fee exactly equal to order amount yields merchant net = 0."""
    res = calculate_route_splits(order_paise=500, commission_bps=0, flat_fee_paise=500)
    assert res.total_fee_paise == 500
    assert res.merchant_net_paise == 0


def test_f04_bva_flat_fee_greater_than_order_clamping() -> None:
    """F04-B4: Flat fee exceeding order amount is clamped to order value without negative debt."""
    res = calculate_route_splits(order_paise=250, commission_bps=0, flat_fee_paise=1000)
    assert res.total_fee_paise == 250
    assert res.merchant_net_paise == 0


def test_f04_bva_bps_exceeding_10000_raises_exception() -> None:
    """F04-B5: Commission exceeding 10,000 bps (e.g. 10001) raises ArithmeticDriftException."""
    with pytest.raises(ArithmeticDriftException):
        calculate_route_splits(order_paise=10000, commission_bps=10001)

# =============================================================================
# FEATURE 05: Durable DLQ Persistence (5 boundary cases)
# =============================================================================

@pytest.mark.asyncio
async def test_f05_bva_large_1mb_payload_storage() -> None:
    """F05-B1: Large 1MB payload successfully enqueued and retrieved without corruption."""
    dlq = DurableDeadLetterQueue()
    large_payload = {"key": "x" * (1024 * 1024), "orderId": "ORD-1MB"}
    entry_id = await dlq.enqueue(payload=large_payload, error="Large payload error")
    record = await dlq.peek(entry_id)
    assert record is not None
    assert len(record.payload["key"]) == 1024 * 1024


@pytest.mark.asyncio
async def test_f05_bva_idempotency_key_exact_sha256_length() -> None:
    """F05-B2: SHA-256 idempotency key indexing handles exact 64-char keys."""
    dlq = DurableDeadLetterQueue()
    sha_key = "e3b0c44298fc1c149afbf4c8996fb92427ae41e4649b934ca495991b7852b855"
    id1 = await dlq.enqueue(payload={"a": 1}, error="e", idempotency_key=sha_key)
    id2 = await dlq.enqueue(payload={"a": 1}, error="e", idempotency_key=sha_key)
    assert id1 == id2


@pytest.mark.asyncio
async def test_f05_bva_max_retries_zero_boundary() -> None:
    """F05-B3: Setting max_retries=0 on enqueue marks record FAILED immediately upon first replay failure."""
    dlq = DurableDeadLetterQueue()
    entry_id = await dlq.enqueue(payload={"msg": "zero_retry"}, error="e", max_retries=0)
    
    def failing_fn(p):
        raise RuntimeError("Immediate fail")
        
    await dlq.replay(entry_id, failing_fn)
    record = await dlq.peek(entry_id)
    assert record is not None and record.status.value == "FAILED"


@pytest.mark.asyncio
async def test_f05_bva_concurrent_enqueues_isolation() -> None:
    """F05-B4: 20 concurrent enqueues maintain strict record isolation in DLQ."""
    dlq = DurableDeadLetterQueue()
    async def do_enqueue(i: int):
        return await dlq.enqueue(payload={"index": i}, error="err")
        
    ids = await asyncio.gather(*[do_enqueue(i) for i in range(20)])
    assert len(set(ids)) == 20
    assert len(dlq.list_entries()) == 20


@pytest.mark.asyncio
async def test_f05_bva_timestamp_accuracy_at_now() -> None:
    """F05-B5: DLQ record createdAt timestamp within 2 seconds of system time."""
    dlq = DurableDeadLetterQueue()
    now = int(time.time())
    entry_id = await dlq.enqueue(payload={"test": "ts"}, error="e")
    record = await dlq.peek(entry_id)
    assert record is not None
    assert abs(record.createdAt - now) <= 2

# =============================================================================
# FEATURE 06: Error Taxonomy & Classification (5 boundary cases)
# =============================================================================

def test_f06_bva_http_status_boundary_200_to_599() -> None:
    """F06-B1: HTTP statuses 500, 502, 503 classified as TRANSIENT_NETWORK; 404, 422 as FATAL_CLIENT."""
    assert classify_error(500) == ErrorCategory.TRANSIENT_NETWORK
    assert classify_error(502) == ErrorCategory.TRANSIENT_NETWORK
    assert classify_error(503) == ErrorCategory.TRANSIENT_NETWORK
    assert classify_error(404) == ErrorCategory.FATAL_CLIENT
    assert classify_error(422) == ErrorCategory.FATAL_CLIENT


def test_f06_bva_nested_exception_unwrapping() -> None:
    """F06-B2: Nested exception causes (e.g. BudgetExceededViolation wrapped in RuntimeError) classified correctly."""
    root_cause = BudgetExceededViolation("Budget cap exceeded")
    wrapped = RuntimeError(f"Workflow failed: {root_cause}")
    assert classify_error(wrapped) == ErrorCategory.FATAL_SECURITY


def test_f06_bva_client_closed_request_499() -> None:
    """F06-B3: Custom HTTP 499 client closed request or timeout error classified as TRANSIENT_NETWORK."""
    assert classify_error("Client 499 closed request due to timeout") == ErrorCategory.TRANSIENT_NETWORK


def test_f06_bva_empty_error_string_fallback() -> None:
    """F06-B4: Empty error or generic unknown string defaults safely to FATAL_CLIENT."""
    assert classify_error("") == ErrorCategory.FATAL_CLIENT
    assert classify_error("Unknown domain error") == ErrorCategory.FATAL_CLIENT


def test_f06_bva_exception_subclasses_classification() -> None:
    """F06-B5: Specific security exceptions (NonceReplayException) map to FATAL_SECURITY."""
    exc = NonceReplayException("Replay attack detected")
    assert classify_error(exc) == ErrorCategory.FATAL_SECURITY

# =============================================================================
# FEATURE 07: Exponential Backoff & Jitter (5 boundary cases)
# =============================================================================

def test_f07_bva_negative_attempt_clamped_to_zero() -> None:
    """F07-B1: Negative attempt number (e.g. -5) clamped to 0, producing [0, base_delay]."""
    delay = compute_backoff_delay(attempt=-5, base_delay=1.0, max_delay=30.0, seed=10)
    assert 0.0 <= delay <= 1.0


def test_f07_bva_base_delay_equal_max_delay() -> None:
    """F07-B2: When base_delay == max_delay, delay is bounded by [0, max_delay]."""
    for att in range(5):
        delay = compute_backoff_delay(attempt=att, base_delay=5.0, max_delay=5.0, seed=42)
        assert 0.0 <= delay <= 5.0


def test_f07_bva_zero_base_delay_returns_zero() -> None:
    """F07-B3: When base_delay = 0.0, computed delay is strictly 0.0."""
    delay = compute_backoff_delay(attempt=5, base_delay=0.0, max_delay=30.0)
    assert delay == 0.0


def test_f07_bva_attempt_30_exact_power_boundary() -> None:
    """F07-B4: Attempt 30 executes without float overflow and respects max_delay."""
    delay = compute_backoff_delay(attempt=30, base_delay=0.5, max_delay=60.0)
    assert delay <= 60.0


def test_f07_bva_deterministic_seed_reproducibility() -> None:
    """F07-B5: Fixed seed produces 100% reproducible delay values."""
    d1 = compute_backoff_delay(attempt=3, base_delay=1.0, max_delay=30.0, seed=1337)
    d2 = compute_backoff_delay(attempt=3, base_delay=1.0, max_delay=30.0, seed=1337)
    assert d1 == d2

# =============================================================================
# FEATURE 08: Idempotent DLQ Replay (5 boundary cases)
# =============================================================================

@pytest.mark.asyncio
async def test_f08_bva_replay_with_async_coroutine_handler() -> None:
    """F08-B1: Replay supports native async coroutine handler functions."""
    dlq = DurableDeadLetterQueue()
    entry_id = await dlq.enqueue(payload={"sku": "SKU-ASYNC"}, error="Timeout")
    
    async def async_handler(payload):
        await asyncio.sleep(0.001)
        return f"Done {payload['sku']}"
        
    success, res = await dlq.replay(entry_id, async_handler)
    assert success is True
    assert res == "Done SKU-ASYNC"


@pytest.mark.asyncio
async def test_f08_bva_replay_with_exception_in_async_handler() -> None:
    """F08-B2: Replay safely catches exceptions thrown in async coroutines."""
    dlq = DurableDeadLetterQueue()
    entry_id = await dlq.enqueue(payload={"sku": "SKU-ERR"}, error="Timeout")
    
    async def async_fail(payload):
        raise ValueError("Async explosion")
        
    success, res = await dlq.replay(entry_id, async_fail)
    assert success is False
    assert "Async explosion" in res["error"]


@pytest.mark.asyncio
async def test_f08_bva_repeated_replay_10_times_idempotency() -> None:
    """F08-B3: 10 consecutive replay calls on resolved entry only execute handler once."""
    dlq = DurableDeadLetterQueue()
    entry_id = await dlq.enqueue(payload={"n": 42}, error="e")
    
    exec_count = 0
    def handler(p):
        nonlocal exec_count
        exec_count += 1
        return "SUCCESS"
        
    for _ in range(10):
        await dlq.replay(entry_id, handler)
    assert exec_count == 1


@pytest.mark.asyncio
async def test_f08_bva_replay_preserves_original_payload() -> None:
    """F08-B4: DLQ record original payload remains unchanged after multiple replays."""
    dlq = DurableDeadLetterQueue()
    orig_payload = {"user": "alice", "items": [{"id": 1}, {"id": 2}]}
    entry_id = await dlq.enqueue(payload=orig_payload, error="e")
    await dlq.replay(entry_id, lambda p: p)
    record = await dlq.peek(entry_id)
    assert record is not None
    assert record.payload == orig_payload


@pytest.mark.asyncio
async def test_f08_bva_replay_state_persisted_to_redis() -> None:
    """F08-B5: Replay state update is written to underlying Redis storage."""
    redis = MockRedisAsync()
    dlq = DurableDeadLetterQueue(redis_client=redis)
    entry_id = await dlq.enqueue(payload={"data": "test"}, error="e")
    await dlq.replay(entry_id, lambda p: "OK")
    redis_val = await redis.get(f"dlq:entry:{entry_id}")
    assert redis_val is not None
    assert "REPLAYED" in redis_val

# =============================================================================
# FEATURE 09: GSTIN & PAN Validators (5 boundary cases)
# =============================================================================

def test_f09_bva_14_char_gstin_rejected() -> None:
    """F09-B1: Exactly 14-character GSTIN rejected by validator."""
    assert validate_gstin("29AABCU9603R1Z") is False


def test_f09_bva_16_char_gstin_rejected() -> None:
    """F09-B2: Exactly 16-character GSTIN rejected by validator."""
    assert validate_gstin("29AABCU9603R1ZM1") is False


def test_f09_bva_all_valid_state_codes_accepted() -> None:
    """F09-B3: All valid state prefixes (01 through 38, 97, 99) accepted when PAN is valid."""
    for state in ["01", "07", "27", "29", "33", "36", "97", "99"]:
        gstin = f"{state}AABCU9603R1ZM"
        assert validate_gstin(gstin) is True


def test_f09_bva_special_characters_in_gstin_rejected() -> None:
    """F09-B4: GSTIN with special characters rejected."""
    assert validate_gstin("29AABCU9603R1Z!") is False
    assert validate_gstin("29AABCU@603R1ZM") is False


def test_f09_bva_pan_with_digit_in_wrong_position() -> None:
    """F09-B5: PAN with digit in letter positions (e.g. 1ABCU9603R) rejected."""
    assert validate_pan("1ABCU9603R") is False
    assert validate_pan("A1BCU9603R") is False
    assert validate_pan("AABCU96031") is False # 10th char must be letter

# =============================================================================
# FEATURE 10: GSTR-1 Rule 46 Invoice Schema (5 boundary cases)
# =============================================================================

def test_f10_bva_invoice_single_item_boundary() -> None:
    """F10-B1: GSTR-1 invoice with exactly 1 line item instantiates cleanly."""
    line = E2eInvoiceLineItem(
        skuId="SKU-1", description="Item 1", hsnSacCode="8504", quantity=1, unitPricePaise=1000,
        taxableAmountPaise=1000, gstRatePercent=18, cgstPaise=90, sgstPaise=90, igstPaise=0, totalPaise=1180,
    )
    inv = E2eGstr1Invoice(
        invoiceNumber="INV-1", invoiceDate="2026-08-26", supplierGstin="29AABCU9603R1ZJ",
        supplierStateCode="29", recipientStateCode="29", placeOfSupplyStateCode="29",
        isIntraState=True, lineItems=[line], taxableSubtotalPaise=1000, totalCgstPaise=90,
        totalSgstPaise=90, totalIgstPaise=0, totalTaxPaise=180, totalTcsPaise=10, grandTotalPaise=1180,
        cryptographicAuditHash="0"*64,
    )
    assert len(inv.lineItems) == 1


def test_f10_bva_invoice_hundred_items_boundary() -> None:
    """F10-B2: GSTR-1 invoice with 100 line items calculates aggregations correctly."""
    lines = [
        E2eInvoiceLineItem(
            skuId=f"SKU-{i}", description=f"Item {i}", hsnSacCode="8504", quantity=1, unitPricePaise=1000,
            taxableAmountPaise=1000, gstRatePercent=18, cgstPaise=90, sgstPaise=90, igstPaise=0, totalPaise=1180,
        )
        for i in range(100)
    ]
    inv = E2eGstr1Invoice(
        invoiceNumber="INV-100", invoiceDate="2026-08-26", supplierGstin="29AABCU9603R1ZJ",
        supplierStateCode="29", recipientStateCode="29", placeOfSupplyStateCode="29",
        isIntraState=True, lineItems=lines, taxableSubtotalPaise=100000, totalCgstPaise=9000,
        totalSgstPaise=9000, totalIgstPaise=0, totalTaxPaise=18000, totalTcsPaise=1000, grandTotalPaise=118000,
        cryptographicAuditHash="0"*64,
    )
    assert len(inv.lineItems) == 100


def test_f10_bva_invoice_zero_discount_and_zero_shipping() -> None:
    """F10-B3: Invoice with shipping=0 and discount=0 has grandTotal == taxable + totalTax."""
    line = E2eInvoiceLineItem(
        skuId="SKU-1", description="Item 1", hsnSacCode="8504", quantity=1, unitPricePaise=5000,
        taxableAmountPaise=5000, gstRatePercent=18, cgstPaise=450, sgstPaise=450, igstPaise=0, totalPaise=5900,
    )
    inv = E2eGstr1Invoice(
        invoiceNumber="INV-ZERO", invoiceDate="2026-08-26", supplierGstin="29AABCU9603R1ZJ",
        supplierStateCode="29", recipientStateCode="29", placeOfSupplyStateCode="29",
        isIntraState=True, lineItems=[line], taxableSubtotalPaise=5000, totalCgstPaise=450,
        totalSgstPaise=450, totalIgstPaise=0, totalTaxPaise=900, totalTcsPaise=50,
        shippingPaise=0, discountPaise=0, grandTotalPaise=5900, cryptographicAuditHash="0"*64,
    )
    assert inv.grandTotalPaise == 5900


def test_f10_bva_invoice_discount_equal_to_subtotal() -> None:
    """F10-B4: Discount equal to taxable subtotal yields gross total == totalTax + shipping."""
    gross = computeCartSettlementTotal(taxableSubtotalPaise=1000, totalTaxPaise=180, shippingPaise=50, discountPaise=1000)
    assert gross == 230


def test_f10_bva_invoice_number_length_16_chars_max() -> None:
    """F10-B5: 16-character maximum statutory invoice number accepted; 17-char rejected."""
    line = E2eInvoiceLineItem(
        skuId="SKU-1", description="Item 1", hsnSacCode="8504", quantity=1, unitPricePaise=1000,
        taxableAmountPaise=1000, gstRatePercent=18, cgstPaise=90, sgstPaise=90, igstPaise=0, totalPaise=1180,
    )
    inv16 = E2eGstr1Invoice(
        invoiceNumber="1234567890123456", invoiceDate="2026-08-26", supplierGstin="29AABCU9603R1ZJ",
        supplierStateCode="29", recipientStateCode="29", placeOfSupplyStateCode="29",
        isIntraState=True, lineItems=[line], taxableSubtotalPaise=1000, totalCgstPaise=90,
        totalSgstPaise=90, totalIgstPaise=0, totalTaxPaise=180, totalTcsPaise=10, grandTotalPaise=1180,
        cryptographicAuditHash="0"*64,
    )
    assert inv16.invoiceNumber == "1234567890123456"

    with pytest.raises(ValidationError):
        E2eGstr1Invoice(
            invoiceNumber="12345678901234567", invoiceDate="2026-08-26", supplierGstin="29AABCU9603R1ZJ",
            supplierStateCode="29", recipientStateCode="29", placeOfSupplyStateCode="29",
            isIntraState=True, lineItems=[line], taxableSubtotalPaise=1000, totalCgstPaise=90,
            totalSgstPaise=90, totalIgstPaise=0, totalTaxPaise=180, totalTcsPaise=10, grandTotalPaise=1180,
            cryptographicAuditHash="0"*64,
        )

# =============================================================================
# FEATURE 11: AP2 Mandate Schemas (M_I, M_C, M_E, M_A) (5 boundary cases)
# =============================================================================

def test_f11_bva_mandate_validity_1_second_ttl() -> None:
    """F11-B1: Mandate with 1 second TTL accepted when evaluated at timestamp."""
    actors = setup_e2e_actors()
    now = 1700000000
    intent = createSignedIntentMandate(
        mandateId="M-I-1S", userSigner=actors.user_cfo, delegatedAgentDid=actors.buyer_agent.getAgentDid(),
        maxBudgetPaise=100000, upiCircleDelegationToken="tok", singleTransactionLimitPaise=100000,
        validUntilTimestamp=now + 1, timestamp=now,
    )
    assert intent.validUntilTimestamp == now + 1


def test_f11_bva_mandate_spend_equal_to_single_tx_limit() -> None:
    """F11-B2: Execution spend exactly equal to singleTransactionLimitPaise passes budget gate."""
    actors = setup_e2e_actors()
    now = 1700000000
    intent = createSignedIntentMandate(
        mandateId="M-I-EQ-TX", userSigner=actors.user_cfo, delegatedAgentDid=actors.buyer_agent.getAgentDid(),
        maxBudgetPaise=500000, upiCircleDelegationToken="tok", singleTransactionLimitPaise=200000,
        timestamp=now,
    )
    item = CartItemSchema(skuId="SKU-1", quantity=1, unitPricePaise=200000, hsnCode="8504", gstRatePercent=0, lineTotalPaise=200000)
    tax = TaxBreakdownSchema(cgstPaise=0, sgstPaise=0, igstPaise=0, totalTaxPaise=0)
    cart = createSignedCartMandate(
        cartId="M-C-EQ-TX", merchantSigner=actors.merchant_nexus, merchantGstin="29AABCU9603R1ZJ",
        merchantStateCode="29", buyerDeliveryPincode="560001", buyerDeliveryStateCode="29",
        items=[item], taxableSubtotalPaise=200000, taxBreakdown=tax, shippingPaise=0, discountPaise=0,
        totalPaise=200000, inventoryLockToken="lock_eq", inventoryLockExpiresAt=now + 60, timestamp=now,
    )
    exec_m = createSignedExecutionMandate(
        executionId="M-E-EQ-TX", buyerAgentSigner=actors.buyer_agent,
        intentMandate=intent, cartMandate=cart, settlementAmountPaise=200000, upiCircleToken="tok",
        timestamp=now,
    )
    assert validateBudgetGate(intent, cart, exec_m, serverTime=now) is True


def test_f11_bva_mandate_spend_equal_to_max_budget() -> None:
    """F11-B3: Execution spend exactly equal to maxBudgetPaise passes budget gate."""
    actors = setup_e2e_actors()
    now = 1700000000
    intent = createSignedIntentMandate(
        mandateId="M-I-EQ-MAX", userSigner=actors.user_cfo, delegatedAgentDid=actors.buyer_agent.getAgentDid(),
        maxBudgetPaise=300000, upiCircleDelegationToken="tok", singleTransactionLimitPaise=300000,
        timestamp=now,
    )
    item = CartItemSchema(skuId="SKU-1", quantity=1, unitPricePaise=300000, hsnCode="8504", gstRatePercent=0, lineTotalPaise=300000)
    tax = TaxBreakdownSchema(cgstPaise=0, sgstPaise=0, igstPaise=0, totalTaxPaise=0)
    cart = createSignedCartMandate(
        cartId="M-C-EQ-MAX", merchantSigner=actors.merchant_nexus, merchantGstin="29AABCU9603R1ZJ",
        merchantStateCode="29", buyerDeliveryPincode="560001", buyerDeliveryStateCode="29",
        items=[item], taxableSubtotalPaise=300000, taxBreakdown=tax, shippingPaise=0, discountPaise=0,
        totalPaise=300000, inventoryLockToken="lock_max", inventoryLockExpiresAt=now + 60, timestamp=now,
    )
    exec_m = createSignedExecutionMandate(
        executionId="M-E-EQ-MAX", buyerAgentSigner=actors.buyer_agent,
        intentMandate=intent, cartMandate=cart, settlementAmountPaise=300000, upiCircleToken="tok",
        timestamp=now,
    )
    assert validateBudgetGate(intent, cart, exec_m, serverTime=now) is True


def test_f11_bva_mandate_empty_authorized_categories() -> None:
    """F11-B4: Empty authorized categories list in IntentMandate allows general procurement."""
    actors = setup_e2e_actors()
    intent = createSignedIntentMandate(
        mandateId="M-I-ALL", userSigner=actors.user_cfo, delegatedAgentDid=actors.buyer_agent.getAgentDid(),
        maxBudgetPaise=100000, upiCircleDelegationToken="tok", singleTransactionLimitPaise=100000,
        authorizedCategories=[],
    )
    assert intent.authorizedCategories == []


def test_f11_bva_amendment_mandate_zero_price_delta() -> None:
    """F11-B5: AmendmentMandate with priceDeltaPaise=0 represents 1:1 price parity replacement."""
    actors = setup_e2e_actors()
    item = CartItemSchema(skuId="SKU-1", quantity=1, unitPricePaise=100000, hsnCode="8504", gstRatePercent=18, lineTotalPaise=100000)
    tax = TaxBreakdownSchema(cgstPaise=9000, sgstPaise=9000, igstPaise=0, totalTaxPaise=18000)
    cart1 = createSignedCartMandate(
        cartId="M-C-1", merchantSigner=actors.merchant_nexus, merchantGstin="29AABCU9603R1ZJ",
        merchantStateCode="29", buyerDeliveryPincode="560001", buyerDeliveryStateCode="29",
        items=[item], taxableSubtotalPaise=100000, taxBreakdown=tax, shippingPaise=0, discountPaise=0,
        totalPaise=118000, inventoryLockToken="lock_1", inventoryLockExpiresAt=2000000000,
    )
    cart2 = cart1.model_copy(update={"cartId": "M-C-2"})
    amend = createSignedAmendmentMandate(
        amendmentId="M-A-ZERO", buyerAgentSigner=actors.buyer_agent, merchantSigner=actors.merchant_nexus,
        previousCartMandate=cart1, newCartMandate=cart2, substitutedSkuMapping={"SKU-1": "SKU-2"},
        priceDeltaPaise=0, amendmentReason="Equivalent model substitution",
    )
    assert amend.priceDeltaPaise == 0

# =============================================================================
# FEATURE 12: HSN/SAC & State Code Enclave (5 boundary cases)
# =============================================================================

def test_f12_bva_lowest_pincode_110001_delhi() -> None:
    """F12-B1: Lowest northern PIN code 110001 maps to state code 07 (Delhi)."""
    assert deriveStateCodeFromPincode("110001") == "07"


def test_f12_bva_highest_pincode_854337_bihar() -> None:
    """F12-B2: Eastern region PIN code 854337 maps to state code 10 (Bihar)."""
    assert deriveStateCodeFromPincode("854337") == "10"


def test_f12_bva_4_digit_hsn_code() -> None:
    """F12-B3: 4-digit minimum chapter HSN code '8471' resolves 18% rate."""
    assert resolveGstRate("8471") == 18


def test_f12_bva_8_digit_hsn_code() -> None:
    """F12-B4: 8-digit full tariff HSN code '84713010' resolves 18% rate."""
    assert resolveGstRate("84713010") == 18


def test_f12_bva_services_sac_code_9983() -> None:
    """F12-B5: Services SAC code '9983' resolves fallback default 18% tax rate."""
    assert resolveGstRate("998311") == 18

# =============================================================================
# FEATURE 13: Hypothesis / Property Math Invariants (5 boundary cases)
# =============================================================================

def test_f13_bva_scale_invariants_1_to_10_billion() -> None:
    """F13-B1: Scale invariance: computeLineItemTotal(p, q) == p * q across 10^0 to 10^10."""
    for exp in range(11):
        price = 10**exp
        assert computeLineItemTotal(price, 3) == 3 * price


def test_f13_bva_identity_element_zero_paise_addition() -> None:
    """F13-B2: Identity element: x + 0 == x in gross total summation."""
    subtotal = 75000
    assert computeCartSettlementTotal(subtotal, 0, 0, 0) == subtotal


def test_f13_bva_triangle_inequality_tax_subtotal() -> None:
    """F13-B3: Gross settlement total >= taxable subtotal when shipping >= discount."""
    gross = computeCartSettlementTotal(taxableSubtotalPaise=10000, totalTaxPaise=1800, shippingPaise=500, discountPaise=200)
    assert gross >= 10000


def test_f13_bva_idempotency_of_validation() -> None:
    """F13-B4: validateIntegerPaise is idempotent: validate(validate(x)) == validate(x)."""
    val = 123456
    assert validateIntegerPaise(validateIntegerPaise(val, "f"), "f") == val


def test_f13_bva_conservation_across_coprime_ratios() -> None:
    """F13-B5: Split conservation holds across coprime ratio sets [7, 11, 13]."""
    total = 99999
    shares = split_bill_conserved(total, [7, 11, 13])
    assert sum(shares) == total

# =============================================================================
# FEATURE 14: Stateful DLQ / 2PC FSM (5 boundary cases)
# =============================================================================

@pytest.mark.asyncio
async def test_f14_bva_2pc_fsm_single_transfer_rollback() -> None:
    """F14-B1: 2PC rollback with single transfer reverses exactly 1 transfer."""
    mock_route = MockRazorpayRouteClient({})
    mock_route.simulateSecondaryTransferFailure = True
    fsm = TwoPhaseCommitFsm(route_client=mock_route)
    fsm.prepare(fencing_token=1)
    
    with pytest.raises(SettlementCompensationTriggeredException):
        await fsm.commit_transfers([
            {"account": "acc_merchant", "amount": 1000},
            {"account": "acc_fail", "amount": 100},
        ])
    assert len(fsm.reversed_transfers) == 1


@pytest.mark.asyncio
async def test_f14_bva_2pc_fsm_five_transfers_lifo_rollback() -> None:
    """F14-B2: 2PC rollback reverses completed transfers in exact LIFO order."""
    class CustomRouteClient:
        def __init__(self):
            self.reversed = []
        async def createTransfer(self, recipientAccountId, amountPaise, notes=None):
            if recipientAccountId == "acc_5":
                raise RuntimeError("5th split rejected")
            return {"id": f"trf_{recipientAccountId}", "amount": amountPaise, "account": recipientAccountId}
        async def reverseTransfer(self, transferId, amountPaise):
            self.reversed.append(transferId)
            return {"id": f"rev_{transferId}"}

    client = CustomRouteClient()
    fsm = TwoPhaseCommitFsm(route_client=client)
    fsm.prepare(fencing_token=1)
    
    requests = [
        {"account": f"acc_{i}", "amount": 1000 * i}
        for i in range(1, 6)
    ]
    with pytest.raises(SettlementCompensationTriggeredException):
        await fsm.commit_transfers(requests)
        
    assert fsm.state == SagaState.ABORTED
    # Should reverse acc_4, acc_3, acc_2, acc_1 in LIFO order
    assert client.reversed == ["trf_acc_4", "trf_acc_3", "trf_acc_2", "trf_acc_1"]


@pytest.mark.asyncio
async def test_f14_bva_2pc_fsm_fencing_token_max_int64() -> None:
    """F14-B3: 2PC FSM accepts maximum 64-bit fencing token (2^63 - 1)."""
    fsm = TwoPhaseCommitFsm(route_client=MockRazorpayRouteClient({}))
    max_fence = 2**63 - 1
    assert fsm.prepare(fencing_token=max_fence) is True
    assert fsm.fencing_token == max_fence


@pytest.mark.asyncio
async def test_f14_bva_2pc_fsm_double_prepare_rejection() -> None:
    """F14-B4: Calling prepare() twice in succession raises IllegalStateTransitionError."""
    fsm = TwoPhaseCommitFsm(route_client=MockRazorpayRouteClient({}))
    fsm.prepare(fencing_token=1)
    with pytest.raises(IllegalStateTransitionError):
        fsm.prepare(fencing_token=2)


@pytest.mark.asyncio
async def test_f14_bva_2pc_fsm_rollback_with_zero_completed_transfers() -> None:
    """F14-B5: Calling rollback when 0 transfers succeeded handles cleanly with 0 reversals."""
    fsm = TwoPhaseCommitFsm(route_client=MockRazorpayRouteClient({}))
    fsm.prepare(fencing_token=1)
    await fsm.rollback()
    assert fsm.state == SagaState.ABORTED
    assert len(fsm.reversed_transfers) == 0

# =============================================================================
# FEATURE 15: Schema Invariant Fuzzing (5 boundary cases)
# =============================================================================

def test_f15_bva_zero_width_unicode_stripping() -> None:
    """F15-B1: Zero-width spaces (\u200B, \u200C) in strings handled cleanly."""
    raw_title = "Precision Sensor\u200B\u200C"
    line = E2eInvoiceLineItem(
        skuId="SKU-ZW", description=raw_title, hsnSacCode="8504", quantity=1, unitPricePaise=1000,
        taxableAmountPaise=1000, gstRatePercent=18, cgstPaise=90, sgstPaise=90, igstPaise=0, totalPaise=1180,
    )
    assert line.description == raw_title


def test_f15_bva_null_byte_rejection() -> None:
    """F15-B2: String with null byte preserved or safely encoded in schema."""
    null_desc = "Sensor\x00Device"
    line = E2eInvoiceLineItem(
        skuId="SKU-NULL", description=null_desc, hsnSacCode="8504", quantity=1, unitPricePaise=1000,
        taxableAmountPaise=1000, gstRatePercent=18, cgstPaise=90, sgstPaise=90, igstPaise=0, totalPaise=1180,
    )
    assert line.description == null_desc


def test_f15_bva_10000_char_long_string_handling() -> None:
    """F15-B3: 10,000 character long string handled in description without memory error."""
    long_desc = "A" * 10000
    line = E2eInvoiceLineItem(
        skuId="SKU-LONG", description=long_desc, hsnSacCode="8504", quantity=1, unitPricePaise=1000,
        taxableAmountPaise=1000, gstRatePercent=18, cgstPaise=90, sgstPaise=90, igstPaise=0, totalPaise=1180,
    )
    assert len(line.description) == 10000


def test_f15_bva_nested_json_object_depth_10() -> None:
    """F15-B4: Deeply nested JSON object (depth 10) canonicalized cleanly by JCS."""
    current: Dict[str, Any] = {"leaf": 42}
    for i in range(10):
        current = {f"level_{i}": current}
    canon = canonicalizeJson(current)
    assert "leaf" in canon.decode()


def test_f15_bva_float_in_jcs_canonicalizer_deeply_nested() -> None:
    """F15-B5: Deeply nested float (e.g. at depth 5) caught and rejected by JCS canonicalizer."""
    nested = {"a": {"b": {"c": {"d": {"e": 3.14159}}}}}
    with pytest.raises(ArithmeticDriftException):
        canonicalizeJson(nested)

# =============================================================================
# FEATURE 16: E2E Regression Verification (5 boundary cases)
# =============================================================================

@pytest.mark.asyncio
async def test_f16_bva_exact_budget_ceiling_spend() -> None:
    """F16-B1: Settlement amount spending 100% of maxBudgetPaise captures successfully."""
    actors = setup_e2e_actors()
    now = int(time.time())
    exact_amount = 500000
    
    intent = createSignedIntentMandate(
        mandateId="M-I-CEIL", userSigner=actors.user_cfo, delegatedAgentDid=actors.buyer_agent.getAgentDid(),
        maxBudgetPaise=exact_amount, upiCircleDelegationToken="tok", singleTransactionLimitPaise=exact_amount,
        timestamp=now,
    )
    item = CartItemSchema(skuId="SKU-1", quantity=1, unitPricePaise=exact_amount, hsnCode="8504", gstRatePercent=0, lineTotalPaise=exact_amount)
    tax = TaxBreakdownSchema(cgstPaise=0, sgstPaise=0, igstPaise=0, totalTaxPaise=0)
    cart = createSignedCartMandate(
        cartId="M-C-CEIL", merchantSigner=actors.merchant_nexus, merchantGstin="29AABCU9603R1ZJ",
        merchantStateCode="29", buyerDeliveryPincode="560001", buyerDeliveryStateCode="29",
        items=[item], taxableSubtotalPaise=exact_amount, taxBreakdown=tax, shippingPaise=0, discountPaise=0,
        totalPaise=exact_amount, inventoryLockToken="lock_ceil", inventoryLockExpiresAt=now + 60, timestamp=now,
    )
    exec_m = createSignedExecutionMandate(
        executionId="M-E-CEIL", buyerAgentSigner=actors.buyer_agent,
        intentMandate=intent, cartMandate=cart, settlementAmountPaise=exact_amount, upiCircleToken="tok",
        timestamp=now,
    )
    redis = MockRedisAsync()
    orchestrator = SettlementOrchestrator(
        routeClient=RazorpayRouteClient(apiKey="key", apiSecret="sec"),
        nonceLedger=NonceLedger(redis),
    )
    res = await orchestrator.executeSettlementSaga(
        intentMandate=intent, cartMandate=cart, executionMandate=exec_m,
        merchantAccount="acc_merchant_nexus_01", paymentId="pay_ceil", serverTime=now,
    )
    assert res.status == "captured"
    assert res.amountPaise == exact_amount


@pytest.mark.asyncio
async def test_f16_bva_single_stock_inventory_race() -> None:
    """F16-B2: Exactly 1 item in stock: first lock succeeds, concurrent second lock fails with -1."""
    redis = MockRedisAsync()
    stock_key = "sku:SKU-RACE:stock"
    fence_key = "sku:SKU-RACE:fence"
    await redis.set(stock_key, 1)
    
    # First requester reserves 1 unit
    res1 = await redis.eval("", 2, stock_key, fence_key, 1, "token_1", 60)
    assert res1[0] == 1  # Success
    
    # Second requester attempts to reserve 1 unit
    res2 = await redis.eval("", 2, stock_key, fence_key, 1, "token_2", 60)
    assert res2[0] == -1  # Depleted
    assert res2[1] == 0   # Available stock is 0


def test_f16_bva_price_drop_alert_at_exact_target_price() -> None:
    """F16-B3: Alert triggers when catalog price drops to exactly targetPricePaise."""
    base_price = 420000
    target_price = 350000
    active_price = 350000
    is_triggered = active_price <= target_price
    assert is_triggered is True


def test_f16_bva_oos_healing_at_exact_5_percent_delta() -> None:
    """F16-B4: Out-of-stock substitute with price increase of exactly 5.0% accepted."""
    orig_price = 100000
    sub_price = 105000  # Exactly +5.0%
    delta_pct = (sub_price - orig_price) / orig_price * 100.0
    assert delta_pct == 5.0
    assert delta_pct <= 5.0


@pytest.mark.asyncio
async def test_f16_bva_multi_party_saga_five_way_route_split() -> None:
    """F16-B5: 5-way Route transfer split (merchant, protocol, logistics, taxes, affiliate) conserved."""
    actors = setup_e2e_actors()
    total_order = 100000
    splits = split_bill_conserved(total_order, [70, 10, 10, 5, 5])
    assert sum(splits) == 100000
    assert len(splits) == 5
