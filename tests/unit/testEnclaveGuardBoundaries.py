"""Guard-boundary tests for the arithmetic enclave's input validation and settlement floor.

Kills two coverage-gap mutants in
packages/mandateEngine/verification/arithmeticEnclave.py that the existing suite
accepts in silence:
  - L242 type guard in normalize_inr_to_paise (raise -> pass)
  - L230 gross floor in compute_cart_settlement_total (gross < 0 -> gross <= 0)
"""

import pytest

from razoragentMesh.packages.mandateEngine.verification.arithmeticEnclave import (
    ArithmeticDriftException,
    compute_cart_settlement_total,
    normalize_inr_to_paise,
)


class _PriceLike:
    """Attacker-shaped object whose __str__ is a parseable decimal string.

    Without the L242 type guard, Decimal(str(value)) would happily swallow this
    and mint paise from an arbitrary object — the exact prior-probe failure.
    """

    def __str__(self) -> str:
        return "99.99"


def testNormalizeRejectsBoolTrue() -> None:
    """L242 guard: True must not normalize to 100 paise.

    Kills the raise->pass mutant for the bool arm. isinstance(True, int) is True
    in Python, so the plain (str, int, Decimal) isinstance check would ACCEPT a
    bool and str(True)=='True' would then fail to parse — but the explicit bool
    check must lead the condition and reject it as an unsupported type first.
    A bool leaking through would let a truthy flag become a 100-paise charge.
    """
    with pytest.raises(ArithmeticDriftException):
        normalize_inr_to_paise(True)


def testNormalizeRejectsBoolFalse() -> None:
    """L242 guard: False is an int subclass and must still be rejected.

    Kills the raise->pass mutant for the bool arm. Because isinstance(False, int)
    is True, only the explicit leading bool check stops False from being treated
    as the integer 0 and silently normalized to 0 paise.
    """
    with pytest.raises(ArithmeticDriftException):
        normalize_inr_to_paise(False)


def testNormalizeRejectsArbitraryObjectWithNumericStr() -> None:
    """L242 guard: a custom object with a numeric __str__ must be rejected.

    Kills the raise->pass mutant for the not-isinstance arm. If removed, a
    _PriceLike() str-ifying to '99.99' becomes 9999 paise — an unvalidated,
    non-currency object minting real money into a settlement.
    """
    with pytest.raises(ArithmeticDriftException):
        normalize_inr_to_paise(_PriceLike())


def testNormalizeRejectsList() -> None:
    """L242 guard: a list is not a supported currency type and must be rejected.

    Kills the raise->pass mutant. str([100]) == '[100]' would fail decimal
    parsing downstream, but the type guard must reject collections up front so
    the error names the type, not a parse failure.
    """
    with pytest.raises(ArithmeticDriftException):
        normalize_inr_to_paise([100])


def testNormalizeRejectsNone() -> None:
    """L242 guard: None must be rejected as an unsupported currency type.

    Kills the raise->pass mutant. Without the guard, str(None) == 'None' would
    only fail later at Decimal parsing; the type guard is what stops a missing
    amount from ever reaching the arithmetic path.
    """
    with pytest.raises(ArithmeticDriftException):
        normalize_inr_to_paise(None)


def testSettlementGrossExactlyZeroIsAllowed() -> None:
    """L230 lower side: a gross of exactly 0 must return 0, not raise.

    A fully-discounted / free cart (subtotal+tax+shipping == discount) is a
    legitimate settlement — validate_integer_paise permits zero (allow_zero
    defaults True), and the floor guard rejects only NEGATIVE gross. If the
    boundary were mutated to `gross <= 0`, this valid zero-value settlement
    would be wrongly rejected. Pins the permitted side of the boundary.
    """
    gross = compute_cart_settlement_total(
        taxableSubtotalPaise=50000, totalTaxPaise=9000, shippingPaise=1000, discountPaise=60000
    )
    assert gross == 0


def testSettlementGrossMinusOneRaises() -> None:
    """L230 upper side: a gross of exactly -1 must raise.

    Kills the `gross < 0` -> `gross <= 0` mutant from the other direction: the
    mutant still raises at -1, so pairing this with the zero-allowed test is what
    forces the boundary to sit at 0 and not 1. A negative gross escaping this
    guard would settle a cart for a negative amount — money paid out, not in.
    """
    with pytest.raises(ArithmeticDriftException):
        compute_cart_settlement_total(
            taxableSubtotalPaise=0, totalTaxPaise=0, shippingPaise=0, discountPaise=1
        )
