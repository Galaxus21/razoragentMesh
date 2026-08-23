"""Autonomous negotiation policy schemas for merchant pricing and concession limits."""

from pydantic import BaseModel, ConfigDict, Field

# Policy Boundary Constants
minMarginFloorBps: int = 0
maxMarginFloorBps: int = 10000
defaultMinimumOrderQuantity: int = 1
minOrderQuantity: int = 1
defaultAutoAcceptSpreadPaise: int = 0
minAutoAcceptSpreadPaise: int = 0
defaultMaxNegotiationTurns: int = 5
minNegotiationTurns: int = 1
maxNegotiationTurnsLimit: int = 10


class NegotiationPolicy(BaseModel):
    """Merchant autonomous negotiation rule parameters and guardrails."""

    model_config = ConfigDict(frozen=True, extra="forbid")

    merchantDid: str
    marginFloorBps: int = Field(ge=minMarginFloorBps, le=maxMarginFloorBps)
    minimumOrderQuantity: int = Field(
        default=defaultMinimumOrderQuantity,
        ge=minOrderQuantity,
    )
    autoAcceptSpreadPaise: int = Field(
        default=defaultAutoAcceptSpreadPaise,
        ge=minAutoAcceptSpreadPaise,
    )
    maxNegotiationTurns: int = Field(
        default=defaultMaxNegotiationTurns,
        ge=minNegotiationTurns,
        le=maxNegotiationTurnsLimit,
    )
    createdAtTimestamp: int
    updatedAtTimestamp: int


__all__ = [
    "NegotiationPolicy",
    "defaultAutoAcceptSpreadPaise",
    "defaultMaxNegotiationTurns",
    "defaultMinimumOrderQuantity",
    "maxMarginFloorBps",
    "maxNegotiationTurnsLimit",
    "minAutoAcceptSpreadPaise",
    "minMarginFloorBps",
    "minNegotiationTurns",
    "minOrderQuantity",
]
