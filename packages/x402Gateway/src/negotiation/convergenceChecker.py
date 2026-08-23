"""Spread calculation, monotonicity validation, and convergence checking."""

from typing import Optional

from ..gatewayExceptions import NonMonotonicConcessionViolation


def computeSpread(sellerAskPaise: int, buyerBidPaise: int) -> int:
    """Computes non-negative spread between seller ask and buyer bid in paise."""
    return max(0, sellerAskPaise - buyerBidPaise)


def checkConvergence(buyerBidPaise: int, sellerAskPaise: int, epsilonPaise: int = 0) -> bool:
    """Checks whether buyer bid meets or exceeds seller ask within optional epsilon."""
    return buyerBidPaise >= (sellerAskPaise - epsilonPaise)


def validateMonotonicity(
    currentBuyerBidPaise: int,
    currentSellerAskPaise: int,
    previousBuyerBidPaise: Optional[int],
    previousSellerAskPaise: Optional[int],
) -> None:
    """Enforces monotonic concession rules for buyer and seller turns."""
    if previousBuyerBidPaise is not None and currentBuyerBidPaise < previousBuyerBidPaise:
        raise NonMonotonicConcessionViolation("Buyer bid cannot decrease")
    if previousSellerAskPaise is not None and currentSellerAskPaise > previousSellerAskPaise:
        raise NonMonotonicConcessionViolation("Seller ask cannot increase")


__all__ = [
    "checkConvergence",
    "computeSpread",
    "validateMonotonicity",
]
