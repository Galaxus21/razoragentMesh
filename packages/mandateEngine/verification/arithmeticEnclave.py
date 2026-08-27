"""Deterministic Integer Paise Arithmetic Enclave.
Enforces pure zero-floating-point financial calculations, statutory GST, conserved splitting,
fee calculations, and spending cap evaluation.
"""
from dataclasses import dataclass
from decimal import Decimal, InvalidOperation, ROUND_HALF_UP
from typing import Any, List, Optional, Union

from ..constants.settlementConstants import (
    basisPointsDivisor, paisePerRupee, percentDivisor,
    tcsCgstBasisPoints, tcsIgstBasisPoints, tcsSgstBasisPoints, zeroPaise,
)
from ..settlement.settlementExceptions import ArithmeticDriftException
@dataclass(frozen=True)
class GstBreakdown:
    """Statutory GST component breakdown in integer paise."""
    cgstPaise: int = 0
    sgstPaise: int = 0
    igstPaise: int = 0
    totalTaxPaise: int = 0
    isIntraState: bool = True

    def __init__(self, cgstPaise: int = 0, sgstPaise: int = 0, igstPaise: int = 0, totalTaxPaise: int = 0, isIntraState: bool = True, **kwargs: Any) -> None:
        cgst = kwargs.get("cgst_paise", cgstPaise)
        sgst = kwargs.get("sgst_paise", sgstPaise)
        igst = kwargs.get("igst_paise", igstPaise)
        tot = kwargs.get("total_tax_paise", totalTaxPaise) or (cgst + sgst + igst)
        intra = kwargs.get("is_intra_state", isIntraState)
        for k, v in [("cgstPaise", cgst), ("cgst_paise", cgst), ("sgstPaise", sgst), ("sgst_paise", sgst), ("igstPaise", igst), ("igst_paise", igst), ("totalTaxPaise", tot), ("total_tax_paise", tot), ("isIntraState", intra), ("is_intra_state", intra)]:
            object.__setattr__(self, k, v)

    def __getitem__(self, key: str) -> Any:
        try: return getattr(self, key)
        except AttributeError: raise KeyError(key)

    def to_dict(self) -> dict[str, Any]:
        return {"cgstPaise": self.cgstPaise, "sgstPaise": self.sgstPaise, "igstPaise": self.igstPaise, "totalTaxPaise": self.totalTaxPaise, "isIntraState": self.isIntraState}


