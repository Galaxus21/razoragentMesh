"""Seller-side margin floor and counter-ask evaluation logic."""

from typing import Optional

from ..constants.negotiationConstants import (
    basisPointsDivisor,
    minConcessionPaise,
    sellerMarginFloorBps,
)


def evaluateMargin(
    wholesaleCostPaise: int,
    askPaise: int,
    marginFloorBps: int = sellerMarginFloorBps,
) -> bool:
    """Evaluates whether seller ask price satisfies the minimum margin floor."""
    minRequiredPaise = wholesaleCostPaise + (wholesaleCostPaise * marginFloorBps) // basisPointsDivisor
    return askPaise >= minRequiredPaise


def computeSellerCounterAsk(
    initialAskPaise: int,
    buyerBidPaise: int,
    turnIndex: int,
    stepConcessionPaise: int = minConcessionPaise,
    costFloorPaise: Optional[int] = None,
) -> int:
    """Calculates deterministic seller concession based on turn progression and cost floor."""
    stepConcession = stepConcessionPaise * turnIndex
    counterAsk = max(initialAskPaise - stepConcession, buyerBidPaise)
    if costFloorPaise is not None:
        counterAsk = max(counterAsk, costFloorPaise)
    return counterAsk


__all__ = [
    "computeSellerCounterAsk",
    "evaluateMargin",
]
