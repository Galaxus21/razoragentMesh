"""Pydantic v2 schema for AmendmentMandate (M_A) for self-healing cart patching."""

from pydantic import BaseModel, ConfigDict, Field


class AmendmentMandate(BaseModel):
    """Dual-signed amendment for out-of-stock substitutions or price updates."""

    model_config = ConfigDict(frozen=True, extra="forbid")

    amendmentId: str = Field(min_length=1, description="Unique amendment identifier")
    previousCartMandateHash: str = Field(
        min_length=64,
        max_length=64,
        description="SHA-256 hash of original CartMandate",
    )
    newCartMandateHash: str = Field(
        min_length=64,
        max_length=64,
        description="SHA-256 hash of amended CartMandate",
    )
    substitutedSkuMapping: dict[str, str] = Field(
        description="Mapping from original out-of-stock SKU to substitute SKU",
    )
    priceDeltaPaise: int = Field(
        description="Signed integer delta in paise (positive for increase, negative for decrease)",
    )
    amendmentReason: str = Field(
        min_length=1,
        max_length=200,
        description="Justification for amendment (e.g. OOS substitute)",
    )
    nonce: str = Field(
        min_length=1,
        description="Single-use cryptographic nonce",
    )
    timestamp: int = Field(
        gt=0,
        description="Unix creation timestamp",
    )
    agentSignature: str = Field(
        min_length=128,
        max_length=128,
        description="Ed25519 signature by buyer agent",
    )
    merchantSignature: str = Field(
        min_length=128,
        max_length=128,
        description="Ed25519 signature by merchant",
    )
