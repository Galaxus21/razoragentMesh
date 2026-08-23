"""Dynamic pricing engine for bullion and commodity spot-rate valuation."""

from dataclasses import dataclass
from decimal import Decimal
from typing import Optional

from ..constants.merchantConstants import (
    basisPointsDivisor,
    defaultQuoteTtlSeconds,
    percentDivisor,
    zeroPaise,
)
from ..schemas.dynamicPricingSchema import DynamicPricingRule
from .spotRateOracle import SpotRateOracle


@dataclass(frozen=True)
class SpotLinkedQuote:
    """Immutable price quotation derived dynamically from bullion spot oracle."""

    unitPricePaise: int
    goldCostPaise: int
    makingChargesPaise: int
    stoneChargesPaise: int
    gstPaise: int
    expiresAtTimestamp: int
    oracleFeedSymbol: str
    spotRatePerGramPaise: int


class StalePriceQuoteException(Exception):
    """Raised when an operation attempts to evaluate or settle an expired price quote."""

    def __init__(self, deltaMs: int) -> None:
        self.deltaMs = deltaMs
        super().__init__(f"Price quote is stale by {deltaMs}ms")


def verifyQuoteNotExpired(expiresAtTimestamp: int, currentTimestamp: int) -> None:
    """Guards against stale quotations by validating against current timestamp."""
    if currentTimestamp > expiresAtTimestamp:
        timeDelta = currentTimestamp - expiresAtTimestamp
        # Convert seconds timestamp delta to milliseconds for audit trail
        deltaMs = timeDelta * 1000 if timeDelta < 100000000 else timeDelta
        raise StalePriceQuoteException(deltaMs=deltaMs)


def _computeGoldCostPaise(
    netWeightGrams: Decimal,
    spotRatePerGramPaise: int,
    purityMultiplier: Decimal,
) -> int:
    """Calculates pure bullion cost before fabrication and tax."""
    rawCost = (
        Decimal(str(netWeightGrams))
        * Decimal(str(spotRatePerGramPaise))
        * Decimal(str(purityMultiplier))
    )
    return int(rawCost)


def _computeMakingChargesPaise(
    rule: DynamicPricingRule,
    goldCostPaise: int,
) -> int:
    """Determines making charges from basis points or flat paise."""
    makingChargeBps = getattr(rule, "makingChargeBps", None)
    if makingChargeBps is not None and makingChargeBps > 0:
        return (goldCostPaise * makingChargeBps) // basisPointsDivisor

    makingChargesType = getattr(rule, "makingChargesType", None)
    if makingChargesType == "PERCENTAGE_OF_GOLD":
        return (goldCostPaise * rule.makingChargesPaise) // basisPointsDivisor

    if getattr(rule, "makingChargesPaise", None) is not None:
        return rule.makingChargesPaise

    return zeroPaise


async def computeSpotLinkedQuote(
    rule: DynamicPricingRule,
    oracle: SpotRateOracle,
    gstRatePercent: int,
    currentTimestamp: int,
) -> SpotLinkedQuote:
    """Evaluates dynamic pricing rule against live oracle into an integer-paise quote."""
    symbol = rule.oracleFeedSymbol if rule.oracleFeedSymbol else "MCX_GOLD_24K_INR_PER_GRAM"
    spotRatePerGramPaise = await oracle.getSpotRatePerGramPaise(symbol)
    goldCostPaise = _computeGoldCostPaise(
        rule.netWeightGrams,
        spotRatePerGramPaise,
        rule.purityMultiplier,
    )
    makingChargesPaise = _computeMakingChargesPaise(rule, goldCostPaise)
    stoneChargesPaise = rule.stoneChargesPaise if rule.stoneChargesPaise is not None else zeroPaise

    taxableAmountPaise = goldCostPaise + makingChargesPaise + stoneChargesPaise
    gstPaise = (taxableAmountPaise * gstRatePercent) // percentDivisor
    unitPricePaise = taxableAmountPaise + gstPaise

    ttlSeconds = rule.maxQuoteTtlSeconds if rule.maxQuoteTtlSeconds > 0 else defaultQuoteTtlSeconds
    expiresAtTimestamp = currentTimestamp + ttlSeconds

    return SpotLinkedQuote(
        unitPricePaise=unitPricePaise,
        goldCostPaise=goldCostPaise,
        makingChargesPaise=makingChargesPaise,
        stoneChargesPaise=stoneChargesPaise,
        gstPaise=gstPaise,
        expiresAtTimestamp=expiresAtTimestamp,
        oracleFeedSymbol=symbol,
        spotRatePerGramPaise=spotRatePerGramPaise,
    )


__all__ = [
    "SpotLinkedQuote",
    "StalePriceQuoteException",
    "computeSpotLinkedQuote",
    "verifyQuoteNotExpired",
]
