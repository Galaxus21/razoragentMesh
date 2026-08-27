"""Milestone 1 Empirical Challenger Adversarial Stress Test Suite.

Adversarial validation covering:
1. 10,000 randomized split_bill_conserved trials (fund conservation invariant).
2. Comprehensive float/NaN/infinity/boolean injection across all arithmetic enclave entry points.
3. Statutory GST boundary rate fuzzing (0-10000 bps, fractional slabs, intra/inter-state invariants).
4. Route settlement fee deductions, zero-drift invariants, and overdraft boundaries.
5. Spending cap boundary transitions and single transaction limits.
6. Currency normalization with half-up rounding, strings, and float rejection.
7. Cart discount allocation conservation and non-negative line item invariant.
"""

from decimal import Decimal
import math
import random
from typing import Any, List
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
    computeGstBreakdown,
    evaluate_spending_cap,
    normalize_inr_to_paise,
    split_bill_conserved,
    validate_integer_paise,
)


class TestSplitBillConservedAdversarial:
    """Stress tests for Hare-Niemeyer Largest Remainder bill splitting."""

    def test_randomized_fund_conservation_10k_runs(self) -> None:
        """Asserts sum(shares) == total across 10,000 randomized split configurations."""
        rng = random.Random(42)

        for _ in range(10_000):
            # Vary participant count from 1 to 150
            num_participants = rng.randint(1, 150)
            
            # Vary total amount from 0 to 10^9 paise (10 million INR)
            total_paise = rng.choice([
                0, 1, 2, 3, 5, 7, 11, 13, 99, 100, 101, 333, 999, 1000,
                rng.randint(0, 100),
                rng.randint(100, 10_000),
                rng.randint(10_000, 1_000_000),
                rng.randint(1_000_000, 1_000_000_000),
            ])

            # Vary ratio distributions
            distribution_type = rng.choice(["uniform", "sparse_zeros", "geometric", "primes", "equal"])
            if distribution_type == "equal":
                ratios = [1] * num_participants
            elif distribution_type == "sparse_zeros":
                ratios = [rng.randint(0, 50) for _ in range(num_participants)]
                # Ensure at least one positive weight
                if sum(ratios) == 0:
                    ratios[0] = 1
            elif distribution_type == "geometric":
                ratios = [int(1.5 ** (i % 15)) for i in range(num_participants)]
            elif distribution_type == "primes":
                primes = [2, 3, 5, 7, 11, 13, 17, 19, 23, 29, 31, 37, 41, 43, 47]
                ratios = [rng.choice(primes) for _ in range(num_participants)]
            else:
                ratios = [rng.randint(1, 1000) for _ in range(num_participants)]

            shares = split_bill_conserved(total_paise, ratios)

            # Fund Conservation Invariant
            assert sum(shares) == total_paise, f"Conservation breached: sum={sum(shares)} != total={total_paise}"
            assert len(shares) == num_participants
            assert all(s >= 0 for s in shares), f"Negative share detected: {shares}"

            # Zero-weight participant invariant: zero ratio must yield zero share
            for r, s in zip(ratios, shares):
                if r == 0:
                    assert s == 0, f"Zero-weight participant received non-zero share: ratio={r}, share={s}"

    def test_extreme_participant_scale(self) -> None:
        """Tests 500 participants with 1 paise, 499 paise, and 1,000,000 paise."""
        n = 500
        ratios = [1] * n

        # 1 paise among 500 participants -> index 0 gets 1 paise, all others 0
        shares_1 = split_bill_conserved(1, ratios)
        assert sum(shares_1) == 1
        assert shares_1[0] == 1
        assert sum(shares_1[1:]) == 0

        # 499 paise among 500 participants -> indices 0..498 get 1 paise, index 499 gets 0
        shares_499 = split_bill_conserved(499, ratios)
        assert sum(shares_499) == 499
        assert all(s == 1 for s in shares_499[:499])
        assert shares_499[499] == 0

        # Prime total among 500 participants with varied ratios
        prime_total = 1_000_000_007
        varied_ratios = [(i % 17) + 1 for i in range(n)]
        shares_prime = split_bill_conserved(prime_total, varied_ratios)
        assert sum(shares_prime) == prime_total
        assert all(s > 0 for s in shares_prime)

    def test_invalid_ratios_rejection(self) -> None:
        """Tests that invalid ratio configurations raise ArithmeticDriftException."""
        with pytest.raises(ArithmeticDriftException):
            split_bill_conserved(100, [])
        with pytest.raises(ArithmeticDriftException):
            split_bill_conserved(100, [0, 0, 0])
        with pytest.raises(ArithmeticDriftException):
            split_bill_conserved(100, [-1, 5, 10])
        with pytest.raises(ArithmeticDriftException):
            split_bill_conserved(100, [1, 2.5, 3])  # type: ignore
        with pytest.raises(ArithmeticDriftException):
            split_bill_conserved(-100, [1, 2, 3])


