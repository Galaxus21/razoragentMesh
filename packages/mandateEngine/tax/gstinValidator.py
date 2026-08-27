"""Canonical Indian GSTIN (Goods and Services Tax Identification Number) Luhn Mod-36 Validator.

Statutory Structure (15 characters):
- Positions 1-2: 2-digit State Code (01-38)
- Positions 3-12: 10-character PAN of the entity (5 letters, 4 digits, 1 letter)
- Position 13: 1-character entity code (1-9, A-Z)
- Position 14: Default character 'Z'
- Position 15: Luhn Mod-36 checksum character (0-9, A-Z)
"""

import re
from typing import Any

# Character lookup table for Radix-36 modulo arithmetic
gstCharsTable: str = "0123456789ABCDEFGHIJKLMNOPQRSTUVWXYZ"
gstinLength: int = 15
gstinPrefixLength: int = 14
gstinRegexPattern: str = r"^(?:0[1-9]|[1-2][0-9]|3[0-8])[A-Z]{5}[0-9]{4}[A-Z]{1}[1-9A-Z]{1}Z[0-9A-Z]{1}$"


def computeGstinChecksum(gstin14: str) -> str:
    """Calculates standard Indian GSTIN 15th character checksum using Luhn mod-36 algorithm.

    Args:
        gstin14: The 14-character GSTIN prefix.

    Returns:
        The single check character (0-9 or A-Z).

    Raises:
        ValueError: If input is not a string, is not 14 characters, or contains invalid characters.
    """
    if not isinstance(gstin14, str):
        raise ValueError(f"GSTIN prefix must be a string, got {type(gstin14).__name__}")

    cleanPrefix = gstin14.strip().upper()
    if len(cleanPrefix) != gstinPrefixLength:
        raise ValueError(f"GSTIN prefix must be exactly {gstinPrefixLength} characters, got {len(cleanPrefix)}")

    total = 0
    for idx in range(gstinPrefixLength):
        char = cleanPrefix[idx]
        if char not in gstCharsTable:
            raise ValueError(f"Invalid character '{char}' at index {idx} in GSTIN prefix")
        val = gstCharsTable.index(char)
        factor = 1 if (idx % 2 == 0) else 2
        product = val * factor
        total += (product // 36) + (product % 36)

    checkCode = (36 - (total % 36)) % 36
    return gstCharsTable[checkCode]


def validateGstin(gstin: Any) -> bool:
    """Validates an Indian GSTIN against statutory format regex and Luhn Mod-36 checksum.

    Args:
        gstin: Candidate GSTIN string.

    Returns:
        True if valid format and checksum, False otherwise.
    """
    if not isinstance(gstin, str):
        return False
    if len(gstin) != gstinLength:
        return False
    if not re.match(gstinRegexPattern, gstin):
        return False
    try:
        expectedCheckChar = computeGstinChecksum(gstin[:gstinPrefixLength])
        return gstin[gstinPrefixLength] == expectedCheckChar
    except Exception:
        return False


__all__ = [
    "computeGstinChecksum",
    "gstCharsTable",
    "gstinLength",
    "gstinPrefixLength",
    "gstinRegexPattern",
    "validateGstin",
]
