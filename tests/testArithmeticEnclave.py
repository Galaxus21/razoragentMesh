"""Unit tests for Layer 4 Deterministic Arithmetic Enclave."""

import pytest
from razoragentMesh.packages.mandateEngine.constants.settlementConstants import paisePerRupee
from razoragentMesh.packages.mandateEngine.verification.arithmeticEnclave import (
    computeCartSettlementTotal,
    computeGstBreakdown,
    computeLineItemTotal,
    computeTcsWithholding,
    validateIntegerPaise,
)
from razoragentMesh.packages.mandateEngine.settlement.settlementExceptions import (
    ArithmeticDriftException,
)


def testValidateIntegerPaise() -> None:
    """Verifies integer acceptance and float/bool rejection."""
    assert validateIntegerPaise(100, "testField") == 100
    assert validateIntegerPaise(0, "testZero") == 0

    with pytest.raises(ArithmeticDriftException):
        validateIntegerPaise(100.5, "floatField")

    with pytest.raises(ArithmeticDriftException):
        validateIntegerPaise(True, "boolField")

    with pytest.raises(ArithmeticDriftException):
        validateIntegerPaise("100", "strField")


def testComputeLineItemTotal() -> None:
    """Verifies integer multiplication of unit price and quantity."""
    assert computeLineItemTotal(150000, 3) == 450000
    with pytest.raises(ArithmeticDriftException):
        computeLineItemTotal(150000, 0)
    with pytest.raises(ArithmeticDriftException):
        computeLineItemTotal(-10, 5)


def testComputeGstBreakdownIntraState() -> None:
    """Verifies intra-state 50/50 split with zero penny loss floor division."""
    # 100 paise at 18% GST -> 18 paise total -> CGST 9, SGST 9, IGST 0
    res = computeGstBreakdown(100, 18, isIntraState=True)
    assert res.totalTaxPaise == 18
    assert res.cgstPaise == 9
    assert res.sgstPaise == 9
    assert res.igstPaise == 0

    # Odd amount test: 101 paise at 5% GST -> CGST and SGST are each the 2.5% half-rate:
    # (101 * 250)//20000 = 2 paise, applied identically -> total = 4 paise.
    oddRes = computeGstBreakdown(101, 5, isIntraState=True)
    assert oddRes.totalTaxPaise == 4
    assert oddRes.cgstPaise == oddRes.sgstPaise == 2
    assert oddRes.cgstPaise + oddRes.sgstPaise == oddRes.totalTaxPaise
    assert oddRes.igstPaise == 0


def testComputeGstBreakdownInterState() -> None:
    """Verifies inter-state 100% IGST application."""
    res = computeGstBreakdown(10000, 18, isIntraState=False)
    assert res.totalTaxPaise == 1800
    assert res.cgstPaise == 0
    assert res.sgstPaise == 0
    assert res.igstPaise == 1800


def testComputeTcsWithholding() -> None:
    """Verifies 1% TCS calculation under Section 52."""
    # 1,00,000 paise (Rs 1,000) at 1% TCS (100 basis points = 1000 paise total)
    # Intra-state: 0.5% CGST (50 bps) = 500 paise, 0.5% SGST (50 bps) = 500 paise, Total = 1000 paise
    intraTcs = computeTcsWithholding(100000, isIntraState=True)
    assert intraTcs["tcsCgstPaise"] == 500
    assert intraTcs["tcsSgstPaise"] == 500
    assert intraTcs["tcsIgstPaise"] == 0
    assert intraTcs["totalTcsPaise"] == 1000

    # Inter-state: 1.0% IGST (100 bps) = 1000 paise
    interTcs = computeTcsWithholding(100000, isIntraState=False)
    assert interTcs["tcsCgstPaise"] == 0
    assert interTcs["tcsSgstPaise"] == 0
    assert interTcs["tcsIgstPaise"] == 1000
    assert interTcs["totalTcsPaise"] == 1000


def testComputeCartSettlementTotal() -> None:
    """Verifies gross cart summation with discounts and shipping."""
    # Subtotal 10000, Tax 1800, Shipping 500, Discount 300 -> Total 12000
    total = computeCartSettlementTotal(
        taxableSubtotalPaise=10000,
        totalTaxPaise=1800,
        shippingPaise=500,
        discountPaise=300,
    )
    assert total == 12000
