"""Autonomous negotiation policy schemas for merchant pricing and concession limits.

`negotiationEnabled` is the merchant's opt-in. It defaults to False, and the x402-INR gateway
refuses to negotiate a SKU whose merchant has not turned it on -- so a merchant who never opens
this screen sells at their listed price and nothing else. Opt-out would have been the cheaper
default to write and the wrong one: price discovery on someone's inventory without their consent
is not a feature they forgot to configure.
"""

from pydantic import BaseModel, ConfigDict, Field

# Policy Boundary Constants
defaultNegotiationEnabled: bool = False
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
    # The opt-in itself. Everything below only describes HOW this merchant negotiates; this field
    # decides WHETHER they do. Defaulted rather than required so that a policy written before this
    # field existed still loads -- and loads as "off".
    negotiationEnabled: bool = defaultNegotiationEnabled
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
    "defaultNegotiationEnabled",
    "defaultMaxNegotiationTurns",
    "defaultMinimumOrderQuantity",
    "maxMarginFloorBps",
    "maxNegotiationTurnsLimit",
    "minAutoAcceptSpreadPaise",
    "minMarginFloorBps",
    "minNegotiationTurns",
    "minOrderQuantity",
]
