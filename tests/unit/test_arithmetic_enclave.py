"""Unit test suite for Canonical Pure Deterministic Arithmetic Enclave (M1).

Validates 21 statutory edge cases, zero-float guarantees, conserved remainder bill splitting,
route settlement overdraft protections, and cross-package facade delegation.
"""

from decimal import Decimal
import pytest

from razoragentMesh.packages.mandateEngine.verification.arithmeticEnclave import (
    ArithmeticDriftException,
    GstBreakdown,
    RouteSplitResult,
    SpendingCapResult,
    allocate_cart_discount_conserved,
    calculate_gst,
    calculate_route_splits,
    compute_cart_settlement_total,
    compute_line_item_total,
    compute_tcs_withholding,
    evaluate_spending_cap,
    normalize_inr_to_paise,
    split_bill_conserved,
    validate_integer_paise,
)
from razoragentMesh.packages.x402Gateway.src.constants.arithmeticUtils import (
    calculate_gst as gw_calculate_gst,
    split_bill_conserved as gw_split_bill_conserved,
    validateIntegerPaise as gw_validate_int,
)
from razoragentMesh.packages.merchantApi.src.catalog.priceNormalizer import (
    normalizeInrToPaise as merchant_normalize_inr,
)


def test_edge_case_01_bool_rejection() -> None:
    """EC-01: validate_integer_paise rejects bool values."""
    with pytest.raises(ArithmeticDriftException):
        validate_integer_paise(True, "is_active")
    with pytest.raises(ArithmeticDriftException):
        validate_integer_paise(False, "flag")


def test_edge_case_02_float_rejection() -> None:
    """EC-02: validate_integer_paise rejects float values."""
    with pytest.raises(ArithmeticDriftException):
        validate_integer_paise(1976.501, "price")


def test_edge_case_03_string_rejection() -> None:
    """EC-03: validate_integer_paise rejects string values."""
    with pytest.raises(ArithmeticDriftException):
        validate_integer_paise("100", "unitPrice")


def test_edge_case_04_negative_rejection() -> None:
    """EC-04: validate_integer_paise rejects negative values."""
    with pytest.raises(ArithmeticDriftException):
        validate_integer_paise(-50, "amount")


def test_edge_case_05_max_bound_rejection() -> None:
    """EC-05: validate_integer_paise rejects values exceeding max bound."""
    with pytest.raises(ArithmeticDriftException):
        validate_integer_paise(2**64, "large_amount")
    with pytest.raises(ArithmeticDriftException):
        validate_integer_paise(10**15, "large_amount", max_bound=10**14)


def test_edge_case_06_gst_5_percent_intra_odd_penny_conservation() -> None:
    """EC-06: 5% Intra-state GST on 101 paise conserves pennies (CGST=2, SGST=3, total=5)."""
    gst = calculate_gst(101, 500, "29", "29")
    assert gst.total_tax_paise == 5
    assert gst.cgst_paise == 2
    assert gst.sgst_paise == 3
    assert gst.igst_paise == 0
    assert gst["cgstPaise"] + gst["sgstPaise"] == gst["totalTaxPaise"]


def test_edge_case_07_gst_5_percent_intra_parity() -> None:
    """EC-07: 5% Intra-state GST on 33,333 paise (CGST=833, SGST=833, total=1666)."""
    gst = calculate_gst(33333, 500, "29", "29")
    assert gst.total_tax_paise == 1666
    assert gst.cgst_paise == 833
    assert gst.sgst_paise == 833
    assert gst.igst_paise == 0


def test_edge_case_08_gst_18_percent_inter_state() -> None:
    """EC-08: 18% Inter-state GST on 77,777 paise (IGST=13999, CGST=0, SGST=0)."""
    gst = calculate_gst(77777, 1800, "27", "29")
    assert gst.total_tax_paise == 13999
    assert gst.cgst_paise == 0
    assert gst.sgst_paise == 0
    assert gst.igst_paise == 13999


def test_edge_case_09_gst_0_25_percent_fractional_slab() -> None:
    """EC-09: 0.25% (25 bps) diamond slab on 100,000 paise."""
    gst = calculate_gst(100000, 25, "29", "29")
    assert gst.total_tax_paise == 250
    assert gst.cgst_paise + gst.sgst_paise == 250
    assert gst.igst_paise == 0


def test_edge_case_10_gst_zero_rate_boundary() -> None:
    """EC-10: 0% tax rate on 500,000 paise returns exact 0."""
    gst = calculate_gst(500000, 0, "29", "29")
    assert gst.total_tax_paise == 0
    assert gst.cgst_paise == 0
    assert gst.sgst_paise == 0
    assert gst.igst_paise == 0


