"""Property-Based Test Suite: Enclave Math Zero-Drift & Conservation Invariants.

Verifies:
1. Intra-state GST penny conservation (CGST + SGST == Total Tax) across statutory slabs and arbitrary bps.
2. Inter-state GST pure IGST allocation (CGST == 0, SGST == 0, IGST == Total Tax).
3. Legacy percent GST API penny conservation across all 0-100% rates.
4. Conserved bill splitting (Hare-Niemeyer largest remainder) exact penny sum and error bounds.
5. Conserved cart discount allocation with individual item price caps and overdraft rejection.
6. Conserved route split payouts (merchant + protocol + logistics == gross) and overdraft defense.
7. TCS Section 52 withholding split conservation (intra: 25/25 bps, inter: 50 bps per Notification 15/2024).
8. Strict float and boolean rejection across all enclave arithmetic interfaces.
"""

from hypothesis import given, settings, strategies as st
import pytest

try:
    from razoragentMesh.packages.mandateEngine.verification.arithmeticEnclave import (
        calculate_gst,
        computeGstBreakdown,
        split_bill_conserved,
        allocate_cart_discount_conserved,
        calculate_route_splits,
        compute_tcs_withholding,
        compute_cart_settlement_total,
        compute_line_item_total,
        validate_integer_paise,
        normalize_inr_to_paise,
        GstBreakdown,
        RouteSplitResult,
    )
    from razoragentMesh.packages.mandateEngine.settlement.settlementExceptions import (
        ArithmeticDriftException,
    )
    from razoragentMesh.packages.mandateEngine.constants.settlementConstants import (
        basisPointsDivisor, tcsCgstBasisPoints, tcsIgstBasisPoints,
    )
except ModuleNotFoundError:
    from packages.mandateEngine.verification.arithmeticEnclave import (
        calculate_gst,
        computeGstBreakdown,
        split_bill_conserved,
        allocate_cart_discount_conserved,
        calculate_route_splits,
        compute_tcs_withholding,
        compute_cart_settlement_total,
        compute_line_item_total,
        validate_integer_paise,
        normalize_inr_to_paise,
        GstBreakdown,
        RouteSplitResult,
    )
    from packages.mandateEngine.settlement.settlementExceptions import (
        ArithmeticDriftException,
    )

# Statutory GST slabs in basis points (0%, 0.25%, 1.5%, 3%, 5%, 6%, 12%, 18%, 28%, 100%)
STATUTORY_GST_SLABS_BPS = [0, 25, 150, 300, 500, 600, 1200, 1800, 2800, 10000]
STATUTORY_GST_SLABS_PERCENT = [0, 5, 12, 18, 28]

# Strategies
paise_strategy = st.integers(min_value=0, max_value=10**12)
positive_paise_strategy = st.integers(min_value=1, max_value=10**12)
statutory_bps_strategy = st.sampled_from(STATUTORY_GST_SLABS_BPS)
arbitrary_bps_strategy = st.integers(min_value=0, max_value=10000)
statutory_percent_strategy = st.sampled_from(STATUTORY_GST_SLABS_PERCENT)
arbitrary_percent_strategy = st.integers(min_value=0, max_value=100)

float_strategy = st.one_of(
    st.floats(min_value=-1e10, max_value=1e10),
    st.sampled_from([0.0, -0.0, 1.5, 1976.501, -1976.501, 1e-5, float("inf"), float("-inf"), float("nan")]),
)


