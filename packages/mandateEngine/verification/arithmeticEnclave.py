"""Deterministic Integer Paise Arithmetic Enclave.

Enforces zero-floating-point financial calculations and GST floor division.
"""

from typing import Any

from ..constants.settlementConstants import (
    basisPointsDivisor,
    percentDivisor,
    tcsCgstBasisPoints,
    tcsIgstBasisPoints,
    tcsSgstBasisPoints,
    zeroPaise,
)


def validateIntegerPaise(amount: Any, fieldName: str) -> int:
    """Validates that a financial field is strictly an integer."""
    if isinstance(amount, bool) or not isinstance(amount, int):
        from ..settlement.settlementExceptions import ArithmeticDriftException

        raise ArithmeticDriftException(
            f"Arithmetic drift violation: field '{fieldName}' must be int, got {type(amount).__name__}"
        )
    return amount


def computeLineItemTotal(unitPricePaise: int, quantity: int) -> int:
    """Computes taxable line item total in integer paise."""
    unitPrice = validateIntegerPaise(unitPricePaise, "unitPricePaise")
    qty = validateIntegerPaise(quantity, "quantity")
    if qty <= 0:
        from ..settlement.settlementExceptions import ArithmeticDriftException

        raise ArithmeticDriftException("Quantity must be positive integer")
    if unitPrice < 0:
        from ..settlement.settlementExceptions import ArithmeticDriftException

        raise ArithmeticDriftException("UnitPricePaise cannot be negative")
    return unitPrice * qty


def computeGstBreakdown(
    taxableSubtotalPaise: int,
    gstRatePercent: int,
    isIntraState: bool,
) -> dict[str, int]:
    """Calculates GST breakdown using floor division and exact penny conservation."""
    subtotal = validateIntegerPaise(taxableSubtotalPaise, "taxableSubtotalPaise")
    rate = validateIntegerPaise(gstRatePercent, "gstRatePercent")

    if subtotal < 0 or rate < 0:
        from ..settlement.settlementExceptions import ArithmeticDriftException

        raise ArithmeticDriftException("Subtotal and GST rate must be non-negative")

    gstPaise = (subtotal * rate) // percentDivisor

    if isIntraState:
        cgstRate = rate // 2
        cgstPaise = (subtotal * cgstRate) // percentDivisor
        sgstPaise = gstPaise - cgstPaise
        igstPaise = zeroPaise
    else:
        cgstPaise = zeroPaise
        sgstPaise = zeroPaise
        igstPaise = gstPaise

    totalTaxPaise = cgstPaise + sgstPaise + igstPaise
    return {
        "cgstPaise": cgstPaise,
        "sgstPaise": sgstPaise,
        "igstPaise": igstPaise,
        "totalTaxPaise": totalTaxPaise,
    }


def computeTcsWithholding(
    taxableSubtotalPaise: int,
    isIntraState: bool,
) -> dict[str, int]:
    """Calculates Section 52 TCS withholding on net taxable value."""
    subtotal = validateIntegerPaise(taxableSubtotalPaise, "taxableSubtotalPaise")
    if subtotal < 0:
        from ..settlement.settlementExceptions import ArithmeticDriftException

        raise ArithmeticDriftException("Subtotal must be non-negative")

    if isIntraState:
        tcsCgstPaise = (subtotal * tcsCgstBasisPoints) // basisPointsDivisor
        tcsSgstPaise = (subtotal * tcsSgstBasisPoints) // basisPointsDivisor
        tcsIgstPaise = zeroPaise
    else:
        tcsCgstPaise = zeroPaise
        tcsSgstPaise = zeroPaise
        tcsIgstPaise = (subtotal * tcsIgstBasisPoints) // basisPointsDivisor

    totalTcsPaise = tcsCgstPaise + tcsSgstPaise + tcsIgstPaise
    return {
        "tcsCgstPaise": tcsCgstPaise,
        "tcsSgstPaise": tcsSgstPaise,
        "tcsIgstPaise": tcsIgstPaise,
        "totalTcsPaise": totalTcsPaise,
    }


def computeCartSettlementTotal(
    taxableSubtotalPaise: int,
    totalTaxPaise: int,
    shippingPaise: int = 0,
    discountPaise: int = 0,
) -> int:
    """Recomputes deterministic gross settlement total in integer paise."""
    subtotal = validateIntegerPaise(taxableSubtotalPaise, "taxableSubtotalPaise")
    tax = validateIntegerPaise(totalTaxPaise, "totalTaxPaise")
    shipping = validateIntegerPaise(shippingPaise, "shippingPaise")
    discount = validateIntegerPaise(discountPaise, "discountPaise")

    grossTotal = subtotal + tax + shipping - discount
    if grossTotal < 0:
        from ..settlement.settlementExceptions import ArithmeticDriftException

        raise ArithmeticDriftException("Calculated gross settlement amount cannot be negative")
    return grossTotal
