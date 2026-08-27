"""Deterministic Integer Paise Arithmetic Utilities for Layer 2 x402-INR Gateway.

Delegates directly to canonical Arithmetic Enclave in mandateEngine.
"""

from typing import Any, Dict, List, Optional, Union
from decimal import Decimal

try:
    from razoragentMesh.packages.mandateEngine.verification.arithmeticEnclave import (
        ArithmeticDriftException,
        GstBreakdown,
        RouteSplitResult,
        SpendingCapResult,
        allocateCartDiscountConserved,
        allocate_cart_discount_conserved,
        calculateRouteSplits,
        calculate_gst,
        calculate_route_splits,
        computeCartSettlementTotal,
        computeGstBreakdown,
        computeLineItemTotal,
        computeTcsWithholding,
        computeTotalPaise,
        compute_cart_settlement_total,
        compute_line_item_total,
        compute_tcs_withholding,
        evaluateSpendingCap,
        evaluate_spending_cap,
        normalizeInrToPaise,
        normalize_inr_to_paise,
        splitBillConserved,
        split_bill_conserved,
        validateIntegerPaise,
        validate_integer_paise,
    )
except ImportError:
    from packages.mandateEngine.verification.arithmeticEnclave import (
        ArithmeticDriftException,
        GstBreakdown,
        RouteSplitResult,
        SpendingCapResult,
        allocateCartDiscountConserved,
        allocate_cart_discount_conserved,
        calculateRouteSplits,
        calculate_gst,
        calculate_route_splits,
        computeCartSettlementTotal,
        computeGstBreakdown,
        computeLineItemTotal,
        computeTcsWithholding,
        computeTotalPaise,
        compute_cart_settlement_total,
        compute_line_item_total,
        compute_tcs_withholding,
        evaluateSpendingCap,
        evaluate_spending_cap,
        normalizeInrToPaise,
        normalize_inr_to_paise,
        splitBillConserved,
        split_bill_conserved,
        validateIntegerPaise,
        validate_integer_paise,
    )

__all__ = [
    "ArithmeticDriftException",
    "GstBreakdown",
    "RouteSplitResult",
    "SpendingCapResult",
    "allocateCartDiscountConserved",
    "allocate_cart_discount_conserved",
    "calculateRouteSplits",
    "calculate_gst",
    "calculate_route_splits",
    "computeCartSettlementTotal",
    "computeGstBreakdown",
    "computeLineItemTotal",
    "computeTcsWithholding",
    "computeTotalPaise",
    "compute_cart_settlement_total",
    "compute_line_item_total",
    "compute_tcs_withholding",
    "evaluateSpendingCap",
    "evaluate_spending_cap",
    "normalizeInrToPaise",
    "normalize_inr_to_paise",
    "splitBillConserved",
    "split_bill_conserved",
    "validateIntegerPaise",
    "validate_integer_paise",
]

