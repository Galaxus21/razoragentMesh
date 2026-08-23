"""Pydantic v2 schema for ExecutionMandate (M_E) binding Intent and Cart mandates."""

from typing import Literal
from pydantic import BaseModel, ConfigDict, Field


class ExecutionMandate(BaseModel):
    """Cryptographic commitment by buyer agent chaining Intent (M_I) and Cart (M_C)."""

    model_config = ConfigDict(frozen=True, extra="forbid")

    executionId: str = Field(min_length=1, description="Unique execution mandate ID")
    buyerAgentDid: str = Field(
        pattern=r"^did:agent:[0-9a-f]{64}$",
        description="DID of the autonomous buyer agent",
    )
    intentMandateHash: str = Field(
        min_length=64,
        max_length=64,
        description="SHA-256 digest of canonical JCS IntentMandate (M_I)",
    )
    cartMandateHash: str = Field(
        min_length=64,
        max_length=64,
        description="SHA-256 digest of canonical JCS CartMandate (M_C)",
    )
    settlementAmountPaise: int = Field(
        gt=0,
        description="Final settlement amount in integer paise",
    )
    currency: Literal["INR"] = Field(
        default="INR",
        description="Currency code (strictly INR)",
    )
    upiCircleToken: str = Field(
        min_length=1,
        description="Delegated UPI Circle execution token",
    )
    nonce: str = Field(
        min_length=1,
        description="Single-use cryptographic nonce",
    )
    timestamp: int = Field(
        gt=0,
        description="Unix execution timestamp",
    )
    agentSignature: str = Field(
        min_length=128,
        max_length=128,
        description="Ed25519 signature by buyer agent",
    )
