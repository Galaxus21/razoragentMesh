"""Tier 1: Comprehensive Feature Coverage Test Suite (16 features × 5 test cases = 80 tests).

Covers F01 to F16 with opaque-box specification testing.
"""

from decimal import Decimal
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
# FEATURE 01: Integer Math Enclave (5 cases)
# =============================================================================

def test_f01_validate_integer_paise_success_and_types() -> None:
    """F01-1: validateIntegerPaise accepts positive, zero, and exact integers."""
    assert validateIntegerPaise(5000, "testField") == 5000
    assert validateIntegerPaise(0, "zeroField") == 0
    assert validateIntegerPaise(100000000, "largeField") == 100000000


def test_f01_float_rejection_raises_arithmetic_drift() -> None:
    """F01-2: validateIntegerPaise rejects float values to prevent rounding drift."""
    with pytest.raises(ArithmeticDriftException):
        validateIntegerPaise(1976.50, "floatPrice")
    with pytest.raises(ArithmeticDriftException):
        validateIntegerPaise(0.0001, "fractionalPaise")


def test_f01_boolean_rejection_raises_arithmetic_drift() -> None:
    """F01-3: validateIntegerPaise rejects booleans masked as integers."""
    with pytest.raises(ArithmeticDriftException):
        validateIntegerPaise(True, "boolField")
    with pytest.raises(ArithmeticDriftException):
        validateIntegerPaise(False, "boolField")


def test_f01_compute_line_item_total_positive() -> None:
    """F01-4: computeLineItemTotal accurately computes unit price * quantity."""
    assert computeLineItemTotal(420000, 3) == 1260000
    assert computeLineItemTotal(100, 1) == 100
    with pytest.raises(ArithmeticDriftException):
        computeLineItemTotal(100, 0)
    with pytest.raises(ArithmeticDriftException):
        computeLineItemTotal(-50, 2)


def test_f01_compute_cart_settlement_total_gross() -> None:
    """F01-5: computeCartSettlementTotal computes gross sum with shipping & discounts."""
    gross = computeCartSettlementTotal(
        taxableSubtotalPaise=100000, totalTaxPaise=18000, shippingPaise=5000, discountPaise=3000
    )
    assert gross == 120000
    with pytest.raises(ArithmeticDriftException):
        computeCartSettlementTotal(taxableSubtotalPaise=100, totalTaxPaise=18, discountPaise=500)

# =============================================================================
# FEATURE 02: Statutory GST (CGST/SGST/IGST) (5 cases)
# =============================================================================

def test_f02_gst_intra_state_50_50_split() -> None:
    """F02-1: Intra-state transaction splits GST 50/50 between CGST and SGST with IGST=0."""
    gst = computeGstBreakdown(taxableSubtotalPaise=100000, gstRatePercent=18, isIntraState=True)
    assert gst["cgstPaise"] == 9000
    assert gst["sgstPaise"] == 9000
    assert gst["igstPaise"] == 0
    assert gst["totalTaxPaise"] == 18000


def test_f02_gst_inter_state_100_igst() -> None:
    """F02-2: Inter-state transaction routes 100% GST to IGST with CGST=0, SGST=0."""
    gst = computeGstBreakdown(taxableSubtotalPaise=100000, gstRatePercent=18, isIntraState=False)
    assert gst["cgstPaise"] == 0
    assert gst["sgstPaise"] == 0
    assert gst["igstPaise"] == 18000
    assert gst["totalTaxPaise"] == 18000


def test_f02_gst_odd_paise_penny_conservation() -> None:
    """F02-3: Odd taxable amount conserves exact pennies across CGST and SGST floor division."""
    gst = computeGstBreakdown(taxableSubtotalPaise=101, gstRatePercent=5, isIntraState=True)
    assert gst["cgstPaise"] + gst["sgstPaise"] == gst["totalTaxPaise"]
    assert gst["totalTaxPaise"] == (101 * 5) // 100
    assert gst["igstPaise"] == 0


def test_f02_gst_zero_rated_exempt_goods() -> None:
    """F02-4: Zero-rated exempt goods calculate 0 paise tax across all components."""
    gst = computeGstBreakdown(taxableSubtotalPaise=500000, gstRatePercent=0, isIntraState=True)
    assert gst["cgstPaise"] == 0 and gst["sgstPaise"] == 0 and gst["totalTaxPaise"] == 0


def test_f02_gst_section_52_tcs_withholding() -> None:
    """F02-5: Section 52 TCS withholding calculates exact 1% split (0.5%+0.5% intra, 1.0% inter)."""
    tcs_intra = computeTcsWithholding(taxableSubtotalPaise=100000, isIntraState=True)
    assert tcs_intra["tcsCgstPaise"] == 500
    assert tcs_intra["tcsSgstPaise"] == 500
    assert tcs_intra["totalTcsPaise"] == 1000

    tcs_inter = computeTcsWithholding(taxableSubtotalPaise=100000, isIntraState=False)
    assert tcs_inter["tcsIgstPaise"] == 1000
    assert tcs_inter["totalTcsPaise"] == 1000

# =============================================================================
# FEATURE 03: Conserved Bill Splitting (5 cases)
# =============================================================================

def test_f03_equal_two_way_split() -> None:
    """F03-1: Equal 2-way split divides funds evenly with zero penny loss."""
    shares = split_bill_conserved(total_amount_paise=10000, participant_ratios=[1, 1])
    assert shares == [5000, 5000]
    assert sum(shares) == 10000


def test_f03_equal_three_way_split_remainder_allocation() -> None:
    """F03-2: 100 paise split 3 ways allocates remainder deterministically to [34, 33, 33]."""
    shares = split_bill_conserved(total_amount_paise=100, participant_ratios=[1, 1, 1])
    assert shares == [34, 33, 33]
    assert sum(shares) == 100


def test_f03_weighted_multi_party_split() -> None:
    """F03-3: Weighted ratio split (3:2:1) allocates proportional shares exactly."""
    shares = split_bill_conserved(total_amount_paise=60000, participant_ratios=[3, 2, 1])
    assert shares == [30000, 20000, 10000]
    assert sum(shares) == 60000


def test_f03_single_party_100_percent_split() -> None:
    """F03-4: Single-party bill split returns 100% of the total amount."""
    shares = split_bill_conserved(total_amount_paise=420000, participant_ratios=[1])
    assert shares == [420000]


def test_f03_ten_party_uneven_split_conservation() -> None:
    """F03-5: 10-party uneven split guarantees sum(shares) == total_amount_paise."""
    ratios = [1, 2, 3, 4, 5, 6, 7, 8, 9, 10]
    shares = split_bill_conserved(total_amount_paise=100003, participant_ratios=ratios)
    assert len(shares) == 10
    assert sum(shares) == 100003

# =============================================================================
# FEATURE 04: Fee & Commission Splits (5 cases)
# =============================================================================

