"""Escrow management API routes for Layer 2 x402-INR gateway."""

from fastapi import APIRouter, Depends, Header, HTTPException, status

from ..constants.negotiationConstants import (
    endpointEscrow,
    endpointEscrowRelease,
    headerEscrowToken,
)
from ..dependencies import (
    EscrowClient,
    defaultEscrowClient,
    getEscrowClient,
)
from ..escrow.microEscrowClient import (
    EscrowRefundReceipt,
    EscrowSession,
)
from ..gatewayExceptions import EscrowSessionNotFoundException
from ..schemas.bidRequestSchema import EscrowCreateRequest

escrowRouter = APIRouter(tags=["escrow"])


@escrowRouter.post(
    endpointEscrow,
    response_model=EscrowSession,
    status_code=status.HTTP_201_CREATED,
)
async def createEscrowSession(
    payload: EscrowCreateRequest,
    escrowClient: EscrowClient = Depends(getEscrowClient),
) -> EscrowSession:
    """Allocates ₹50 micro-escrow session on UPI Circle rails."""
    return await escrowClient.createEscrowSession(
        buyerAgentDid=payload.buyerAgentDid,
        initialHoldPaise=payload.initialHoldPaise,
    )


@escrowRouter.post(endpointEscrowRelease, response_model=EscrowRefundReceipt)
async def releaseEscrow(
    sessionToken: str = Header(..., alias=headerEscrowToken),
    escrowClient: EscrowClient = Depends(getEscrowClient),
) -> EscrowRefundReceipt:
    """Releases unspent escrow balance back to buyer pool."""
    try:
        return await escrowClient.releaseUnspentEscrow(sessionToken)
    except EscrowSessionNotFoundException as err:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail=str(err))


__all__ = [
    "createEscrowSession",
    "defaultEscrowClient",
    "escrowRouter",
    "releaseEscrow",
]
