"""Pydantic v2 schema for IntentMandate (M_I) signed by human/CFO principal."""

from typing import Literal
from pydantic import BaseModel, ConfigDict, Field


class IntentMandate(BaseModel):
    """Delegated authorization and spending bounds from principal to buyer agent."""

    model_config = ConfigDict(frozen=True, extra="forbid")

    mandateId: str = Field(
        min_length=1,
        description="Unique identifier for the intent mandate",
    )
    userDid: str = Field(
        pattern=r"^did:agent:[0-9a-f]{64}$",
        description="DID of the principal/user",
    )
    delegatedAgentDid: str = Field(
        pattern=r"^did:agent:[0-9a-f]{64}$",
        description="DID of the authorized autonomous buyer agent",
    )
    maxBudgetPaise: int = Field(
        gt=0,
        description="Maximum cumulative spend cap in integer paise",
    )
    currency: Literal["INR"] = Field(
        default="INR",
        description="Currency code (strictly INR)",
    )
    authorizedCategories: list[str] = Field(
        default_factory=list,
        description="Allowed product category tags",
    )
    validUntilTimestamp: int = Field(
        gt=0,
        description="Unix timestamp when delegation expires",
    )
    upiCircleDelegationToken: str = Field(
        min_length=1,
        description="NPCI UPI Circle delegation grant token",
    )
    singleTransactionLimitPaise: int = Field(
        gt=0,
        description="Single transaction maximum ceiling in integer paise",
    )
    nonce: str = Field(
        min_length=1,
        description="Single-use cryptographic nonce",
    )
    timestamp: int = Field(
        gt=0,
        description="Unix creation timestamp",
    )
    userSignature: str = Field(
        min_length=128,
        max_length=128,
        description="Ed25519 signature by user principal",
    )