@dataclass(frozen=True)
class RouteSplitResult:
    """Conserved route split calculation result in integer paise."""
    orderPaise: int = 0
    commissionPaise: int = 0
    flatFeePaise: int = 0
    totalFeePaise: int = 0
    merchantNetPaise: int = 0
    merchantAccount: str = "acc_merchant_default"
    protocolFeeAccount: str = "acc_protocol_fee"
    logisticsAccount: str = "acc_logistics_default"
    protocolFeePaise: int = 0
    logisticsAmountPaise: int = 0

    def __init__(self, orderPaise: int = 0, commissionPaise: int = 0, flatFeePaise: int = 0, totalFeePaise: int = 0, merchantNetPaise: int = 0, **kwargs: Any) -> None:
        order = kwargs.get("order_paise", orderPaise) or kwargs.get("totalPaise", 0) or kwargs.get("total_paise", 0)
        comm = kwargs.get("commission_paise", commissionPaise)
        flat = kwargs.get("flat_fee_paise", flatFeePaise)
        proto = kwargs.get("protocol_fee_paise", kwargs.get("protocolFeePaise", comm + flat))
        logistics = kwargs.get("logistics_amount_paise", kwargs.get("logisticsAmountPaise", 0))
        tot_fee = kwargs.get("total_deductions_paise", kwargs.get("total_fee_paise", totalFeePaise or (proto + logistics)))
        merch = kwargs.get("merchant_paise", kwargs.get("merchant_amount_paise", kwargs.get("merchantAmountPaise", merchantNetPaise or (order - tot_fee))))
        merch_acc = kwargs.get("merchant_account", kwargs.get("merchantAccount", "acc_merchant_default"))
        proto_acc = kwargs.get("protocol_fee_account", kwargs.get("protocolFeeAccount", "acc_protocol_fee"))
        log_acc = kwargs.get("logistics_account", kwargs.get("logisticsAccount", "acc_logistics_default"))
        for k, v in [
            ("orderPaise", order), ("order_paise", order), ("totalPaise", order), ("total_paise", order),
            ("commissionPaise", comm), ("commission_paise", comm), ("flatFeePaise", flat), ("flat_fee_paise", flat),
            ("totalFeePaise", tot_fee), ("total_deductions_paise", tot_fee), ("total_fee_paise", tot_fee),
            ("merchantNetPaise", merch), ("merchant_paise", merch), ("merchantAmountPaise", merch), ("merchant_amount_paise", merch),
            ("protocolFeePaise", proto), ("protocol_fee_paise", proto), ("logisticsAmountPaise", logistics), ("logistics_amount_paise", logistics),
            ("merchantAccount", merch_acc), ("merchant_account", merch_acc), ("protocolFeeAccount", proto_acc), ("protocol_fee_account", proto_acc), ("logisticsAccount", log_acc), ("logistics_account", log_acc),
        ]:
            object.__setattr__(self, k, v)

    def __getitem__(self, key: str) -> Any:
        try: return getattr(self, key)
        except AttributeError: raise KeyError(key)

    def to_dict(self) -> dict[str, Any]:
        return {"orderPaise": self.orderPaise, "commissionPaise": self.commissionPaise, "flatFeePaise": self.flatFeePaise, "totalFeePaise": self.totalFeePaise, "merchantNetPaise": self.merchantNetPaise, "merchantAccount": self.merchantAccount}


@dataclass(frozen=True)
class SpendingCapResult:
    """Spending cap and budget limit evaluation result."""
    allowed: bool
    remainingDailyPaise: int = 0
    violationReason: str = ""

    def __init__(self, allowed: bool, remainingDailyPaise: int = 0, violationReason: str = "", **kwargs: Any) -> None:
        rem = kwargs.get("remaining_daily_paise", remainingDailyPaise)
        reason = kwargs.get("violation_reason", violationReason)
        for k, v in [("allowed", allowed), ("remainingDailyPaise", rem), ("remaining_daily_paise", rem), ("violationReason", reason), ("violation_reason", reason)]:
            object.__setattr__(self, k, v)

    def __getitem__(self, key: str) -> Any:
        try: return getattr(self, key)
        except AttributeError: raise KeyError(key)


def validate_integer_paise(amount: Any, field_name: str = "amount", *, allow_zero: bool = True, max_bound: int = 2**63 - 1, **kwargs: Any) -> int:
    """Strictly validates that an input is a pure integer representing paise."""
    fname = kwargs.get("fieldName", field_name)
    if isinstance(amount, bool) or not isinstance(amount, int):
        raise ArithmeticDriftException(f"Arithmetic drift violation: field '{fname}' must be int, got {type(amount).__name__}")
    if not allow_zero and amount <= 0:
        raise ArithmeticDriftException(f"Field '{fname}' must be positive integer (> 0), got {amount}")
    if allow_zero and amount < 0:
        raise ArithmeticDriftException(f"Field '{fname}' cannot be negative, got {amount}")
    if amount > max_bound:
        raise ArithmeticDriftException(f"Field '{fname}' exceeds maximum allowed bound ({max_bound}): got {amount}")
    return amount


validateIntegerPaise = validate_integer_paise