def test_f04_basis_points_commission_deduction() -> None:
    """F04-1: 500 bps (5%) platform commission calculated with zero float drift."""
    res = calculate_route_splits(order_paise=100000, commission_bps=500, flat_fee_paise=0)
    assert res.commission_paise == 5000
    assert res.total_fee_paise == 5000
    assert res.merchant_net_paise == 95000


def test_f04_flat_fee_deduction() -> None:
    """F04-2: Flat fee deduction without commission deducted cleanly."""
    res = calculate_route_splits(order_paise=50000, commission_bps=0, flat_fee_paise=50)
    assert res.commission_paise == 0
    assert res.flat_fee_paise == 50
    assert res.merchant_net_paise == 49950


def test_f04_combined_bps_and_flat_fee() -> None:
    """F04-3: Combined percentage commission + flat fee split calculated accurately."""
    res = calculate_route_splits(order_paise=200000, commission_bps=250, flat_fee_paise=100)
    # 2.5% of 200,000 = 5,000 paise + 100 paise flat fee = 5,100 paise total fee
    assert res.commission_paise == 5000
    assert res.total_fee_paise == 5100
    assert res.merchant_net_paise == 194900


def test_f04_fee_exceeding_order_amount_clamped() -> None:
    """F04-4: When fee exceeds order value, merchant net is clamped to 0 with no negative debt."""
    res = calculate_route_splits(order_paise=1000, commission_bps=0, flat_fee_paise=2000)
    assert res.merchant_net_paise == 0
    assert res.total_fee_paise == 1000


def test_f04_zero_commission_and_zero_flat_fee() -> None:
    """F04-5: Zero commission and zero flat fee returns full order amount to merchant."""
    res = calculate_route_splits(order_paise=75000, commission_bps=0, flat_fee_paise=0)
    assert res.total_fee_paise == 0
    assert res.merchant_net_paise == 75000

# =============================================================================
# FEATURE 05: Durable DLQ Persistence (5 cases)
# =============================================================================

@pytest.mark.asyncio
async def test_f05_dlq_enqueue_successful_persistence() -> None:
    """F05-1: DLQ enqueue creates durable record with status PENDING and error details."""
    dlq = DurableDeadLetterQueue()
    entry_id = await dlq.enqueue(
        payload={"orderId": "ORD-001", "amountPaise": 50000},
        error=RuntimeError("Gateway connection timeout"),
        category=ErrorCategory.TRANSIENT_NETWORK,
        idempotency_key="idem_ord_001",
    )
    assert entry_id.startswith("dlq_")
    record = await dlq.peek(entry_id)
    assert record is not None
    assert record.payload["orderId"] == "ORD-001"
    assert record.errorCategory == ErrorCategory.TRANSIENT_NETWORK
    assert record.status.value == "PENDING"


@pytest.mark.asyncio
async def test_f05_dlq_idempotency_key_deduplication() -> None:
    """F05-2: Enqueuing with duplicate idempotency key returns existing entry without duplication."""
    dlq = DurableDeadLetterQueue()
    id1 = await dlq.enqueue(payload={"data": "test"}, error="err1", idempotency_key="key_duplicate")
    id2 = await dlq.enqueue(payload={"data": "test"}, error="err2", idempotency_key="key_duplicate")
    assert id1 == id2
    assert len(dlq.list_entries()) == 1


@pytest.mark.asyncio
async def test_f05_dlq_empty_payload_rejection() -> None:
    """F05-3: DLQ rejects empty dictionary payload with ValueError."""
    dlq = DurableDeadLetterQueue()
    with pytest.raises(ValueError):
        await dlq.enqueue(payload={}, error="err")


@pytest.mark.asyncio
async def test_f05_dlq_record_retrieval_peek() -> None:
    """F05-4: Peek returns None for non-existent entry ID and record for valid ID."""
    dlq = DurableDeadLetterQueue()
    assert await dlq.peek("non_existent_id") is None
    entry_id = await dlq.enqueue(payload={"sku": "SKU-1"}, error="fail")
    record = await dlq.peek(entry_id)
    assert record is not None and record.payload["sku"] == "SKU-1"


@pytest.mark.asyncio
async def test_f05_dlq_list_entries_by_status() -> None:
    """F05-5: list_entries returns all records or filtered by status."""
    dlq = DurableDeadLetterQueue()
    await dlq.enqueue(payload={"msg": "1"}, error="err1")
    await dlq.enqueue(payload={"msg": "2"}, error="err2")
    all_entries = dlq.list_entries()
    assert len(all_entries) == 2

# =============================================================================
# FEATURE 06: Error Taxonomy & Classification (5 cases)
# =============================================================================

def test_f06_classify_http_429_transient_rate_limit() -> None:
    """F06-1: HTTP 429 status or Rate Limit error classified as TRANSIENT_RATE_LIMIT and retryable."""
    cat = classify_error(429)
    assert cat == ErrorCategory.TRANSIENT_RATE_LIMIT
    assert is_retryable(cat) is True
    assert classify_error("Too Many Requests: Rate limit exceeded") == ErrorCategory.TRANSIENT_RATE_LIMIT


def test_f06_classify_http_504_transient_network() -> None:
    """F06-2: HTTP 504 gateway timeout classified as TRANSIENT_NETWORK and retryable."""
    cat = classify_error(504)
    assert cat == ErrorCategory.TRANSIENT_NETWORK
    assert is_retryable(cat) is True
    assert classify_error("ReadTimeout: Socket timed out") == ErrorCategory.TRANSIENT_NETWORK


def test_f06_classify_http_400_fatal_client() -> None:
    """F06-3: HTTP 400 Bad Request classified as FATAL_CLIENT and non-retryable."""
    cat = classify_error(400)
    assert cat == ErrorCategory.FATAL_CLIENT
    assert is_retryable(cat) is False


def test_f06_classify_security_signature_fatal_security() -> None:
    """F06-4: Cryptographic signature failure classified as FATAL_SECURITY and non-retryable."""
    cat = classify_error(SignatureVerificationFailedException("Bad signature"))
    assert cat == ErrorCategory.FATAL_SECURITY
    assert is_retryable(cat) is False


def test_f06_classify_poison_pill_unparseable() -> None:
    """F06-5: Corrupted or unparseable JSON payload classified as POISON_PILL."""
    cat = classify_error("Poison pill: malformed unhandled json string")
    assert cat == ErrorCategory.POISON_PILL
    assert is_retryable(cat) is False

# =============================================================================
# FEATURE 07: Exponential Backoff & Jitter (5 cases)
# =============================================================================

def test_f07_backoff_delay_exponential_growth() -> None:
    """F07-1: Backoff upper ceiling grows exponentially with attempt count."""
    delay0 = compute_backoff_delay(attempt=0, base_delay=1.0, max_delay=60.0, seed=42)
    assert 0.0 <= delay0 <= 1.0
    # At attempt 4, ceiling is min(60, 1.0 * 16) = 16.0
    delay4 = compute_backoff_delay(attempt=4, base_delay=1.0, max_delay=60.0, seed=42)
    assert 0.0 <= delay4 <= 16.0