class TestFloatInjectionRejectionMatrix:
    """Empirical verification that floats, NaNs, infinities, booleans, and non-ints are strictly rejected."""

    POISON_INPUTS = [
        10.5, 0.0, -0.0, -10.5, 1e-6, 1e12,
        float("inf"), float("-inf"), float("nan"),
        True, False,
        "100", "100.5",
        Decimal("100"), Decimal("100.5"),
        None, [], {}, object(),
    ]

    def test_validate_integer_paise_poison_matrix(self) -> None:
        """Asserts validate_integer_paise rejects every poison input."""
        for poison in self.POISON_INPUTS:
            with pytest.raises(ArithmeticDriftException):
                validate_integer_paise(poison, "poison_field")

    def test_compute_line_item_total_poison_matrix(self) -> None:
        """Asserts compute_line_item_total rejects poison inputs in price or qty."""
        for poison in self.POISON_INPUTS:
            with pytest.raises(ArithmeticDriftException):
                compute_line_item_total(unit_price_paise=poison, quantity=5)  # type: ignore
            with pytest.raises(ArithmeticDriftException):
                compute_line_item_total(unit_price_paise=100, quantity=poison)  # type: ignore

    def test_calculate_gst_poison_matrix(self) -> None:
        """Asserts calculate_gst rejects poison inputs in base or tax rate."""
        for poison in self.POISON_INPUTS:
            with pytest.raises(ArithmeticDriftException):
                calculate_gst(base_amount_paise=poison, tax_rate_bps=1800, supplier_state_code="29", pos_state_code="29")  # type: ignore
            with pytest.raises(ArithmeticDriftException):
                calculate_gst(base_amount_paise=10000, tax_rate_bps=poison, supplier_state_code="29", pos_state_code="29")  # type: ignore

    def test_calculate_route_splits_poison_matrix(self) -> None:
        """Asserts calculate_route_splits rejects poison inputs in order, commission, flat fee, shipping."""
        for poison in self.POISON_INPUTS:
            with pytest.raises(ArithmeticDriftException):
                calculate_route_splits(order_paise=poison, commission_bps=200, flat_fee_paise=50)  # type: ignore
            with pytest.raises(ArithmeticDriftException):
                calculate_route_splits(order_paise=10000, commission_bps=poison, flat_fee_paise=50)  # type: ignore
            with pytest.raises(ArithmeticDriftException):
                calculate_route_splits(order_paise=10000, commission_bps=200, flat_fee_paise=poison)  # type: ignore

    def test_evaluate_spending_cap_poison_matrix(self) -> None:
        """Asserts evaluate_spending_cap rejects poison inputs in cumulative, delta, or cap."""
        for poison in self.POISON_INPUTS:
            with pytest.raises(ArithmeticDriftException):
                evaluate_spending_cap(cumulative_paise=poison, delta_paise=1000, cap_paise=5000)  # type: ignore
            with pytest.raises(ArithmeticDriftException):
                evaluate_spending_cap(cumulative_paise=1000, delta_paise=poison, cap_paise=5000)  # type: ignore
            with pytest.raises(ArithmeticDriftException):
                evaluate_spending_cap(cumulative_paise=1000, delta_paise=1000, cap_paise=poison)  # type: ignore

    def test_normalize_inr_to_paise_poison_matrix(self) -> None:
        """Asserts normalize_inr_to_paise rejects float, bool, invalid strings, negative numbers."""
        float_poisons = [10.5, 0.0, -0.0, -10.5, float("inf"), float("-inf"), float("nan")]
        for poison in float_poisons:
            with pytest.raises(ArithmeticDriftException):
                normalize_inr_to_paise(poison)  # type: ignore

        with pytest.raises(ArithmeticDriftException):
            normalize_inr_to_paise(True)  # type: ignore
        with pytest.raises(ArithmeticDriftException):
            normalize_inr_to_paise(False)  # type: ignore
        with pytest.raises(ArithmeticDriftException):
            normalize_inr_to_paise("invalid_currency")
        with pytest.raises(ArithmeticDriftException):
            normalize_inr_to_paise("-100.50")
        with pytest.raises(ArithmeticDriftException):
            normalize_inr_to_paise(Decimal("-50.00"))


