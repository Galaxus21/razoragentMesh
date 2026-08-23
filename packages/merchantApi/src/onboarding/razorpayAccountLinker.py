"""Razorpay Route linked account validation and split reference builders."""

from ..constants.merchantConstants import (
    minRazorpayAccountIdLength,
    razorpayRouteAccountPrefix,
)


def validateRazorpayAccountId(accountId: str) -> bool:
    """Validates Razorpay Route linked account identifier structure."""
    if not isinstance(accountId, str):
        return False
    cleanedId = accountId.strip()
    if not cleanedId.startswith(razorpayRouteAccountPrefix):
        return False
    return len(cleanedId) >= minRazorpayAccountIdLength


def buildRouteLinkedAccountRef(accountId: str, merchantDid: str) -> dict[str, str]:
    """Constructs structured reference dictionary for Razorpay Route split configuration."""
    if not validateRazorpayAccountId(accountId):
        raise ValueError(f"Invalid Razorpay Route account ID: '{accountId}'")
    if not merchantDid or not isinstance(merchantDid, str):
        raise ValueError("Invalid merchant DID")

    return {
        "account_id": accountId.strip(),
        "merchant_did": merchantDid.strip(),
    }


__all__ = [
    "buildRouteLinkedAccountRef",
    "validateRazorpayAccountId",
]