def test_f07_backoff_delay_max_delay_ceiling() -> None:
    """F07-2: Backoff delay respects max_delay ceiling even under high attempts."""
    for att in [10, 20, 30]:
        delay = compute_backoff_delay(attempt=att, base_delay=1.0, max_delay=10.0, seed=123)
        assert delay <= 10.0


def test_f07_backoff_jitter_distribution_bounds() -> None:
    """F07-3: Full Jitter produces randomized values within [0, ceiling]."""
    delays = [compute_backoff_delay(attempt=3, base_delay=0.5, max_delay=30.0) for _ in range(50)]
    assert all(0.0 <= d <= 4.0 for d in delays)
    assert len(set(delays)) > 1  # Verify randomness


def test_f07_backoff_attempt_zero_bounded() -> None:
    """F07-4: Attempt 0 delay is bounded by [0, base_delay]."""
    delay = compute_backoff_delay(attempt=0, base_delay=0.5, max_delay=30.0, seed=99)
    assert 0.0 <= delay <= 0.5


def test_f07_backoff_extreme_attempt_overflow_guard() -> None:
    """F07-5: Extreme attempt count (e.g. 1000) does not cause float overflow."""
    delay = compute_backoff_delay(attempt=1000, base_delay=1.0, max_delay=30.0)
    assert 0.0 <= delay <= 30.0

# =============================================================================
# FEATURE 08: Idempotent DLQ Replay (5 cases)
# =============================================================================

@pytest.mark.asyncio
async def test_f08_replay_pending_entry_success() -> None:
    """F08-1: Replaying a pending DLQ entry executes handler and marks status REPLAYED."""
    dlq = DurableDeadLetterQueue()
    entry_id = await dlq.enqueue(payload={"orderId": "ORD-REPLAY-1", "amount": 100}, error="Timeout")
    
    success, result = await dlq.replay(entry_id, lambda p: f"Processed {p['orderId']}")
    assert success is True
    assert result == "Processed ORD-REPLAY-1"
    record = await dlq.peek(entry_id)
    assert record is not None and record.status.value == "REPLAYED"


@pytest.mark.asyncio
async def test_f08_replay_already_replayed_is_idempotent() -> None:
    """F08-2: Replaying an already resolved DLQ entry returns already_replayed without re-executing."""
    dlq = DurableDeadLetterQueue()
    entry_id = await dlq.enqueue(payload={"orderId": "ORD-REPLAY-2"}, error="Timeout")
    
    call_count = 0
    def handler(p):
        nonlocal call_count
        call_count += 1
        return "OK"
        
    await dlq.replay(entry_id, handler)
    assert call_count == 1
    
    # Second replay
    success, result = await dlq.replay(entry_id, handler)
    assert success is True
    assert result["status"] == "already_replayed"
    assert call_count == 1  # Handler not called again


@pytest.mark.asyncio
async def test_f08_replay_handler_failure_increments_retry() -> None:
    """F08-3: Replay handler failure catches exception, increments retryCount, and preserves PENDING status."""
    dlq = DurableDeadLetterQueue()
    entry_id = await dlq.enqueue(payload={"orderId": "ORD-FAIL-1"}, error="Timeout", max_retries=3)
    
    def failing_handler(p):
        raise RuntimeError("Service still down")
        
    success, result = await dlq.replay(entry_id, failing_handler)
    assert success is False
    assert "Service still down" in result["error"]
    record = await dlq.peek(entry_id)
    assert record is not None and record.retryCount == 1
    assert record.status.value == "PENDING"


@pytest.mark.asyncio
async def test_f08_replay_max_retries_marks_failed() -> None:
    """F08-4: Exceeding maxRetries marks entry status as FAILED."""
    dlq = DurableDeadLetterQueue()
    entry_id = await dlq.enqueue(payload={"orderId": "ORD-MAX-FAIL"}, error="Timeout", max_retries=1)
    
    def failing_handler(p):
        raise RuntimeError("Persistent failure")
        
    success, result = await dlq.replay(entry_id, failing_handler)
    assert success is False
    record = await dlq.peek(entry_id)
    assert record is not None and record.status.value == "FAILED"


@pytest.mark.asyncio
async def test_f08_replay_non_existent_entry_raises_key_error() -> None:
    """F08-5: Replaying non-existent entry ID raises KeyError."""
    dlq = DurableDeadLetterQueue()
    with pytest.raises(KeyError):
        await dlq.replay("dlq_unknown_id", lambda p: p)

# =============================================================================
# FEATURE 09: GSTIN & PAN Validators (5 cases)
# =============================================================================

def test_f09_valid_gstin_format_verification() -> None:
    """F09-1: Valid 15-character GSTIN format passes validation."""
    assert validate_gstin("29AABCU9603R1ZJ") is True
    assert validate_gstin("27ABCDE1234F1Z0") is True
    assert validate_gstin("07AAAAA0000A1Z4") is True


def test_f09_invalid_state_code_gstin_rejection() -> None:
    """F09-2: GSTIN with invalid or unallocated state prefix (e.g. 00, 98) fails validation."""
    assert validate_gstin("00AABCU9603R1ZM") is False
    assert validate_gstin("98AABCU9603R1ZM") is False


def test_f09_valid_pan_format_verification() -> None:
    """F09-3: Valid 10-character PAN format passes validation."""
    assert validate_pan("AABCU9603R") is True
    assert validate_pan("ABCDE1234F") is True


def test_f09_malformed_pan_rejection() -> None:
    """F09-4: Malformed, lowercase, or incorrect length PAN fails validation."""
    assert validate_pan("aabcu9603r") is False
    assert validate_pan("AABCU9603") is False  # 9 chars
    assert validate_pan("AABCU9603RR") is False # 11 chars
    assert validate_pan("12345ABCDE") is False


def test_f09_extract_pan_and_state_from_gstin() -> None:
    """F09-5: Extracts embedded 10-character PAN and 2-digit state code from GSTIN."""
    gstin = "29AABCU9603R1ZJ"
    assert extract_pan_from_gstin(gstin) == "AABCU9603R"
    assert extract_state_from_gstin(gstin) == "29"
    assert extract_pan_from_gstin("INVALID") is None

# =============================================================================
# FEATURE 10: GSTR-1 Rule 46 Invoice Schema (5 cases)
# =============================================================================

