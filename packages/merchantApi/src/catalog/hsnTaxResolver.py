"""HSN code validation and GST statutory tax rate resolution."""

import re
from typing import Optional

from ..constants.hsnCodeDirectory import resolveGstRate
from ..constants.merchantConstants import (
    hsnCodeRegexPattern,
    maxHsnCodeLength,
    minHsnCodeLength,
)

_hsnCompiledPattern: re.Pattern[str] = re.compile(hsnCodeRegexPattern)


def validateHsnCode(hsnCode: Optional[str]) -> bool:
    """Validates if the provided string complies with Indian HSN format (4 to 8 numeric digits)."""
    if not isinstance(hsnCode, str):
        return False
    codeLength = len(hsnCode)
    if codeLength < minHsnCodeLength or codeLength > maxHsnCodeLength:
        return False
    return bool(_hsnCompiledPattern.fullmatch(hsnCode))


def resolveHsnGstRate(hsnCode: str) -> int:
    """Resolves statutory GST rate percentage for a given valid Indian HSN code."""
    if not validateHsnCode(hsnCode):
        raise ValueError(f"Malformed Indian HSN code: '{hsnCode}'. Must be 4 to 8 numeric digits.")
    return resolveGstRate(hsnCode)


__all__ = [
    "resolveHsnGstRate",
    "validateHsnCode",
]
