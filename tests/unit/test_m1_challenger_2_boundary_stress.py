import random
from decimal import Decimal
import pytest
from razoragentMesh.packages.mandateEngine.verification.arithmeticEnclave import (
    calculate_route_splits, calculateRouteSplits,
    evaluate_spending_cap, evaluateSpendingCap,
    compute_tcs_withholding, computeTcsWithholding,
    allocate_cart_discount_conserved, allocateCartDiscountConserved,
    compute_cart_settlement_total, computeCartSettlementTotal,
    normalize_inr_to_paise, normalizeInrToPaise,
    validate_integer_paise, validateIntegerPaise,
    split_bill_conserved, splitBillConserved,
    calculate_gst, computeGstBreakdown,
    compute_line_item_total, computeLineItemTotal, computeTotalPaise,
    ArithmeticDriftException, GstBreakdown, RouteSplitResult, SpendingCapResult
)
from razoragentMesh.packages.x402Gateway.src.constants.arithmeticUtils import (
    calculate_route_splits as gw_calc_route_splits,
    evaluate_spending_cap as gw_eval_spending_cap,
    compute_tcs_withholding as gw_compute_tcs,
    normalize_inr_to_paise as gw_norm_inr
)

def test_route_splits_boundary_and_fuzzing():
    res = calculate_route_splits(10000, 0, 0, shipping_paise=0)
    assert res.merchantNetPaise == 10000 and res.commissionPaise == 0

    res = calculate_route_splits(10000, 10000, 0, shipping_paise=0)
    assert res.merchantNetPaise == 0 and res.commissionPaise == 10000

    res = calculate_route_splits(1000, 0, 500, shipping_paise=500)
    assert res.merchantNetPaise == 0 and res.totalFeePaise == 1000

    with pytest.raises(ArithmeticDriftException):
        calculate_route_splits(1000, 0, 501, shipping_paise=500)

    rng = random.Random(999)
    for _ in range(10000):
        order = rng.randint(0, 1_000_000)
        comm_bps = rng.randint(0, 10000)
        flat_fee = rng.randint(0, 10000)
        ship = rng.randint(0, 50000)
        comm_exp = (order * comm_bps) // 10000
        tot = comm_exp + flat_fee + ship
        if tot > order:
            with pytest.raises(ArithmeticDriftException):
                calculate_route_splits(order, comm_bps, flat_fee, shipping_paise=ship)
        else:
            s = calculate_route_splits(order, comm_bps, flat_fee, shipping_paise=ship)
            assert s.orderPaise == order
            assert s.commissionPaise == comm_exp
            assert s.flatFeePaise == flat_fee
            assert s.totalFeePaise == tot
            assert s.merchantNetPaise == order - tot
            assert s.merchantNetPaise + s.totalFeePaise == order
            assert s.protocolFeePaise == comm_exp + flat_fee
            assert s.logisticsAmountPaise == ship

def test_spending_cap_boundary_transitions():
    cap = 50000
    cumul = 30000
    remaining = 20000

    r1 = evaluate_spending_cap(cumul, remaining - 1, cap)
    assert r1.allowed is True and r1.remainingDailyPaise == 1 and r1.violationReason == ''

    r2 = evaluate_spending_cap(cumul, remaining, cap)
    assert r2.allowed is True and r2.remainingDailyPaise == 0 and r2.violationReason == ''

    r3 = evaluate_spending_cap(cumul, remaining + 1, cap)
    assert r3.allowed is False and r3.remainingDailyPaise == 20000 and 'exceeds spending cap' in r3.violationReason

    r_at_cap_0 = evaluate_spending_cap(50000, 0, 50000)
    assert r_at_cap_0.allowed is True and r_at_cap_0.remainingDailyPaise == 0
    r_at_cap_1 = evaluate_spending_cap(50000, 1, 50000)
    assert r_at_cap_1.allowed is False and r_at_cap_1.remainingDailyPaise == 0

    r_above_cap = evaluate_spending_cap(55000, 0, 50000)
    assert r_above_cap.allowed is False and r_above_cap.remainingDailyPaise == 0

    single_lim = 10000
    r_single_ok = evaluate_spending_cap(0, single_lim, cap, single_tx_limit_paise=single_lim)
    assert r_single_ok.allowed is True
    r_single_fail = evaluate_spending_cap(0, single_lim + 1, cap, single_tx_limit_paise=single_lim)
    assert r_single_fail.allowed is False and 'exceeds single transaction limit' in r_single_fail.violationReason

    for bad_args in [(-1, 100, 1000), (100, -1, 1000), (100, 100, -1000)]:
        with pytest.raises(ArithmeticDriftException):
            evaluate_spending_cap(*bad_args)

