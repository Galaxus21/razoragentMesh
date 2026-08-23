"""Escrow management API routes for Layer 2 x402-INR gateway."""

from fastapi import APIRouter, Header, HTTPException

from ..constants.negotiationConstants import (
    endpointEscrow,
    endpointEscrowRelease,
    headerEscrowToken,
)
from ..escrow.microEscrowClient import (
    EscrowRefundReceipt,
    EscrowSession,
    MicroEscrowClient,
)
from ..gatewayExceptions import EscrowSessionNotFoundException
from ..schemas.bidRequestSchema import EscrowCreateRequest

escrowRouter = APIRouter(tags=["escrow"])
defaultEscrowClient = MicroEscrowClient()


@escrowRouter.post(endpointEscrow, response_model=EscrowSession)
async def createEscrowSession(payload: EscrowCreateRequest) -> EscrowSession:
    """Allocates ₹50 micro-escrow session on UPI Circle rails."""
    return await defaultEscrowClient.createEscrowSession(
        buyerAgentDid=payload.buyerAgentDid,
        initialHoldPaise=payload.initialHoldPaise,
    )


@escrowRouter.post(endpointEscrowRelease, response_model=EscrowRefundReceipt)
async def releaseEscrow(
    sessionToken: str = Header(..., alias=headerEscrowToken),
) -> EscrowRefundReceipt:
    """Releases unspent escrow balance back to buyer pool."""
    try:
        return await defaultEscrowClient.releaseUnspentEscrow(sessionToken)
    except EscrowSessionNotFoundException as err:
        raise HTTPException(status_code=404, detail=str(err))


__all__ = [
    "createEscrowSession",
    "defaultEscrowClient",
    "escrowRouter",
    "releaseEscrow",
]