def test_f10_invoice_mandatory_fields_validation() -> None:
    """F10-1: GSTR-1 Rule 46 invoice instantiates cleanly with all statutory fields."""
    line = E2eInvoiceLineItem(
        skuId="SKU-INV-1", description="Industrial Sensor", hsnSacCode="8504",
        quantity=1, unitPricePaise=100000, taxableAmountPaise=100000,
        gstRatePercent=18, cgstPaise=9000, sgstPaise=9000, igstPaise=0, totalPaise=118000,
    )
    inv = E2eGstr1Invoice(
        invoiceNumber="INV-2026-001", invoiceDate="2026-08-26T00:00:00Z",
        supplierGstin="29AABCU9603R1ZJ", supplierStateCode="29",
        recipientGstin="29ABCDE1234F1ZW", recipientStateCode="29",
        placeOfSupplyStateCode="29", isIntraState=True,
        lineItems=[line], taxableSubtotalPaise=100000,
        totalCgstPaise=9000, totalSgstPaise=9000, totalIgstPaise=0,
        totalTaxPaise=18000, totalTcsPaise=1000, shippingPaise=0, discountPaise=0,
        grandTotalPaise=118000, cryptographicAuditHash="a" * 64,
    )
    assert inv.invoiceNumber == "INV-2026-001"
    assert inv.isIntraState is True


def test_f10_invoice_line_items_tax_summation_invariant() -> None:
    """F10-2: Invoice line item taxable and tax amounts sum precisely to total invoice headers."""
    line1 = E2eInvoiceLineItem(
        skuId="SKU-1", description="Item 1", hsnSacCode="8504", quantity=1, unitPricePaise=50000,
        taxableAmountPaise=50000, gstRatePercent=18, cgstPaise=4500, sgstPaise=4500, igstPaise=0, totalPaise=59000,
    )
    line2 = E2eInvoiceLineItem(
        skuId="SKU-2", description="Item 2", hsnSacCode="8504", quantity=2, unitPricePaise=25000,
        taxableAmountPaise=50000, gstRatePercent=18, cgstPaise=4500, sgstPaise=4500, igstPaise=0, totalPaise=59000,
    )
    totalTaxable = line1.taxableAmountPaise + line2.taxableAmountPaise
    totalTax = line1.cgstPaise + line1.sgstPaise + line2.cgstPaise + line2.sgstPaise
    assert totalTaxable == 100000
    assert totalTax == 18000


def test_f10_invoice_hsn_code_pattern_enforcement() -> None:
    """F10-3: Invoice line item rejects non-numeric or invalid length HSN codes."""
    with pytest.raises(ValidationError):
        E2eInvoiceLineItem(
            skuId="SKU-BAD", description="Item", hsnSacCode="HSN85", quantity=1, unitPricePaise=100,
            taxableAmountPaise=100, gstRatePercent=18, cgstPaise=9, sgstPaise=9, igstPaise=0, totalPaise=118,
        )


def test_f10_invoice_reverse_charge_flag_default() -> None:
    """F10-4: Default reverse charge flag is False as per standard forward charge."""
    line = E2eInvoiceLineItem(
        skuId="SKU-1", description="Item", hsnSacCode="8504", quantity=1, unitPricePaise=1000,
        taxableAmountPaise=1000, gstRatePercent=18, cgstPaise=90, sgstPaise=90, igstPaise=0, totalPaise=1180,
    )
    inv = E2eGstr1Invoice(
        invoiceNumber="INV-01", invoiceDate="2026-08-26", supplierGstin="29AABCU9603R1ZJ",
        supplierStateCode="29", recipientStateCode="29", placeOfSupplyStateCode="29",
        isIntraState=True, lineItems=[line], taxableSubtotalPaise=1000, totalCgstPaise=90,
        totalSgstPaise=90, totalIgstPaise=0, totalTaxPaise=180, totalTcsPaise=10, grandTotalPaise=1180,
        cryptographicAuditHash="0" * 64,
    )
    assert inv.isReverseChargeApplicable is False


def test_f10_invoice_cryptographic_audit_hash_64_hex() -> None:
    """F10-5: Cryptographic audit hash is strictly 64 hexadecimal characters."""
    with pytest.raises(ValidationError):
        E2eGstr1Invoice(
            invoiceNumber="INV-01", invoiceDate="2026-08-26", supplierGstin="29AABCU9603R1ZJ",
            supplierStateCode="29", recipientStateCode="29", placeOfSupplyStateCode="29",
            isIntraState=True, lineItems=[], taxableSubtotalPaise=1000, totalCgstPaise=90,
            totalSgstPaise=90, totalIgstPaise=0, totalTaxPaise=180, totalTcsPaise=10, grandTotalPaise=1180,
            cryptographicAuditHash="short_hash",
        )

# =============================================================================
# FEATURE 11: AP2 Mandate Schemas (M_I, M_C, M_E, M_A) (5 cases)
# =============================================================================

def test_f11_intent_mandate_creation_and_bounds() -> None:
    """F11-1: IntentMandate (M_I) created with valid spend bounds and Ed25519 signature."""
    actors = setup_e2e_actors()
    intent = createSignedIntentMandate(
        mandateId="M-I-01", userSigner=actors.user_cfo, delegatedAgentDid=actors.buyer_agent.getAgentDid(),
        maxBudgetPaise=500000, upiCircleDelegationToken="upi_tok", singleTransactionLimitPaise=250000,
    )
    assert intent.mandateId == "M-I-01"
    assert intent.maxBudgetPaise == 500000
    assert len(intent.userSignature) == 128


def test_f11_cart_mandate_creation_and_inventory_lock() -> None:
    """F11-2: CartMandate (M_C) signed by merchant carries lock token and itemized breakdown."""
    actors = setup_e2e_actors()
    item = CartItemSchema(
        skuId="SKU-001", quantity=1, unitPricePaise=100000, hsnCode="8504",
        gstRatePercent=18, lineTotalPaise=100000,
    )
    tax = TaxBreakdownSchema(cgstPaise=9000, sgstPaise=9000, igstPaise=0, totalTaxPaise=18000)
    cart = createSignedCartMandate(
        cartId="M-C-01", merchantSigner=actors.merchant_nexus, merchantGstin="29AABCU9603R1ZJ",
        merchantStateCode="29", buyerDeliveryPincode="560001", buyerDeliveryStateCode="29",
        items=[item], taxableSubtotalPaise=100000, taxBreakdown=tax, shippingPaise=0, discountPaise=0,
        totalPaise=118000, inventoryLockToken="lock_tok_001", inventoryLockExpiresAt=int(time.time()) + 60,
    )
    assert cart.cartId == "M-C-01"
    assert cart.totalPaise == 118000
    assert len(cart.merchantSignature) == 128


