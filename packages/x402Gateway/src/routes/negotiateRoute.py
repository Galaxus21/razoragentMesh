"""Negotiation and PoW challenge API routes for Layer 2 x402-INR gateway."""

import time
from typing import Dict, Optional, Tuple
from fastapi import APIRouter, Header, HTTPException, Request

from ..compiler.astContractCompiler import compileCommercialContractAst
from ..constants.negotiationConstants import (
    defaultClientHost,
    endpointChallenge,
    endpointNegotiate,
    headerEscrowToken,
    headerPowChallenge,
    headerPowSolution,
)
from ..escrow.microEscrowClient import DebitReceipt
from ..gatewayExceptions import (
    EscrowSessionNotFoundException,
    InsufficientEscrowBalanceException,
    InvalidProofOfWorkException,
    NegotiationExhaustedException,
    NonMonotonicConcessionViolation,
    PowChallengeExpiredException,
    PowReplayDetectedException,
)
from ..middleware.proofOfWorkMiddleware import (
    Http402ChallengeResponse,
    IngressAntiSpamShield,
)
from ..negotiation.bidStateMachine import (
    RubinsteinStahlNegotiator,
)
from ..schemas.bidRequestSchema import (
    NegotiateTurnRequest,
    NegotiateTurnResponse,
    NegotiationStepResult,
)
from ..schemas.contractAstSchema import CommercialContractAst
from .escrowRoute import defaultEscrowClient

negotiateRouter = APIRouter(tags=["negotiate"])
defaultAntiSpamShield = IngressAntiSpamShield()
activeNegotiators: Dict[str, RubinsteinStahlNegotiator] = {}


@negotiateRouter.get(endpointChallenge, response_model=Http402ChallengeResponse)
async def getPowChallenge(request: Request) -> Http402ChallengeResponse:
    """Generates fresh SHA-256 PoW challenge."""
    clientIp = request.client.host if request.client else defaultClientHost
    return defaultAntiSpamShield.generateChallenge(clientIp)


async def verifyPoWAndDebitEscrow(
    powChallenge: Optional[str],
    powSolution: Optional[str],
    escrowToken: Optional[str],
    turnNumber: int,
) -> DebitReceipt:
    """Verifies PoW headers and debits turn fee from active escrow session."""
    if not powChallenge or not powSolution or not escrowToken:
        raise HTTPException(
            status_code=402,
            detail="x402-INR authentication required: PoW solution and escrow token missing",
        )
    try:
        solNonce = int(powSolution)
        defaultAntiSpamShield.validatePoWSubmission(powChallenge, solNonce)
    except (ValueError, InvalidProofOfWorkException, PowChallengeExpiredException) as err:
        raise HTTPException(status_code=403, detail=f"Invalid PoW solution: {err}")
    except PowReplayDetectedException as err:
        raise HTTPException(status_code=409, detail=f"Replay detected: {err}")

    try:
        return await defaultEscrowClient.debitTurnFee(
            sessionToken=escrowToken,
            turnIndex=turnNumber,
        )
    except (EscrowSessionNotFoundException, InsufficientEscrowBalanceException) as err:
        raise HTTPException(status_code=402, detail=str(err))


def getOrCreateNegotiator(
    sessionKey: str,
    skuId: str,
    quantity: int,
    balancePaise: int,
) -> RubinsteinStahlNegotiator:
    """Retrieves or instantiates active session negotiator."""
    if sessionKey not in activeNegotiators:
        activeNegotiators[sessionKey] = RubinsteinStahlNegotiator(
            skuId=skuId,
            quantity=quantity,
            escrowBalancePaise=balancePaise,
        )
    return activeNegotiators[sessionKey]


def compileContractIfConverged(
    step: NegotiationStepResult,
    payload: NegotiateTurnRequest,
    sessionKey: str,
) -> Tuple[Optional[CommercialContractAst], Optional[str]]:
    """Compiles immutable AST if negotiation has reached convergence."""
    if not step.isConverged:
        return None, None
    now = int(time.time())
    contractAst, astHash = compileCommercialContractAst(
        skuId=payload.skuId,
        quantity=payload.quantity,
        agreedUnitPrice=payload.sellerAskPaise,
        turns=payload.turnNumber,
        buyerDid=payload.buyerAgentDid,
        merchantDid=payload.merchantDid,
        timestamp=now,
    )
    activeNegotiators.pop(sessionKey, None)
    return contractAst, astHash


@negotiateRouter.post(endpointNegotiate, response_model=NegotiateTurnResponse)
async def negotiateTurn(
    payload: NegotiateTurnRequest,
    powChallenge: Optional[str] = Header(None, alias=headerPowChallenge),
    powSolution: Optional[str] = Header(None, alias=headerPowSolution),
    escrowToken: Optional[str] = Header(None, alias=headerEscrowToken),
) -> NegotiateTurnResponse:
    """Processes single negotiation turn under PoW and micro-escrow verification."""
    debitReceipt = await verifyPoWAndDebitEscrow(
        powChallenge, powSolution, escrowToken, payload.turnNumber
    )
    sessionKey = f"{payload.buyerAgentDid}:{payload.skuId}"
    negotiator = getOrCreateNegotiator(
        sessionKey, payload.skuId, payload.quantity, debitReceipt.remainingBalancePaise
    )

    try:
        step = negotiator.executeTurn(
            turnNumber=payload.turnNumber,
            buyerBidPaise=payload.buyerBidPaise,
            sellerAskPaise=payload.sellerAskPaise,
        )
    except NonMonotonicConcessionViolation as err:
        raise HTTPException(status_code=400, detail=str(err))
    except NegotiationExhaustedException as err:
        raise HTTPException(status_code=409, detail=str(err))

    contractAst, astHash = compileContractIfConverged(step, payload, sessionKey)

    return NegotiateTurnResponse(
        stepResult=step,
        debitReceipt=debitReceipt,
        contractAst=contractAst,
        contractAstHash=astHash,
    )


__all__ = [
    "activeNegotiators",
    "compileContractIfConverged",
    "defaultAntiSpamShield",
    "getOrCreateNegotiator",
    "getPowChallenge",
    "negotiateRouter",
    "negotiateTurn",
    "verifyPoWAndDebitEscrow",
]
