"""Strict integer-paise financial currency normalizer and drift protector."""

from decimal import Decimal
from typing import Union

try:
    from razoragentMesh.packages.mandateEngine.verification.arithmeticEnclave import (
        ArithmeticDriftException,
        normalizeInrToPaise,
        normalize_inr_to_paise,
    )
except ImportError:
    from packages.mandateEngine.verification.arithmeticEnclave import (
        ArithmeticDriftException,
        normalizeInrToPaise,
        normalize_inr_to_paise,
    )

__all__ = [
    "ArithmeticDriftException",
    "normalizeInrToPaise",
    "normalize_inr_to_paise",
]

