"""Schemas for dynamic spot-linked pricing rules and oracle feeds."""

from decimal import Decimal
from enum import Enum
from typing import Literal, Optional
from pydantic import BaseModel, ConfigDict, Field


class SupportedOracleFeedSymbol(str, Enum):
    """Supported oracle spot price feed symbols."""

    GOLD_24K = "MCX_GOLD_24K_INR_PER_GRAM"
    GOLD_22K = "MCX_GOLD_22K_INR_PER_GRAM"
    SILVER = "MCX_SILVER_INR_PER_KG"


# Dynamic Pricing Validation Constants
defaultPurityMultiplier: Decimal = Decimal("1.0")
minPurityMultiplier: Decimal = Decimal("0.0")
maxPurityMultiplier: Decimal = Decimal("1.0")
defaultNetWeightGrams: Decimal = Decimal("0.0")
minNetWeightGrams: Decimal = Decimal("0.0")
defaultPaise: int = 0
minPaise: int = 0
defaultQuoteTtlSecs: int = 60
minQuoteTtlSecs: int = 10
maxQuoteTtlSecs: int = 300


class DynamicPricingRule(BaseModel):
    """Configuration for formulaic spot-rate-linked dynamic pricing."""

    model_config = ConfigDict(frozen=True, extra="forbid")

    pricingType: Literal["STATIC", "FORMULA_SPOT_LINKED"] = "STATIC"
    oracleFeedSymbol: Optional[str] = None
    purityMultiplier: Decimal = Field(
        default=defaultPurityMultiplier,
        ge=minPurityMultiplier,
        le=maxPurityMultiplier,
    )
    netWeightGrams: Decimal = Field(
        default=defaultNetWeightGrams,
        ge=minNetWeightGrams,
    )
    makingChargesPaise: int = Field(default=defaultPaise, ge=minPaise)
    makingChargesType: Literal["FIXED_PAISE", "PERCENTAGE_OF_GOLD"] = "FIXED_PAISE"
    stoneChargesPaise: int = Field(default=defaultPaise, ge=minPaise)
    maxQuoteTtlSeconds: int = Field(
        default=defaultQuoteTtlSecs,
        ge=minQuoteTtlSecs,
        le=maxQuoteTtlSecs,
    )


__all__ = [
    "DynamicPricingRule",
    "SupportedOracleFeedSymbol",
    "defaultNetWeightGrams",
    "defaultPaise",
    "defaultPurityMultiplier",
    "defaultQuoteTtlSecs",
    "maxPurityMultiplier",
    "maxQuoteTtlSecs",
    "minNetWeightGrams",
    "minPaise",
    "minPurityMultiplier",
    "minQuoteTtlSecs",
]
