"""Strict integer-paise financial currency normalizer and drift protector."""

from decimal import Decimal, InvalidOperation, ROUND_HALF_UP
from typing import Union

from ..constants.merchantConstants import paisePerRupee


class ArithmeticDriftException(Exception):
    """Raised when float arithmetic or invalid financial structures are encountered."""

    def __init__(self, message: str) -> None:
        super().__init__(message)


def normalizeInrToPaise(value: Union[str, int, Decimal]) -> int:
    """Converts INR currency representation to integer paise using exact decimal arithmetic."""
    # Floating-point values introduce binary rounding errors into ledgers and are strictly forbidden
    if isinstance(value, float):
        raise ArithmeticDriftException(
            f"Floating-point values are strictly forbidden in financial paths: {value}"
        )

    if not isinstance(value, (str, int, Decimal)):
        raise ArithmeticDriftException(
            f"Unsupported type for financial currency normalization: {type(value).__name__}"
        )

    try:
        decimalRepresentation = Decimal(str(value).strip())
    except (InvalidOperation, ValueError) as err:
        raise ArithmeticDriftException(
            f"Failed to parse numeric string into decimal currency: {value}"
        ) from err

    if decimalRepresentation < Decimal("0"):
        raise ArithmeticDriftException(
            f"Negative financial amounts are strictly forbidden: {value}"
        )

    # Scale from standard INR units to paise with standard banking half-up rounding
    scaledPaise = (decimalRepresentation * Decimal(str(paisePerRupee))).quantize(
        Decimal("1"),
        rounding=ROUND_HALF_UP,
    )
    return int(scaledPaise)


__all__ = [
    "ArithmeticDriftException",
    "normalizeInrToPaise",
]