def compute_line_item_total(unit_price_paise: int = 0, quantity: int = 0, *, unitPricePaise: Optional[int] = None, **kwargs: Any) -> int:
    price = unitPricePaise if unitPricePaise is not None else kwargs.get("unit_price_paise", unit_price_paise)
    qty = kwargs.get("quantity", quantity)
    p = validate_integer_paise(price, "unitPricePaise")
    q = validate_integer_paise(qty, "quantity")
    if q <= 0: raise ArithmeticDriftException("Quantity must be positive integer")
    if p < 0: raise ArithmeticDriftException("UnitPricePaise cannot be negative")
    return p * q


computeLineItemTotal = compute_line_item_total
computeTotalPaise = compute_line_item_total

def calculate_gst(base_amount_paise: int = 0, tax_rate_bps: int = 0, supplier_state_code: str = "", pos_state_code: str = "", *, baseAmountPaise: Optional[int] = None, taxRateBps: Optional[int] = None, supplierStateCode: Optional[str] = None, posStateCode: Optional[str] = None, rounding_mode: str = "FLOOR", **kwargs: Any) -> GstBreakdown:
    """Calculates exact statutory GST components using basis points and zero-drift integer arithmetic."""
    base = baseAmountPaise if baseAmountPaise is not None else kwargs.get("base_amount_paise", base_amount_paise)
    rate_bps = taxRateBps if taxRateBps is not None else kwargs.get("tax_rate_bps", tax_rate_bps)
    supp = supplierStateCode if supplierStateCode is not None else kwargs.get("supplier_state_code", supplier_state_code)
    pos = posStateCode if posStateCode is not None else kwargs.get("pos_state_code", pos_state_code)
    b, rb = validate_integer_paise(base, "base_amount_paise"), validate_integer_paise(rate_bps, "tax_rate_bps")
    is_intra = (str(supp).strip() == str(pos).strip())
    total_tax = (b * rb + 5000) // 10000 if rounding_mode == "HALF_UP" else (b * rb) // 10000
    if is_intra:
        cgst_rate_bps = rb // 2
        cgst = (b * cgst_rate_bps + 5000) // 10000 if rounding_mode == "HALF_UP" else (b * cgst_rate_bps) // 10000
        sgst, igst = total_tax - cgst, 0
    else:
        cgst, sgst, igst = 0, 0, total_tax
    return GstBreakdown(cgstPaise=cgst, sgstPaise=sgst, igstPaise=igst, totalTaxPaise=total_tax, isIntraState=is_intra)


