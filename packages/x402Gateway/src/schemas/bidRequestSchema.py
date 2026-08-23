"""Pydantic schemas for negotiation bids, status, and turn requests/responses."""

from enum import Enum
from typing import Optional
from pydantic import BaseModel, ConfigDict, Field

from ..constants.negotiationConstants import (
    initialEscrowPoolPaise,
    maxNegotiationTurns,
)
from ..escrow.escrowSessionManager import DebitReceipt
from .contractAstSchema import CommercialContractAst


class NegotiationStatus(str, Enum):
    """Lifecycle statuses for negotiation session."""

    IN_PROGRESS = "IN_PROGRESS"
    CONVERGED = "CONVERGED"
    REJECTED = "REJECTED"
    NEGOTIATION_EXHAUSTED = "NEGOTIATION_EXHAUSTED"


class NegotiationStepResult(BaseModel):
    """Step result recorded at each negotiation turn."""

    model_config = ConfigDict(frozen=True, extra="forbid")

    turnNumber: int = Field(ge=1, le=maxNegotiationTurns)
    buyerBidPaise: int = Field(gt=0)
    sellerAskPaise: int = Field(gt=0)
    spreadPaise: int = Field(ge=0)
    isConverged: bool
    cumulativeMicroFeesPaise: int = Field(gt=0)


class EscrowCreateRequest(BaseModel):
    """Request payload for creating a new micro-escrow session."""

    model_config = ConfigDict(frozen=True, extra="forbid")

    buyerAgentDid: str = Field(min_length=1)
    initialHoldPaise: int = Field(default=initialEscrowPoolPaise, gt=0)


class NegotiateTurnRequest(BaseModel):
    """Request payload for executing a negotiation turn."""

    model_config = ConfigDict(frozen=True, extra="forbid")

    skuId: str = Field(min_length=1)
    quantity: int = Field(gt=0)
    turnNumber: int = Field(ge=1, le=maxNegotiationTurns)
    buyerBidPaise: int = Field(gt=0)
    sellerAskPaise: int = Field(gt=0)
    buyerAgentDid: str = Field(min_length=1)
    merchantDid: str = Field(min_length=1)


class NegotiateTurnResponse(BaseModel):
    """Response payload returned after processing a negotiation turn."""

    model_config = ConfigDict(frozen=True, extra="forbid")

    stepResult: NegotiationStepResult
    debitReceipt: Optional[DebitReceipt] = None
    contractAst: Optional[CommercialContractAst] = None
    contractAstHash: Optional[str] = None


__all__ = [
    "EscrowCreateRequest",
    "NegotiateTurnRequest",
    "NegotiateTurnResponse",
    "NegotiationStatus",
    "NegotiationStepResult",
]