class TestGstStatutoryPrecisionAndSlabs:
    """Stress testing GST calculations across statutory slabs, basis points, and state boundaries."""

    SLABS_BPS = [
        0,      # 0% Exempted
        1,      # 0.01% Ultra-fine slab
        25,     # 0.25% Diamonds/Precious stones
        150,    # 1.50% Rough gemstones
        300,    # 3.00% Gold / Bullion
        500,    # 5.00% Essential goods
        600,    # 6.00% Brick kiln / Special
        1200,   # 12.00% Standard slab lower
        1800,   # 18.00% Standard slab upper
        2800,   # 28.00% Demerit / Luxury
        10000,  # 100.00% Theoretical max
    ]

    def test_gst_conservation_fuzzing_5k(self) -> None:
        """Tests GST conservation across 5,000 randomized amounts and statutory slabs."""
        rng = random.Random(12345)

        for _ in range(5_000):
            base = rng.choice([
                0, 1, 2, 3, 7, 13, 99, 101, 333, 999, 1976501,
                rng.randint(0, 100_000),
                rng.randint(100_000, 10_000_000),
            ])
            rate_bps = rng.choice(self.SLABS_BPS)
            is_intra = rng.choice([True, False])
            rounding = rng.choice(["FLOOR", "HALF_UP"])

            supp_state = "29"
            pos_state = "29" if is_intra else "27"

            gst = calculate_gst(base, rate_bps, supp_state, pos_state, rounding_mode=rounding)

            if is_intra:
                # Fund conservation invariant: CGST + SGST == total_tax
                assert gst.cgst_paise + gst.sgst_paise == gst.total_tax_paise
                assert gst.igst_paise == 0
                assert gst.is_intra_state is True
                assert gst.cgst_paise >= 0
                assert gst.sgst_paise >= 0

                # Parity invariant for even basis points
                if rate_bps % 2 == 0:
                    assert abs(gst.sgst_paise - gst.cgst_paise) <= 1
            else:
                # Inter-state invariant: IGST == total_tax
                assert gst.igst_paise == gst.total_tax_paise
                assert gst.cgst_paise == 0
                assert gst.sgst_paise == 0
                assert gst.is_intra_state is False

    def test_state_code_whitespace_resilience(self) -> None:
        """Tests that state codes with spaces are trimmed and compared correctly."""
        gst_intra = calculate_gst(10000, 1800, " 29 ", "29\t")
        assert gst_intra.is_intra_state is True
        assert gst_intra.cgst_paise == 900
        assert gst_intra.sgst_paise == 900
        assert gst_intra.igst_paise == 0

        gst_inter = calculate_gst(10000, 1800, " 29 ", " 27 ")
        assert gst_inter.is_intra_state is False
        assert gst_inter.igst_paise == 1800