def test_edge_case_11_split_bill_zero_amount() -> None:
    """EC-11: split_bill_conserved with 0 total paise returns list of zeroes."""
    res = split_bill_conserved(0, [1, 2, 3])
    assert res == [0, 0, 0]


def test_edge_case_12_split_bill_1_paise_tie_breaking() -> None:
    """EC-12: split_bill_conserved with 1 paise among 3 equal ratios allocates to index 0."""
    res = split_bill_conserved(1, [1, 1, 1])
    assert res == [1, 0, 0]
    assert sum(res) == 1


def test_edge_case_13_split_bill_2_paise_among_three() -> None:
    """EC-13: split_bill_conserved with 2 paise among 3 equal ratios."""
    res = split_bill_conserved(2, [1, 1, 1])
    assert res == [1, 1, 0]
    assert sum(res) == 2


def test_edge_case_14_split_bill_largest_remainder_distribution() -> None:
    """EC-14: 100 paise split by [3, 7, 11] preserves exact 100 paise."""
    res = split_bill_conserved(100, [3, 7, 11])
    assert res == [14, 33, 53]
    assert sum(res) == 100


def test_edge_case_15_split_bill_prime_amount_conservation() -> None:
    """EC-15: Large prime total 1,000,000,007 split across primes [13, 17, 19, 23]."""
    total = 1000000007
    res = split_bill_conserved(total, [13, 17, 19, 23])
    assert sum(res) == total
    assert all(x > 0 for x in res)


def test_edge_case_16_split_bill_zero_weight_participant() -> None:
    """EC-16: Zero-weight participant receives exactly 0."""
    res = split_bill_conserved(100, [0, 5, 0])
    assert res == [0, 100, 0]
    assert sum(res) == 100


def test_edge_case_17_calculate_route_splits_normal() -> None:
    """EC-17: Route split deduction: 10,000 order, 200 bps comm (200p), 50p flat, 500p ship."""
    split = calculate_route_splits(10000, 200, 50, shipping_paise=500)
    assert split.order_paise == 10000
    assert split.commission_paise == 200
    assert split.flat_fee_paise == 50
    assert split.protocolFeePaise == 250
    assert split.logisticsAmountPaise == 500
    assert split.totalFeePaise == 750
    assert split.merchant_paise == 9250
    assert split.merchant_paise + split.totalFeePaise == 10000


def test_edge_case_18_calculate_route_splits_overdraft() -> None:
    """EC-18: Overdraft check raises ArithmeticDriftException when deductions exceed order."""
    with pytest.raises(ArithmeticDriftException):
        calculate_route_splits(500, 1000, 100, shipping_paise=600)


def test_edge_case_19_normalize_inr_string_to_paise() -> None:
    """EC-19: normalize_inr_to_paise converts decimal strings properly."""
    assert normalize_inr_to_paise("1976.50") == 197650
    assert normalize_inr_to_paise("0.05") == 5
    assert normalize_inr_to_paise(Decimal("1976.50")) == 197650


def test_edge_case_20_normalize_inr_float_rejection() -> None:
    """EC-20: normalize_inr_to_paise strictly rejects float inputs."""
    with pytest.raises(ArithmeticDriftException):
        normalize_inr_to_paise(1976.50)


def test_edge_case_21_allocate_cart_discount_conserved() -> None:
    """EC-21: Cart discount allocation preserves sum of line item discounts."""
    items = [33333, 55555, 77777]
    discounts = allocate_cart_discount_conserved(items, 15000)
    assert sum(discounts) == 15000
    net_items = [items[i] - discounts[i] for i in range(3)]
    assert sum(net_items) == sum(items) - 15000


def test_spending_cap_evaluation() -> None:
    """Validates spending cap logic and single transaction limit enforcement."""
    r1 = evaluate_spending_cap(10000, 20000, 50000)
    assert r1.allowed is True
    assert r1.remaining_daily_paise == 20000

    r2 = evaluate_spending_cap(40000, 20000, 50000)
    assert r2.allowed is False
    assert "exceeds spending cap" in r2.violation_reason

    r3 = evaluate_spending_cap(10000, 20000, 50000, single_tx_limit_paise=15000)
    assert r3.allowed is False
    assert "exceeds single transaction limit" in r3.violation_reason


def test_cross_package_facade_delegation() -> None:
    """Validates that x402Gateway and merchantApi facades delegate cleanly."""
    assert gw_validate_int(1000, "gw_field") == 1000
    gst = gw_calculate_gst(10000, 1800, "29", "29")
    assert gst.total_tax_paise == 1800
    shares = gw_split_bill_conserved(100, [1, 1])
    assert shares == [50, 50]
    assert merchant_normalize_inr("499.00") == 49900
