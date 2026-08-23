"""Pydantic schemas for x402 challenge and verification results."""

from typing import Optional
from pydantic import BaseModel, ConfigDict, Field

from ..constants.negotiationConstants import (
    microFeePerTurnPaise,
    powLeadingZeros,
    protocolName,
)


class Http402ChallengeResponse(BaseModel):
    """Structured challenge response emitted when x402 PoW/escrow is required."""

    model_config = ConfigDict(frozen=True, extra="forbid")

    statusCode: int = 402
    wwwAuthenticate: str = protocolName
    challengeToken: str = Field(min_length=1)
    tokenCostPaise: int = microFeePerTurnPaise
    powDifficultyZeros: int = powLeadingZeros


class PowVerificationResult(BaseModel):
    """Outcome of verifying a proof-of-work solution."""

    model_config = ConfigDict(frozen=True, extra="forbid")

    isValid: bool
    challengeToken: str
    computedDigest: str
    errorMessage: Optional[str] = None


__all__ = [
    "Http402ChallengeResponse",
    "PowVerificationResult",
]