class TestRouteSplitsOverdraftAndConservation:
    """Stress tests for route fee deductions, boundary conditions, and overdraft protection."""

    def test_route_splits_conservation_randomized_5k(self) -> None:
        """Asserts merchantNetPaise + totalFeePaise == orderPaise across 5,000 cases."""
        rng = random.Random(777)

        for _ in range(5_000):
            order = rng.randint(100, 1_000_000)
            comm_bps = rng.randint(0, 500)       # 0% to 5% commission
            flat_fee = rng.randint(0, 50)        # 0 to 50 paise flat fee
            shipping = rng.randint(0, 500)       # 0 to 500 paise shipping

            # Skip if parameters naturally cause an overdraft
            comm_paise = (order * comm_bps) // 10000
            total_deductions = comm_paise + flat_fee + shipping
            if total_deductions > order:
                with pytest.raises(ArithmeticDriftException):
                    calculate_route_splits(order, comm_bps, flat_fee, shipping_paise=shipping)
                continue

            result = calculate_route_splits(order, comm_bps, flat_fee, shipping_paise=shipping)
            assert result.order_paise == order
            assert result.merchant_paise + result.total_fee_paise == order
            assert result.total_fee_paise == result.protocol_fee_paise + result.logistics_amount_paise
            assert result.protocol_fee_paise == result.commission_paise + result.flat_fee_paise
            assert result.merchant_paise >= 0

    def test_route_splits_exact_overdraft_boundary(self) -> None:
        """Tests boundary when deductions == order (allowed, merchant=0) vs deductions == order + 1 (overdraft)."""
        order = 1000
        # deductions = 1000 (comm=200, flat=300, ship=500)
        res = calculate_route_splits(order, 2000, 300, shipping_paise=500)
        assert res.merchant_paise == 0
        assert res.total_fee_paise == 1000

        # deductions = 1001 -> must raise ArithmeticDriftException
        with pytest.raises(ArithmeticDriftException):
            calculate_route_splits(order, 2000, 301, shipping_paise=500)


class TestSpendingCapTransitionsAndLimits:
    """Stress tests for spending cap evaluations, daily limits, and single tx caps."""

    def test_spending_cap_exact_boundaries(self) -> None:
        """Tests exact threshold transitions."""
        cap = 100_000

        # Exactly at cap
        res_exact = evaluate_spending_cap(cumulative_paise=70_000, delta_paise=30_000, cap_paise=cap)
        assert res_exact.allowed is True
        assert res_exact.remaining_daily_paise == 0

        # 1 paise breach
        res_breach = evaluate_spending_cap(cumulative_paise=70_000, delta_paise=30_001, cap_paise=cap)
        assert res_breach.allowed is False
        assert res_breach.remaining_daily_paise == 30_000
        assert "exceeds spending cap" in res_breach.violation_reason

        # Single transaction limit exact boundary
        res_tx_ok = evaluate_spending_cap(cumulative_paise=10_000, delta_paise=25_000, cap_paise=cap, single_tx_limit_paise=25_000)
        assert res_tx_ok.allowed is True

        res_tx_breach = evaluate_spending_cap(cumulative_paise=10_000, delta_paise=25_001, cap_paise=cap, single_tx_limit_paise=25_000)
        assert res_tx_breach.allowed is False
        assert "exceeds single transaction limit" in res_tx_breach.violation_reason


class TestNormalizeInrCurrencyConversions:
    """Stress tests for half-up currency normalization."""

    def test_normalize_half_up_banking_cases(self) -> None:
        """Asserts half-up rounding on fractional paise."""
        assert normalize_inr_to_paise("0.004") == 0
        assert normalize_inr_to_paise("0.005") == 1
        assert normalize_inr_to_paise("1976.504") == 197650
        assert normalize_inr_to_paise("1976.505") == 197651
        assert normalize_inr_to_paise("100.00") == 10000
        assert normalize_inr_to_paise(Decimal("100.00")) == 10000
        assert normalize_inr_to_paise(100) == 10000


class TestDiscountAllocationConservation:
    """Stress tests for proportional cart discount allocation."""

    def test_discount_allocation_conservation_1k_runs(self) -> None:
        """Asserts sum(discounts) == global_discount and discounts[i] <= items[i]."""
        rng = random.Random(888)

        for _ in range(1_000):
            num_items = rng.randint(1, 30)
            items = [rng.randint(100, 50_000) for _ in range(num_items)]
            cart_total = sum(items)

            discount = rng.randint(0, cart_total)
            discounts = allocate_cart_discount_conserved(items, discount)

            assert sum(discounts) == discount
            assert len(discounts) == num_items
            assert all(d >= 0 for d in discounts)
            assert all(d <= item for d, item in zip(discounts, items))