def test_tcs_and_discount_allocation_enclave():
    tcs_10k = compute_tcs_withholding(10000, is_intra_state=True)
    assert tcs_10k['tcsCgstPaise'] == 50 and tcs_10k['tcsSgstPaise'] == 50
    assert tcs_10k['tcsIgstPaise'] == 0 and tcs_10k['totalTcsPaise'] == 100

    tcs_intra = compute_tcs_withholding(100000, is_intra_state=True)
    assert tcs_intra['tcsCgstPaise'] == 500 and tcs_intra['tcsSgstPaise'] == 500
    assert tcs_intra['tcsIgstPaise'] == 0 and tcs_intra['totalTcsPaise'] == 1000

    tcs_inter = compute_tcs_withholding(100000, is_intra_state=False)
    assert tcs_inter['tcsCgstPaise'] == 0 and tcs_inter['tcsSgstPaise'] == 0
    assert tcs_inter['tcsIgstPaise'] == 1000 and tcs_inter['totalTcsPaise'] == 1000

    items = [1000, 2000, 3000]
    assert allocate_cart_discount_conserved(items, 6000) == [1000, 2000, 3000]
    assert allocate_cart_discount_conserved(items, 0) == [0, 0, 0]
    assert allocate_cart_discount_conserved([], 0) == []

    with pytest.raises(ArithmeticDriftException):
        allocate_cart_discount_conserved(items, 6001)

    d = allocate_cart_discount_conserved([1000, 1000, 1000], 100)
    assert d == [34, 33, 33] and sum(d) == 100

    rng = random.Random(777)
    for _ in range(5000):
        n = rng.randint(1, 20)
        cart = [rng.randint(100, 50000) for _ in range(n)]
        tot_cart = sum(cart)
        disc = rng.randint(0, tot_cart)
        res_disc = allocate_cart_discount_conserved(cart, disc)
        assert sum(res_disc) == disc
        assert all(0 <= res_disc[i] <= cart[i] for i in range(n))

    ctot = compute_cart_settlement_total(10000, 1800, 500, 1000)
    assert ctot == 11300
    with pytest.raises(ArithmeticDriftException):
        compute_cart_settlement_total(1000, 100, 50, 2000)

def test_currency_normalization_and_attack_vectors():
    assert normalize_inr_to_paise('1976.50') == 197650
    assert normalize_inr_to_paise('0') == 0
    assert normalize_inr_to_paise('0.00') == 0
    assert normalize_inr_to_paise('0.01') == 1
    assert normalize_inr_to_paise('0.005') == 1
    assert normalize_inr_to_paise('0.004') == 0
    assert normalize_inr_to_paise('  123.45  ') == 12345
    assert normalize_inr_to_paise(Decimal('49.99')) == 4999
    assert normalize_inr_to_paise(500) == 50000

    for bad in [19.76, 0.0, float('nan'), float('inf'), float('-inf'), True, False, None, [], {}, '-10.00', 'abc', '']:
        with pytest.raises(ArithmeticDriftException):
            normalize_inr_to_paise(bad)

def test_function_name_aliasing_and_result_field_access():
    """calculate_gst / GstBreakdown etc. expose one camelCase spelling per field; only the
    module-level function names (snake_case vs camelCase) are deliberately dual-aliased."""
    assert validateIntegerPaise(100) == validate_integer_paise(100)
    assert calculateRouteSplits(1000, 500, 50).to_dict() == calculate_route_splits(1000, 500, 50).to_dict()
    assert evaluateSpendingCap(100, 50, 200).allowed == evaluate_spending_cap(100, 50, 200).allowed
    assert allocateCartDiscountConserved([100, 200], 30) == allocate_cart_discount_conserved([100, 200], 30)
    assert computeTcsWithholding(10000) == compute_tcs_withholding(10000)
    assert computeCartSettlementTotal(100, 10, 5, 2) == compute_cart_settlement_total(100, 10, 5, 2)
    assert normalizeInrToPaise('10.50') == normalize_inr_to_paise('10.50')
    assert splitBillConserved(100, [1, 1]) == split_bill_conserved(100, [1, 1])
    assert computeLineItemTotal(100, 3) == compute_line_item_total(100, 3) == computeTotalPaise(100, 3)

    gst = calculate_gst(10000, 1800, '29', '29')
    assert gst.cgstPaise == 900
    assert gst.sgstPaise == 900
    assert gst.igstPaise == 0
    assert gst.totalTaxPaise == 1800
    assert gst.isIntraState is True
    assert isinstance(gst.to_dict(), dict)

    split = calculate_route_splits(10000, 200, 50, shipping_paise=500)
    assert split.orderPaise == 10000
    assert split.merchantNetPaise == 9250
    assert split.totalFeePaise == 750
    assert isinstance(split.to_dict(), dict)

    sc = evaluate_spending_cap(10000, 5000, 20000)
    assert sc.allowed is True
    assert sc.remainingDailyPaise == 5000
    assert sc.violationReason == ''

    res_gw = gw_calc_route_splits(5000, 100, 20)
    assert res_gw.merchantNetPaise == 4930
    assert gw_eval_spending_cap(1000, 500, 2000).allowed is True
    assert gw_compute_tcs(50000)['totalTcsPaise'] == 500
    assert gw_norm_inr('99.00') == 9900