def computeGstBreakdown(taxableSubtotalPaise: int = 0, gstRatePercent: int = 0, isIntraState: bool = True, *, taxable_subtotal_paise: Optional[int] = None, gst_rate_percent: Optional[int] = None, is_intra_state: Optional[bool] = None, **kwargs: Any) -> GstBreakdown:
    """Calculates GST breakdown using floor division and exact penny conservation (legacy percent API)."""
    subtotal = taxable_subtotal_paise if taxable_subtotal_paise is not None else kwargs.get("taxableSubtotalPaise", taxableSubtotalPaise)
    rate = gst_rate_percent if gst_rate_percent is not None else kwargs.get("gstRatePercent", gstRatePercent)
    intra = is_intra_state if is_intra_state is not None else kwargs.get("isIntraState", isIntraState)
    sub, r = validate_integer_paise(subtotal, "taxableSubtotalPaise"), validate_integer_paise(rate, "gstRatePercent")
    gst = (sub * r) // percentDivisor
    if intra:
        cgst = (sub * (r // 2)) // percentDivisor
        sgst, igst = gst - cgst, zeroPaise
    else:
        cgst, sgst, igst = zeroPaise, zeroPaise, gst
    return GstBreakdown(cgstPaise=cgst, sgstPaise=sgst, igstPaise=igst, totalTaxPaise=cgst + sgst + igst, isIntraState=intra)


def split_bill_conserved(total_amount_paise: int = 0, participant_ratios: Optional[list[int]] = None, *, totalAmountPaise: Optional[int] = None, participantRatios: Optional[list[int]] = None, **kwargs: Any) -> list[int]:
    """Divides total_amount_paise among participants using Largest Remainder (Hare-Niemeyer) method."""
    total_val = totalAmountPaise if totalAmountPaise is not None else kwargs.get("total_amount_paise", total_amount_paise)
    ratios = participantRatios if participantRatios is not None else (participant_ratios if participant_ratios is not None else kwargs.get("participant_ratios", []))
    total = validate_integer_paise(total_val, "total_amount_paise")
    if not ratios: raise ArithmeticDriftException("Participant ratios list cannot be empty")
    for idx, r in enumerate(ratios): validate_integer_paise(r, f"participant_ratios[{idx}]")
    total_weight, n = sum(ratios), len(ratios)
    if total_weight <= 0: raise ArithmeticDriftException("Sum of participant weights must be positive (> 0)")
    if total == 0: return [0] * n
    floor_shares = [(total * w) // total_weight for w in ratios]
    remainders = [(total * w) % total_weight for w in ratios]
    ranked_indices = sorted(range(n), key=lambda i: (-remainders[i], -ratios[i], i))
    shares = list(floor_shares)
    for i in range(total - sum(floor_shares)): shares[ranked_indices[i]] += 1
    assert sum(shares) == total
    return shares


splitBillConserved = split_bill_conserved


def calculate_route_splits(order_paise: int = 0, commission_bps: int = 0, flat_fee_paise: int = 0, merchant_account: str = "acc_merchant_default", logistics_account: str = "acc_logistics_default", shipping_paise: int = 0, protocol_account: str = "acc_protocol_fee", *, orderPaise: Optional[int] = None, commissionBps: Optional[int] = None, flatFeePaise: Optional[int] = None, merchantAccount: Optional[str] = None, logisticsAccount: Optional[str] = None, shippingPaise: Optional[int] = None, protocolAccount: Optional[str] = None, **kwargs: Any) -> RouteSplitResult:
    """Computes fee deductions and net merchant payout with boundary clamping and zero-drift invariants."""
    ord_val = orderPaise if orderPaise is not None else kwargs.get("order_paise", order_paise)
    comm_val = commissionBps if commissionBps is not None else kwargs.get("commission_bps", commission_bps)
    flat_val = flatFeePaise if flatFeePaise is not None else kwargs.get("flat_fee_paise", flat_fee_paise)
    ship_val = shippingPaise if shippingPaise is not None else kwargs.get("shipping_paise", shipping_paise)
    merch_acc = merchantAccount or kwargs.get("merchant_account", merchant_account)
    proto_acc = protocolAccount or kwargs.get("protocol_account", kwargs.get("protocolFeeAccount", kwargs.get("protocol_fee_account", protocol_account)))
    log_acc = logisticsAccount or kwargs.get("logistics_account", logistics_account)
    order = validate_integer_paise(ord_val, "order_paise", allow_zero=True)
    comm_paise = (order * validate_integer_paise(comm_val, "commission_bps")) // 10000
    proto_fee = comm_paise + validate_integer_paise(flat_val, "flat_fee_paise")
    total_deductions = proto_fee + validate_integer_paise(ship_val, "shipping_paise")
    if total_deductions > order:
        raise ArithmeticDriftException(f"Settlement overdraft: total deductions ({total_deductions} paise) exceed order gross ({order} paise)")
    return RouteSplitResult(orderPaise=order, commissionPaise=comm_paise, flatFeePaise=flat_val, totalFeePaise=total_deductions, merchantNetPaise=order - total_deductions, protocolFeePaise=proto_fee, logisticsAmountPaise=ship_val, merchantAccount=merch_acc, protocolFeeAccount=proto_acc, logisticsAccount=log_acc)


calculateRouteSplits = calculate_route_splits


def evaluate_spending_cap(cumulative_paise: int = 0, delta_paise: int = 0, cap_paise: int = 0, single_tx_limit_paise: Optional[int] = None, *, cumulativePaise: Optional[int] = None, deltaPaise: Optional[int] = None, capPaise: Optional[int] = None, singleTxLimitPaise: Optional[int] = None, **kwargs: Any) -> SpendingCapResult:
    """Evaluates spending cap and single transaction bounds."""
    cumul_val = cumulativePaise if cumulativePaise is not None else kwargs.get("cumulative_paise", cumulative_paise)
    delta_val = deltaPaise if deltaPaise is not None else kwargs.get("delta_paise", delta_paise)
    cap_val = capPaise if capPaise is not None else kwargs.get("cap_paise", cap_paise)
    single_lim_val = singleTxLimitPaise if singleTxLimitPaise is not None else (single_tx_limit_paise if single_tx_limit_paise is not None else kwargs.get("single_tx_limit_paise"))
    cumul, delta, cap = validate_integer_paise(cumul_val, "cumulative_paise"), validate_integer_paise(delta_val, "delta_paise"), validate_integer_paise(cap_val, "cap_paise")
    if single_lim_val is not None:
        single_lim = validate_integer_paise(single_lim_val, "single_tx_limit_paise")
        if delta > single_lim:
            return SpendingCapResult(allowed=False, remainingDailyPaise=max(0, cap - cumul), violationReason=f"Transaction {delta} paise exceeds single transaction limit {single_lim} paise")
    if cumul + delta > cap:
        return SpendingCapResult(allowed=False, remainingDailyPaise=max(0, cap - cumul), violationReason=f"Cumulative spending {cumul + delta} paise exceeds spending cap {cap} paise")
    return SpendingCapResult(allowed=True, remainingDailyPaise=cap - (cumul + delta), violationReason="")


evaluateSpendingCap = evaluate_spending_cap


def allocate_cart_discount_conserved(item_taxable_paise: Optional[list[int]] = None, global_discount_paise: int = 0, *, itemTaxablePaise: Optional[list[int]] = None, globalDiscountPaise: Optional[int] = None, **kwargs: Any) -> list[int]:
    """Apportions global_discount_paise across items preserving exact total discount."""
    items = itemTaxablePaise if itemTaxablePaise is not None else (item_taxable_paise if item_taxable_paise is not None else kwargs.get("item_taxable_paise", []))
    disc_val = globalDiscountPaise if globalDiscountPaise is not None else kwargs.get("global_discount_paise", global_discount_paise)
    discount = validate_integer_paise(disc_val, "global_discount_paise")
    if not items: return []
    for idx, p in enumerate(items): validate_integer_paise(p, f"item_taxable_paise[{idx}]")
    cart_total = sum(items)
    if discount > cart_total: raise ArithmeticDriftException("Global discount cannot exceed total cart value")
    if discount == 0: return [0] * len(items)
    return split_bill_conserved(discount, items)


allocateCartDiscountConserved = allocate_cart_discount_conserved


def compute_tcs_withholding(taxable_subtotal_paise: int = 0, is_intra_state: bool = True, *, taxableSubtotalPaise: Optional[int] = None, isIntraState: Optional[bool] = None, **kwargs: Any) -> dict[str, int]:
    """Calculates Section 52 TCS withholding on net taxable value."""
    sub_val = taxableSubtotalPaise if taxableSubtotalPaise is not None else kwargs.get("taxable_subtotal_paise", taxable_subtotal_paise)
    intra = isIntraState if isIntraState is not None else kwargs.get("is_intra_state", is_intra_state)
    subtotal = validate_integer_paise(sub_val, "taxable_subtotal_paise")
    if intra:
        tcs_cgst = (subtotal * tcsCgstBasisPoints) // basisPointsDivisor
        tcs_sgst = (subtotal * tcsSgstBasisPoints) // basisPointsDivisor
        tcs_igst = zeroPaise
    else:
        tcs_cgst, tcs_sgst, tcs_igst = zeroPaise, zeroPaise, (subtotal * tcsIgstBasisPoints) // basisPointsDivisor
    total_tcs = tcs_cgst + tcs_sgst + tcs_igst
    return {"tcsCgstPaise": tcs_cgst, "tcsSgstPaise": tcs_sgst, "tcsIgstPaise": tcs_igst, "totalTcsPaise": total_tcs, "tcs_cgst_paise": tcs_cgst, "tcs_sgst_paise": tcs_sgst, "tcs_igst_paise": tcs_igst, "total_tcs_paise": total_tcs}


computeTcsWithholding = compute_tcs_withholding


def compute_cart_settlement_total(taxable_subtotal_paise: int = 0, total_tax_paise: int = 0, shipping_paise: int = 0, discount_paise: int = 0, *, taxableSubtotalPaise: Optional[int] = None, totalTaxPaise: Optional[int] = None, shippingPaise: Optional[int] = None, discountPaise: Optional[int] = None, **kwargs: Any) -> int:
    """Recomputes deterministic gross settlement total in integer paise."""
    sub_val = taxableSubtotalPaise if taxableSubtotalPaise is not None else kwargs.get("taxable_subtotal_paise", taxable_subtotal_paise)
    tax_val = totalTaxPaise if totalTaxPaise is not None else kwargs.get("total_tax_paise", total_tax_paise)
    ship_val = shippingPaise if shippingPaise is not None else kwargs.get("shipping_paise", shipping_paise)
    disc_val = discountPaise if discountPaise is not None else kwargs.get("discount_paise", discount_paise)
    gross = validate_integer_paise(sub_val, "taxable_subtotal_paise") + validate_integer_paise(tax_val, "total_tax_paise") + validate_integer_paise(ship_val, "shipping_paise") - validate_integer_paise(disc_val, "discount_paise")
    if gross < 0: raise ArithmeticDriftException("Calculated gross settlement amount cannot be negative")
    return gross


computeCartSettlementTotal = compute_cart_settlement_total


def normalize_inr_to_paise(value: Union[str, int, Decimal]) -> int:
    """Converts INR currency representation (str, int, Decimal) to integer paise using banking half-up rounding."""
    if isinstance(value, float):
        raise ArithmeticDriftException(f"Floating-point values are strictly forbidden in financial paths: {value}")
    if isinstance(value, bool) or not isinstance(value, (str, int, Decimal)):
        raise ArithmeticDriftException(f"Unsupported type for financial currency normalization: {type(value).__name__}")
    try:
        dec = Decimal(str(value).strip())
    except (InvalidOperation, ValueError) as err:
        raise ArithmeticDriftException(f"Failed to parse numeric string into decimal currency: {value}") from err
    if dec < Decimal("0"): raise ArithmeticDriftException(f"Negative financial amounts are strictly forbidden: {value}")
    return int((dec * Decimal(str(paisePerRupee))).quantize(Decimal("1"), rounding=ROUND_HALF_UP))


normalizeInrToPaise = normalize_inr_to_paise


__all__ = [
    "ArithmeticDriftException", "GstBreakdown", "RouteSplitResult", "SpendingCapResult",
    "allocateCartDiscountConserved", "allocate_cart_discount_conserved", "calculateRouteSplits",
    "calculate_gst", "calculate_route_splits", "computeCartSettlementTotal", "computeGstBreakdown",
    "computeLineItemTotal", "computeTcsWithholding", "computeTotalPaise", "compute_cart_settlement_total",
    "compute_line_item_total", "compute_tcs_withholding", "evaluateSpendingCap", "evaluate_spending_cap",
    "normalizeInrToPaise", "normalize_inr_to_paise", "splitBillConserved", "split_bill_conserved",
    "validateIntegerPaise", "validate_integer_paise",
]