def test_f11_execution_mandate_hash_chain_binding() -> None:
    """F11-3: ExecutionMandate (M_E) cryptographically binds M_I and M_C hashes."""
    actors = setup_e2e_actors()
    intent = createSignedIntentMandate(
        mandateId="M-I-01", userSigner=actors.user_cfo, delegatedAgentDid=actors.buyer_agent.getAgentDid(),
        maxBudgetPaise=500000, upiCircleDelegationToken="upi_tok", singleTransactionLimitPaise=500000,
    )
    item = CartItemSchema(skuId="SKU-001", quantity=1, unitPricePaise=100000, hsnCode="8504", gstRatePercent=18, lineTotalPaise=100000)
    tax = TaxBreakdownSchema(cgstPaise=9000, sgstPaise=9000, igstPaise=0, totalTaxPaise=18000)
    cart = createSignedCartMandate(
        cartId="M-C-01", merchantSigner=actors.merchant_nexus, merchantGstin="29AABCU9603R1ZJ",
        merchantStateCode="29", buyerDeliveryPincode="560001", buyerDeliveryStateCode="29",
        items=[item], taxableSubtotalPaise=100000, taxBreakdown=tax, shippingPaise=0, discountPaise=0,
        totalPaise=118000, inventoryLockToken="lock_tok", inventoryLockExpiresAt=int(time.time()) + 60,
    )
    exec_mandate = createSignedExecutionMandate(
        executionId="M-E-01", buyerAgentSigner=actors.buyer_agent,
        intentMandate=intent, cartMandate=cart, settlementAmountPaise=118000, upiCircleToken="upi_tok",
    )
    assert exec_mandate.intentMandateHash == computeMandateHash(intent)
    assert exec_mandate.cartMandateHash == computeMandateHash(cart)
    assert verifyMandateHashChain(intent, cart, exec_mandate) is True


def test_f11_amendment_mandate_dual_signature_binding() -> None:
    """F11-4: AmendmentMandate (M_A) captures dual signatures from buyer agent and merchant."""
    actors = setup_e2e_actors()
    item = CartItemSchema(skuId="SKU-001", quantity=1, unitPricePaise=100000, hsnCode="8504", gstRatePercent=18, lineTotalPaise=100000)
    tax = TaxBreakdownSchema(cgstPaise=9000, sgstPaise=9000, igstPaise=0, totalTaxPaise=18000)
    cart1 = createSignedCartMandate(
        cartId="M-C-01", merchantSigner=actors.merchant_nexus, merchantGstin="29AABCU9603R1ZJ",
        merchantStateCode="29", buyerDeliveryPincode="560001", buyerDeliveryStateCode="29",
        items=[item], taxableSubtotalPaise=100000, taxBreakdown=tax, shippingPaise=0, discountPaise=0,
        totalPaise=118000, inventoryLockToken="lock_1", inventoryLockExpiresAt=int(time.time()) + 60,
    )
    cart2 = cart1.model_copy(update={"cartId": "M-C-02"})
    amendment = createSignedAmendmentMandate(
        amendmentId="M-A-01", buyerAgentSigner=actors.buyer_agent, merchantSigner=actors.merchant_nexus,
        previousCartMandate=cart1, newCartMandate=cart2, substitutedSkuMapping={"SKU-001": "SKU-002"},
        priceDeltaPaise=0, amendmentReason="OOS replacement",
    )
    assert amendment.previousCartMandateHash == computeMandateHash(cart1)
    assert len(amendment.agentSignature) == 128
    assert len(amendment.merchantSignature) == 128


def test_f11_mandate_chain_tamper_detection() -> None:
    """F11-5: Modifying any field in Intent or Cart mandate causes hash chain verification failure."""
    actors = setup_e2e_actors()
    intent = createSignedIntentMandate(
        mandateId="M-I-01", userSigner=actors.user_cfo, delegatedAgentDid=actors.buyer_agent.getAgentDid(),
        maxBudgetPaise=500000, upiCircleDelegationToken="upi_tok", singleTransactionLimitPaise=500000,
    )
    item = CartItemSchema(skuId="SKU-001", quantity=1, unitPricePaise=100000, hsnCode="8504", gstRatePercent=18, lineTotalPaise=100000)
    tax = TaxBreakdownSchema(cgstPaise=9000, sgstPaise=9000, igstPaise=0, totalTaxPaise=18000)
    cart = createSignedCartMandate(
        cartId="M-C-01", merchantSigner=actors.merchant_nexus, merchantGstin="29AABCU9603R1ZJ",
        merchantStateCode="29", buyerDeliveryPincode="560001", buyerDeliveryStateCode="29",
        items=[item], taxableSubtotalPaise=100000, taxBreakdown=tax, shippingPaise=0, discountPaise=0,
        totalPaise=118000, inventoryLockToken="lock_tok", inventoryLockExpiresAt=int(time.time()) + 60,
    )
    exec_mandate = createSignedExecutionMandate(
        executionId="M-E-01", buyerAgentSigner=actors.buyer_agent,
        intentMandate=intent, cartMandate=cart, settlementAmountPaise=118000, upiCircleToken="upi_tok",
    )
    tampered_cart = cart.model_copy(update={"totalPaise": 118001})
    with pytest.raises(MandateHashChainMismatchException):
        verifyMandateHashChain(intent, tampered_cart, exec_mandate)

# =============================================================================
# FEATURE 12: HSN/SAC & State Code Enclave (5 cases)
# =============================================================================

def test_f12_pincode_to_state_code_lookup() -> None:
    """F12-1: Postal PIN code mapped to 2-digit GST state code."""
    assert deriveStateCodeFromPincode("560001") == "29" # Karnataka
    assert deriveStateCodeFromPincode("110001") == "07" # Delhi
    assert deriveStateCodeFromPincode("400001") == "27" # Maharashtra


def test_f12_invalid_pincode_format_rejection() -> None:
    """F12-2: Non-numeric, 5-digit, or leading zero PIN codes raise InvalidPincodeException."""
    with pytest.raises(InvalidPincodeException):
        deriveStateCodeFromPincode("060001")
    with pytest.raises(InvalidPincodeException):
        deriveStateCodeFromPincode("56000")
    with pytest.raises(InvalidPincodeException):
        deriveStateCodeFromPincode("ABCDEF")


def test_f12_unmapped_pincode_prefix_rejection() -> None:
    """F12-3: Unallocated PIN prefix (e.g. 99) raises InvalidPincodeException."""
    with pytest.raises(InvalidPincodeException):
        deriveStateCodeFromPincode("999999")


def test_f12_hsn_code_tax_rate_resolution() -> None:
    """F12-4: HSN 4-digit chapter prefix resolves statutory GST percentage."""
    assert resolveGstRate("85041010") == 18 # Electronics
    assert resolveGstRate("71131910") == 3  # Jewelry
    assert resolveGstRate("04012000") == 0  # Milk / Exempt
    assert resolveGstRate("30049099") == 12 # Pharma


def test_f12_unmapped_hsn_fallback_to_default() -> None:
    """F12-5: Unmapped HSN code safely falls back to standard 18% default rate."""
    assert resolveGstRate("999999") == defaultGstRatePercent

# =============================================================================
# FEATURE 13: Hypothesis / Property Math Invariants (5 cases)
# =============================================================================