class TestPropertyGstZeroDrift:
    """Property tests for statutory GST calculations and penny conservation."""

    @settings(max_examples=1000, deadline=None)
    @given(amount=paise_strategy, rate_bps=statutory_bps_strategy)
    def test_property_intra_state_statutory_slabs_conservation(self, amount: int, rate_bps: int) -> None:
        """Property: For any paise (0-10^12) and statutory GST slab, CGST equals SGST exactly
        and cgst + sgst == total_gst strictly."""
        res = calculate_gst(
            base_amount_paise=amount,
            tax_rate_bps=rate_bps,
            supplier_state_code="29",
            pos_state_code="29",
        )
        assert res.cgstPaise == res.sgstPaise
        assert res.cgstPaise + res.sgstPaise == res.totalTaxPaise
        assert res.igstPaise == 0
        assert res.isIntraState is True
        assert res.totalTaxPaise == 2 * ((amount * rate_bps) // 20000)

    @settings(max_examples=1000, deadline=None)
    @given(amount=paise_strategy, rate_bps=arbitrary_bps_strategy)
    def test_property_intra_state_arbitrary_bps_conservation(self, amount: int, rate_bps: int) -> None:
        """Property: For any paise and arbitrary rate (0-10000 bps), CGST equals SGST exactly
        and cgst + sgst == total_gst."""
        res = calculate_gst(
            base_amount_paise=amount,
            tax_rate_bps=rate_bps,
            supplier_state_code="29",
            pos_state_code="29",
        )
        assert res.cgstPaise == res.sgstPaise
        assert res.cgstPaise + res.sgstPaise == res.totalTaxPaise
        assert res.igstPaise == 0
        assert res.isIntraState is True
        assert res.totalTaxPaise == 2 * ((amount * rate_bps) // 20000)

    @settings(max_examples=1000, deadline=None)
    @given(amount=paise_strategy, rate_bps=arbitrary_bps_strategy)
    def test_property_inter_state_igst_allocation(self, amount: int, rate_bps: int) -> None:
        """Property: For inter-state supply, CGST and SGST are 0 and IGST equals total_gst."""
        res = calculate_gst(
            base_amount_paise=amount,
            tax_rate_bps=rate_bps,
            supplier_state_code="29",
            pos_state_code="27",
        )
        assert res.cgstPaise == 0
        assert res.sgstPaise == 0
        assert res.igstPaise == res.totalTaxPaise
        assert res.isIntraState is False
        assert res.totalTaxPaise == (amount * rate_bps) // 10000

    @settings(max_examples=1000, deadline=None)
    @given(amount=paise_strategy, rate_percent=arbitrary_percent_strategy)
    def test_property_legacy_percent_gst_conservation(self, amount: int, rate_percent: int) -> None:
        """Property: Legacy percent API computes CGST exactly equal to SGST and strictly
        conserves CGST + SGST == totalTaxPaise."""
        res_intra = computeGstBreakdown(amount, rate_percent, isIntraState=True)
        assert res_intra.cgstPaise == res_intra.sgstPaise
        assert res_intra.cgstPaise + res_intra.sgstPaise == res_intra.totalTaxPaise
        assert res_intra.igstPaise == 0
        assert res_intra.totalTaxPaise == 2 * ((amount * rate_percent) // 200)

        res_inter = computeGstBreakdown(amount, rate_percent, isIntraState=False)
        assert res_inter.cgstPaise == 0
        assert res_inter.sgstPaise == 0
        assert res_inter.igstPaise == res_inter.totalTaxPaise
        assert res_inter.totalTaxPaise == (amount * rate_percent) // 100


class TestPropertyConservedSplitting:
    """Property tests for Hare-Niemeyer bill splitting and discount allocation."""

    @settings(max_examples=1000, deadline=None)
    @given(
        total=paise_strategy,
        ratios=st.lists(st.integers(min_value=0, max_value=10**6), min_size=1, max_size=50).filter(lambda r: sum(r) > 0),
    )
    def test_property_bill_splitting_conservation_and_bounds(self, total: int, ratios: list[int]) -> None:
        """Property: Conserved bill split preserves total sum with bounded error per participant."""
        shares = split_bill_conserved(total, ratios)
        assert sum(shares) == total
        assert len(shares) == len(ratios)
        assert all(s >= 0 for s in shares)

        total_weight = sum(ratios)
        for i, weight in enumerate(ratios):
            exact_share = (total * weight) / total_weight
            assert abs(shares[i] - exact_share) < 1.0

    @settings(max_examples=1000, deadline=None)
    @given(
        items=st.lists(st.integers(min_value=0, max_value=10**9), min_size=1, max_size=20).filter(lambda x: sum(x) > 0),
        data=st.data(),
    )
    def test_property_cart_discount_allocation_conservation(self, items: list[int], data: st.DataObject) -> None:
        """Property: Cart discount apportionment preserves total discount without exceeding item prices."""
        cart_total = sum(items)
        discount = data.draw(st.integers(min_value=0, max_value=cart_total))

        allocated = allocate_cart_discount_conserved(items, discount)
        assert sum(allocated) == discount
        assert len(allocated) == len(items)
        for d, item_price in zip(allocated, items):
            assert 0 <= d <= item_price

    @settings(max_examples=500, deadline=None)
    @given(
        items=st.lists(st.integers(min_value=1, max_value=10**6), min_size=1, max_size=10),
        excess=st.integers(min_value=1, max_value=10**6),
    )
    def test_property_cart_discount_overdraft_raises(self, items: list[int], excess: int) -> None:
        """Property: Discount exceeding cart total strictly raises ArithmeticDriftException."""
        with pytest.raises(ArithmeticDriftException):
            allocate_cart_discount_conserved(items, sum(items) + excess)


class TestPropertyRouteSplitsAndTcs:
    """Property tests for 3-way route payout conservation and TCS Section 52."""

    @settings(max_examples=1000, deadline=None)
    @given(
        order=paise_strategy,
        comm_bps=arbitrary_bps_strategy,
        flat_fee=st.integers(min_value=0, max_value=10**6),
        shipping=st.integers(min_value=0, max_value=10**6),
    )
    def test_property_route_splits_conservation_or_overdraft(
        self, order: int, comm_bps: int, flat_fee: int, shipping: int
    ) -> None:
        """Property: Route splits conserve order amount or raise ArithmeticDriftException on overdraft."""
        comm_paise = (order * comm_bps) // 10000
        proto_fee = comm_paise + flat_fee
        total_deductions = proto_fee + shipping

        if total_deductions <= order:
            result = calculate_route_splits(
                order_paise=order,
                commission_bps=comm_bps,
                flat_fee_paise=flat_fee,
                shipping_paise=shipping,
            )
            assert result.merchantNetPaise + result.totalFeePaise == result.orderPaise == order
            assert result.protocolFeePaise + result.logisticsAmountPaise == result.totalFeePaise
            assert result.merchantNetPaise >= 0
        else:
            with pytest.raises(ArithmeticDriftException):
                calculate_route_splits(
                    order_paise=order,
                    commission_bps=comm_bps,
                    flat_fee_paise=flat_fee,
                    shipping_paise=shipping,
                )

    @settings(max_examples=1000, deadline=None)
    @given(subtotal=paise_strategy)
    def test_property_tcs_withholding_conservation(self, subtotal: int) -> None:
        """Property: TCS withholding strictly conserves 50+50 bps (intra) or 100 bps (inter)."""
        tcs_intra = compute_tcs_withholding(subtotal, is_intra_state=True)
        assert tcs_intra["tcsCgstPaise"] + tcs_intra["tcsSgstPaise"] == tcs_intra["totalTcsPaise"]
        assert tcs_intra["tcsCgstPaise"] == (subtotal * tcsCgstBasisPoints) // basisPointsDivisor
        assert tcs_intra["tcsSgstPaise"] == (subtotal * tcsCgstBasisPoints) // basisPointsDivisor
        assert tcs_intra["tcsIgstPaise"] == 0

        tcs_inter = compute_tcs_withholding(subtotal, is_intra_state=False)
        assert tcs_inter["tcsIgstPaise"] == tcs_inter["totalTcsPaise"]
        assert tcs_inter["tcsIgstPaise"] == (subtotal * tcsIgstBasisPoints) // basisPointsDivisor
        assert tcs_inter["tcsCgstPaise"] == 0
        assert tcs_inter["tcsSgstPaise"] == 0


class TestPropertyStrictFloatRejection:
    """Property tests asserting strict rejection of floating-point and boolean types."""

    @settings(max_examples=500, deadline=None)
    @given(val=float_strategy)
    def test_property_validate_integer_paise_rejects_floats(self, val: float) -> None:
        """Property: validate_integer_paise strictly rejects any float."""
        with pytest.raises(ArithmeticDriftException):
            validate_integer_paise(val, "floatField")

    @settings(max_examples=100, deadline=None)
    @given(b=st.booleans())
    def test_property_validate_integer_paise_rejects_booleans(self, b: bool) -> None:
        """Property: validate_integer_paise strictly rejects booleans masked as integers."""
        with pytest.raises(ArithmeticDriftException):
            validate_integer_paise(b, "boolField")

    @settings(max_examples=500, deadline=None)
    @given(val=float_strategy)
    def test_property_enclave_functions_reject_floats(self, val: float) -> None:
        """Property: All enclave entrypoints reject injected floats."""
        with pytest.raises(ArithmeticDriftException):
            compute_line_item_total(val, 1)  # type: ignore
        with pytest.raises(ArithmeticDriftException):
            calculate_gst(val, 1800, "29", "29")  # type: ignore
        with pytest.raises(ArithmeticDriftException):
            computeGstBreakdown(val, 18)  # type: ignore
        with pytest.raises(ArithmeticDriftException):
            normalize_inr_to_paise(val)
