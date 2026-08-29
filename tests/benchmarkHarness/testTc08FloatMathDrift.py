from typing import Any
import pytest

from razoragentMesh.packages.mandateEngine.verification.arithmeticEnclave import (
    computeCartSettlementTotal,
    computeGstBreakdown,
    computeLineItemTotal,
    computeTcsWithholding,
    validateIntegerPaise,
)
from razoragentMesh.packages.mandateEngine.crypto.jcsCanonicalizer import canonicalizeJson
from razoragentMesh.packages.mandateEngine.settlement.settlementExceptions import (
    ArithmeticDriftException,
)

# Test Float Injections
sampleFloatValue = 1976.501
sampleFloatGst = 4200.50


def testTc08FloatInArithmeticEnclaveRaisesException() -> None:
    """TC-08: Float Math Drift — Injected float value raises ArithmeticDriftException, 0% hallucinations."""
    # 1. Direct validator
    with pytest.raises(ArithmeticDriftException) as excInfo:
        validateIntegerPaise(sampleFloatValue, "unitPricePaise")
    assert "Arithmetic drift violation" in str(excInfo.value)

    # 2. Boolean masked as integer
    with pytest.raises(ArithmeticDriftException):
        validateIntegerPaise(True, "quantity")

    # 3. Float in computeLineItemTotal
    with pytest.raises(ArithmeticDriftException):
        computeLineItemTotal(420000, 1.5)  # type: ignore

    with pytest.raises(ArithmeticDriftException):
        computeLineItemTotal(sampleFloatGst, 2)  # type: ignore

    # 4. Float in computeGstBreakdown
    with pytest.raises(ArithmeticDriftException):
        computeGstBreakdown(420000, 18.5, isIntraState=True)  # type: ignore


def testTc08FloatInJcsCanonicalizerRaisesException() -> None:
    """Verifies that RFC 8785 JCS canonicalizer forbids floats in financial payloads."""
    payloadWithFloat = {
        "skuId": "SKU-001",
        "unitPrice": 4200.50,
        "quantity": 1,
    }
    with pytest.raises(ArithmeticDriftException) as excInfo:
        canonicalizeJson(payloadWithFloat)
    assert "Floating-point value" in str(excInfo.value)


def testTc08ExactZeroDriftIntegerPaiseConservation() -> None:
    """Verifies zero-drift exact integer paise arithmetic conservation across GST splits."""
    # Test case: ₹3,350.00 (335,000 paise) * 50 units = ₹1,67,500.00 (16,750,000 paise)
    unitPricePaise = 335000
    quantity = 50
    taxableSubtotal = computeLineItemTotal(unitPricePaise, quantity)
    assert taxableSubtotal == 16750000

    # 18% GST calculation (Intra-State: 9% CGST + 9% SGST)
    gstBreakdown = computeGstBreakdown(taxableSubtotal, 18, isIntraState=True)
    assert gstBreakdown.cgstPaise == 1507500  # ₹15,075.00
    assert gstBreakdown.sgstPaise == 1507500  # ₹15,075.00
    assert gstBreakdown.igstPaise == 0
    assert gstBreakdown.totalTaxPaise == 3015000  # ₹30,150.00

    # Penny conservation check: CGST + SGST must exactly equal totalTaxPaise
    assert (
        gstBreakdown.cgstPaise + gstBreakdown.sgstPaise
        == gstBreakdown.totalTaxPaise
    )

    # Section 52 TCS Withholding (1% total = 0.5% CGST + 0.5% SGST = 83,750 + 83,750 paise = 167,500 paise)
    tcs = computeTcsWithholding(taxableSubtotal, isIntraState=True)
    assert tcs["tcsCgstPaise"] == 83750  # ₹837.50
    assert tcs["tcsSgstPaise"] == 83750  # ₹837.50
    assert tcs["totalTcsPaise"] == 167500  # ₹1,675.00

    # Gross Settlement Total
    grossTotal = computeCartSettlementTotal(
        taxableSubtotal, gstBreakdown.totalTaxPaise, shippingPaise=0, discountPaise=0
    )
    assert grossTotal == 19765000  # Exactly ₹1,97,650.00 with 0% drift