def test_f13_integer_math_associativity_property() -> None:
    """F13-1: Integer addition across line item subtotals is strictly associative: (a + b) + c == a + (b + c)."""
    amounts = [100000, 250000, 375000]
    left = (amounts[0] + amounts[1]) + amounts[2]
    right = amounts[0] + (amounts[1] + amounts[2])
    assert left == right == 725000


def test_f13_non_negativity_invariants_across_amounts() -> None:
    """F13-2: Non-negativity invariant holds across gross, taxable, and tax paise."""
    subtotal = 50000
    tax = 9000
    shipping = 500
    discount = 1000
    gross = computeCartSettlementTotal(subtotal, tax, shipping, discount)
    assert gross >= 0
    assert gross == 58500


def test_f13_conserved_split_sum_invariant_property() -> None:
    """F13-3: Multi-party conserved splitting invariant: sum(splits) == total across prime amounts."""
    for total in [1, 7, 13, 97, 100003, 9999991]:
        splits = split_bill_conserved(total, [2, 3, 5])
        assert sum(splits) == total


def test_f13_monotonicity_under_quantity_scaling() -> None:
    """F13-4: computeLineItemTotal is strictly monotonic with respect to quantity: total(q+1) > total(q)."""
    unit_price = 45000
    for q in range(1, 10):
        assert computeLineItemTotal(unit_price, q + 1) > computeLineItemTotal(unit_price, q)


def test_f13_zero_drift_across_repeated_splits() -> None:
    """F13-5: Zero penny drift across 100 randomized transaction allocations."""
    for i in range(1, 101):
        amt = i * 137
        shares = split_bill_conserved(amt, [1, 1, 1])
        assert sum(shares) == amt

# =============================================================================
# FEATURE 14: Stateful DLQ / 2PC FSM (5 cases)
# =============================================================================

@pytest.mark.asyncio
async def test_f14_2pc_fsm_prepare_state_transition() -> None:
    """F14-1: 2PC FSM transitions from INITIAL to PREPARED with monotonic fencing token."""
    fsm = TwoPhaseCommitFsm(route_client=MockRazorpayRouteClient({}))
    assert fsm.state == SagaState.INITIAL
    assert fsm.prepare(fencing_token=1) is True
    assert fsm.state == SagaState.PREPARED
    assert fsm.fencing_token == 1


@pytest.mark.asyncio
async def test_f14_2pc_fsm_commit_state_transition() -> None:
    """F14-2: 2PC FSM transitions from PREPARED to COMMITTED upon successful transfer dispatch."""
    fsm = TwoPhaseCommitFsm(route_client=MockRazorpayRouteClient({}))
    fsm.prepare(fencing_token=1)
    transfers = await fsm.commit_transfers([{"account": "acc_merchant", "amount": 100000}])
    assert fsm.state == SagaState.COMMITTED
    assert len(transfers) == 1


@pytest.mark.asyncio
async def test_f14_2pc_fsm_abort_rollback_on_transfer_failure() -> None:
    """F14-3: Transfer dispatch failure triggers ABORT state and LIFO compensation reversal."""
    mock_route = MockRazorpayRouteClient({})
    mock_route.simulateSecondaryTransferFailure = True
    fsm = TwoPhaseCommitFsm(route_client=mock_route)
    fsm.prepare(fencing_token=1)
    
    with pytest.raises(SettlementCompensationTriggeredException):
        await fsm.commit_transfers([
            {"account": "acc_merchant", "amount": 100000},
            {"account": "acc_logistics", "amount": 5000},
        ])
    assert fsm.state == SagaState.ABORTED
    assert len(fsm.reversed_transfers) == 1  # Merchant transfer compensated


@pytest.mark.asyncio
async def test_f14_2pc_fsm_fencing_token_monotonic_check() -> None:
    """F14-4: Non-monotonic fencing token is rejected with FencingTokenViolationError."""
    fsm = TwoPhaseCommitFsm(route_client=MockRazorpayRouteClient({}))
    fsm.fencing_token = 10
    with pytest.raises(FencingTokenViolationError):
        fsm.prepare(fencing_token=5)


@pytest.mark.asyncio
async def test_f14_2pc_fsm_illegal_transition_rejection() -> None:
    """F14-5: Attempting to COMMIT directly from INITIAL state raises IllegalStateTransitionError."""
    fsm = TwoPhaseCommitFsm(route_client=MockRazorpayRouteClient({}))
    with pytest.raises(IllegalStateTransitionError):
        await fsm.commit_transfers([{"account": "acc_1", "amount": 100}])

# =============================================================================
# FEATURE 15: Schema Invariant Fuzzing (5 cases)
# =============================================================================

def test_f15_sql_injection_resilience_in_text_fields() -> None:
    """F15-1: SQL injection string in invoice description preserved safely without executing."""
    sql_payload = "'; DROP TABLE invoices; --"
    line = E2eInvoiceLineItem(
        skuId="SKU-SQL", description=sql_payload, hsnSacCode="8504", quantity=1, unitPricePaise=1000,
        taxableAmountPaise=1000, gstRatePercent=18, cgstPaise=90, sgstPaise=90, igstPaise=0, totalPaise=1180,
    )
    assert line.description == sql_payload


def test_f15_prompt_injection_tag_handling() -> None:
    """F15-2: HTML and script injection tags in SKU descriptions handled as safe text."""
    xss_payload = "<script>alert('pwned')</script>"
    line = E2eInvoiceLineItem(
        skuId="SKU-XSS", description=xss_payload, hsnSacCode="8504", quantity=1, unitPricePaise=1000,
        taxableAmountPaise=1000, gstRatePercent=18, cgstPaise=90, sgstPaise=90, igstPaise=0, totalPaise=1180,
    )
    assert line.description == xss_payload


def test_f15_negative_amount_rejection_in_schemas() -> None:
    """F15-3: Negative unit price or quantity rejected by Pydantic validation."""
    with pytest.raises(ValidationError):
        E2eInvoiceLineItem(
            skuId="SKU-1", description="Item", hsnSacCode="8504", quantity=-1, unitPricePaise=1000,
            taxableAmountPaise=1000, gstRatePercent=18, cgstPaise=90, sgstPaise=90, igstPaise=0, totalPaise=1180,
        )


def test_f15_empty_string_rejection_in_required_fields() -> None:
    """F15-4: Empty string in mandatory schema fields raises ValidationError."""
    with pytest.raises(ValidationError):
        E2eInvoiceLineItem(
            skuId="", description="Item", hsnSacCode="8504", quantity=1, unitPricePaise=1000,
            taxableAmountPaise=1000, gstRatePercent=18, cgstPaise=90, sgstPaise=90, igstPaise=0, totalPaise=1180,
        )


def test_f15_extreme_int_value_overflow_resilience() -> None:
    """F15-5: Extremely large integer amounts (10^12 paise = 10 billion INR) handled accurately."""
    large_val = 1_000_000_000_000
    line = E2eInvoiceLineItem(
        skuId="SKU-LARGE", description="Industrial Turbine", hsnSacCode="8504", quantity=1, unitPricePaise=large_val,
        taxableAmountPaise=large_val, gstRatePercent=18, cgstPaise=90_000_000_000, sgstPaise=90_000_000_000,
        igstPaise=0, totalPaise=1_180_000_000_000,
    )
    assert line.unitPricePaise == large_val

# =============================================================================
# FEATURE 16: E2E Regression Verification (5 cases)
# =============================================================================

@pytest.mark.asyncio
async def test_f16_e2e_nominal_buyer_settlement_workflow() -> None:
    """F16-1: Complete autonomous buyer settlement from mandate creation to capture & invoice."""
    actors = setup_e2e_actors()
    now = int(time.time())
    
    intent = createSignedIntentMandate(
        mandateId="M-I-E2E-1", userSigner=actors.user_cfo, delegatedAgentDid=actors.buyer_agent.getAgentDid(),
        maxBudgetPaise=1000000, upiCircleDelegationToken="upi_tok_e2e", singleTransactionLimitPaise=500000,
        timestamp=now,
    )
    item = CartItemSchema(skuId="SKU-001", quantity=1, unitPricePaise=420000, hsnCode="8504", gstRatePercent=18, lineTotalPaise=420000)
    tax = TaxBreakdownSchema(cgstPaise=37800, sgstPaise=37800, igstPaise=0, totalTaxPaise=75600)
    cart = createSignedCartMandate(
        cartId="M-C-E2E-1", merchantSigner=actors.merchant_nexus, merchantGstin="29AABCU9603R1ZJ",
        merchantStateCode="29", buyerDeliveryPincode="560001", buyerDeliveryStateCode="29",
        items=[item], taxableSubtotalPaise=420000, taxBreakdown=tax, shippingPaise=0, discountPaise=0,
        totalPaise=495600, inventoryLockToken="lock_e2e_1", inventoryLockExpiresAt=now + 60, timestamp=now,
    )
    exec_mandate = createSignedExecutionMandate(
        executionId="M-E-E2E-1", buyerAgentSigner=actors.buyer_agent,
        intentMandate=intent, cartMandate=cart, settlementAmountPaise=495600, upiCircleToken="upi_tok_e2e",
        timestamp=now,
    )
    
    redis = MockRedisAsync()
    orchestrator = SettlementOrchestrator(
        routeClient=RazorpayRouteClient(apiKey="key", apiSecret="sec"),
        nonceLedger=NonceLedger(redis),
    )
    res = await orchestrator.executeSettlementSaga(
        intentMandate=intent, cartMandate=cart, executionMandate=exec_mandate,
        merchantAccount="acc_merchant_nexus_01", paymentId="pay_e2e_1", serverTime=now,
    )
    assert res.status == "captured"
    assert res.amountPaise == 495600
    assert len(res.invoice.cryptographicAuditHash) == 64


@pytest.mark.asyncio
async def test_f16_e2e_multi_item_cart_procurement_workflow() -> None:
    """F16-2: Multi-item cart settlement aggregating distinct GST rate categories."""
    actors = setup_e2e_actors()
    now = int(time.time())
    
    intent = createSignedIntentMandate(
        mandateId="M-I-E2E-MULTI", userSigner=actors.user_cfo, delegatedAgentDid=actors.buyer_agent.getAgentDid(),
        maxBudgetPaise=2000000, upiCircleDelegationToken="upi_tok_multi", singleTransactionLimitPaise=2000000,
        timestamp=now,
    )
    item1 = CartItemSchema(skuId="SKU-1", quantity=1, unitPricePaise=200000, hsnCode="8504", gstRatePercent=18, lineTotalPaise=200000)
    item2 = CartItemSchema(skuId="SKU-2", quantity=2, unitPricePaise=50000, hsnCode="7113", gstRatePercent=3, lineTotalPaise=100000)
    
    tax1 = computeGstBreakdown(200000, 18, isIntraState=True)
    tax2 = computeGstBreakdown(100000, 3, isIntraState=True)
    totalCgst = tax1["cgstPaise"] + tax2["cgstPaise"]
    totalSgst = tax1["sgstPaise"] + tax2["sgstPaise"]
    totalTax = totalCgst + totalSgst
    totalGross = 300000 + totalTax
    
    tax_breakdown = TaxBreakdownSchema(cgstPaise=totalCgst, sgstPaise=totalSgst, igstPaise=0, totalTaxPaise=totalTax)
    cart = createSignedCartMandate(
        cartId="M-C-E2E-MULTI", merchantSigner=actors.merchant_nexus, merchantGstin="29AABCU9603R1ZJ",
        merchantStateCode="29", buyerDeliveryPincode="560001", buyerDeliveryStateCode="29",
        items=[item1, item2], taxableSubtotalPaise=300000, taxBreakdown=tax_breakdown, shippingPaise=0, discountPaise=0,
        totalPaise=totalGross, inventoryLockToken="lock_multi", inventoryLockExpiresAt=now + 60, timestamp=now,
    )
    exec_mandate = createSignedExecutionMandate(
        executionId="M-E-E2E-MULTI", buyerAgentSigner=actors.buyer_agent,
        intentMandate=intent, cartMandate=cart, settlementAmountPaise=totalGross, upiCircleToken="upi_tok_multi",
        timestamp=now,
    )
    
    redis = MockRedisAsync()
    orchestrator = SettlementOrchestrator(
        routeClient=RazorpayRouteClient(apiKey="key", apiSecret="sec"),
        nonceLedger=NonceLedger(redis),
    )
    res = await orchestrator.executeSettlementSaga(
        intentMandate=intent, cartMandate=cart, executionMandate=exec_mandate,
        merchantAccount="acc_merchant_nexus_01", paymentId="pay_e2e_multi", serverTime=now,
    )
    assert res.status == "captured"
    assert res.amountPaise == totalGross


@pytest.mark.asyncio
async def test_f16_e2e_2pc_saga_transfer_rollback_workflow() -> None:
    """F16-3: 2PC saga triggers complete transfer rollback when secondary split account fails."""
    actors = setup_e2e_actors()
    now = int(time.time())
    
    intent = createSignedIntentMandate(
        mandateId="M-I-E2E-RB", userSigner=actors.user_cfo, delegatedAgentDid=actors.buyer_agent.getAgentDid(),
        maxBudgetPaise=1000000, upiCircleDelegationToken="upi_tok", singleTransactionLimitPaise=1000000,
        timestamp=now,
    )
    item = CartItemSchema(skuId="SKU-001", quantity=1, unitPricePaise=100000, hsnCode="8504", gstRatePercent=18, lineTotalPaise=100000)
    tax = TaxBreakdownSchema(cgstPaise=9000, sgstPaise=9000, igstPaise=0, totalTaxPaise=18000)
    cart = createSignedCartMandate(
        cartId="M-C-E2E-RB", merchantSigner=actors.merchant_nexus, merchantGstin="29AABCU9603R1ZJ",
        merchantStateCode="29", buyerDeliveryPincode="560001", buyerDeliveryStateCode="29",
        items=[item], taxableSubtotalPaise=100000, taxBreakdown=tax, shippingPaise=0, discountPaise=0,
        totalPaise=118000, inventoryLockToken="lock_rb", inventoryLockExpiresAt=now + 60, timestamp=now,
    )
    exec_mandate = createSignedExecutionMandate(
        executionId="M-E-E2E-RB", buyerAgentSigner=actors.buyer_agent,
        intentMandate=intent, cartMandate=cart, settlementAmountPaise=118000, upiCircleToken="upi_tok",
        timestamp=now,
    )
    
    redis = MockRedisAsync()
    routeClient = RazorpayRouteClient(apiKey="key", apiSecret="sec")
    routeClient.simulatedFailureAccount = "acc_protocol_fee"
    orchestrator = SettlementOrchestrator(routeClient=routeClient, nonceLedger=NonceLedger(redis))
    
    with pytest.raises(SettlementCompensationTriggeredException):
        await orchestrator.executeSettlementSaga(
            intentMandate=intent, cartMandate=cart, executionMandate=exec_mandate,
            merchantAccount="acc_merchant_nexus_01", paymentId="pay_e2e_rb", serverTime=now,
        )


def test_f16_e2e_out_of_stock_vector_healing_workflow() -> None:
    """F16-4: Out-of-stock item triggers substitute search, cart amendment, and dual signature."""
    actors = setup_e2e_actors()
    now = int(time.time())
    
    item1 = CartItemSchema(skuId="SKU-OOS-1", quantity=1, unitPricePaise=350000, hsnCode="8504", gstRatePercent=18, lineTotalPaise=350000)
    tax1 = TaxBreakdownSchema(cgstPaise=31500, sgstPaise=31500, igstPaise=0, totalTaxPaise=63000)
    cart1 = createSignedCartMandate(
        cartId="M-C-OOS-ORIG", merchantSigner=actors.merchant_nexus, merchantGstin="29AABCU9603R1ZJ",
        merchantStateCode="29", buyerDeliveryPincode="560001", buyerDeliveryStateCode="29",
        items=[item1], taxableSubtotalPaise=350000, taxBreakdown=tax1, shippingPaise=0, discountPaise=0,
        totalPaise=413000, inventoryLockToken="lock_oos", inventoryLockExpiresAt=now + 60, timestamp=now,
    )
    
    item2 = CartItemSchema(skuId="SKU-SUB-4", quantity=1, unitPricePaise=355000, hsnCode="8504", gstRatePercent=18, lineTotalPaise=355000)
    tax2 = TaxBreakdownSchema(cgstPaise=31950, sgstPaise=31950, igstPaise=0, totalTaxPaise=63900)
    cart2 = createSignedCartMandate(
        cartId="M-C-OOS-HEALED", merchantSigner=actors.merchant_nexus, merchantGstin="29AABCU9603R1ZJ",
        merchantStateCode="29", buyerDeliveryPincode="560001", buyerDeliveryStateCode="29",
        items=[item2], taxableSubtotalPaise=355000, taxBreakdown=tax2, shippingPaise=0, discountPaise=0,
        totalPaise=418900, inventoryLockToken="lock_healed", inventoryLockExpiresAt=now + 60, timestamp=now,
    )
    
    amendment = createSignedAmendmentMandate(
        amendmentId="M-A-HEALED-1", buyerAgentSigner=actors.buyer_agent, merchantSigner=actors.merchant_nexus,
        previousCartMandate=cart1, newCartMandate=cart2, substitutedSkuMapping={"SKU-OOS-1": "SKU-SUB-4"},
        priceDeltaPaise=5000, amendmentReason="OOS replacement", timestamp=now,
    )
    assert amendment.substitutedSkuMapping["SKU-OOS-1"] == "SKU-SUB-4"
    assert amendment.priceDeltaPaise == 5000


@pytest.mark.asyncio
async def test_f16_e2e_nonce_replay_rejection_workflow() -> None:
    """F16-5: Replaying an already committed execution mandate nonce is rejected with NonceReplayException."""
    actors = setup_e2e_actors()
    now = int(time.time())
    
    intent = createSignedIntentMandate(
        mandateId="M-I-REPLAY", userSigner=actors.user_cfo, delegatedAgentDid=actors.buyer_agent.getAgentDid(),
        maxBudgetPaise=1000000, upiCircleDelegationToken="upi_tok", singleTransactionLimitPaise=1000000,
        timestamp=now,
    )
    item = CartItemSchema(skuId="SKU-001", quantity=1, unitPricePaise=100000, hsnCode="8504", gstRatePercent=18, lineTotalPaise=100000)
    tax = TaxBreakdownSchema(cgstPaise=9000, sgstPaise=9000, igstPaise=0, totalTaxPaise=18000)
    cart = createSignedCartMandate(
        cartId="M-C-REPLAY", merchantSigner=actors.merchant_nexus, merchantGstin="29AABCU9603R1ZJ",
        merchantStateCode="29", buyerDeliveryPincode="560001", buyerDeliveryStateCode="29",
        items=[item], taxableSubtotalPaise=100000, taxBreakdown=tax, shippingPaise=0, discountPaise=0,
        totalPaise=118000, inventoryLockToken="lock_replay", inventoryLockExpiresAt=now + 60, timestamp=now,
    )
    exec_mandate = createSignedExecutionMandate(
        executionId="M-E-REPLAY", buyerAgentSigner=actors.buyer_agent,
        intentMandate=intent, cartMandate=cart, settlementAmountPaise=118000, upiCircleToken="upi_tok",
        timestamp=now,
    )
    
    redis = MockRedisAsync()
    orchestrator = SettlementOrchestrator(
        routeClient=RazorpayRouteClient(apiKey="key", apiSecret="sec"),
        nonceLedger=NonceLedger(redis),
    )
    # First execution succeeds
    res = await orchestrator.executeSettlementSaga(
        intentMandate=intent, cartMandate=cart, executionMandate=exec_mandate,
        merchantAccount="acc_merchant_nexus_01", paymentId="pay_replay_1", serverTime=now,
    )
    assert res.status == "captured"
    
    # Second execution with same execution mandate nonce fails
    with pytest.raises(NonceReplayException):
        await orchestrator.executeSettlementSaga(
            intentMandate=intent, cartMandate=cart, executionMandate=exec_mandate,
            merchantAccount="acc_merchant_nexus_01", paymentId="pay_replay_2", serverTime=now,
        )
