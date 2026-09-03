"""Negotiation and PoW challenge API routes for Layer 2 x402-INR gateway.

There is no merchant-side agent in this mesh. The merchant is represented here by their stored
policy, and `negotiateTurn` will not run at all unless that policy exists and says
`negotiationEnabled` -- negotiation is opt-in per merchant. Everything about the seller's side of
the bargain (who the merchant is, what the item lists at, how far below list they will go) comes
from `resolveMerchantNegotiationTerms`, which reads merchant-written Redis records. The request
body's `sellerAskPaise` and `merchantDid` are treated as a buyer's *proposal*, never as fact.
"""

import logging
import time
from typing import Any, Dict, Optional, Tuple
from fastapi import APIRouter, Depends, Header, HTTPException, Request

from ..compiler.astContractCompiler import compileCommercialContractAst
from ..config import getGatewaySettings
from ..constants.gatewayConstants import (
    httpStatusBadRequest, httpStatusConflict,
    httpStatusForbidden, httpStatusPaymentRequired,
)
from ..constants.negotiationConstants import (
    defaultClientHost, endpointChallenge, endpointNegotiate,
    headerEscrowToken, headerPowChallenge, headerPowSolution,
)
from ..dependencies import (
    AntiSpamSybilShield, EscrowClient, defaultAntiSpamShield,
    defaultEscrowClient, defaultPolicyRedisClient, getAntiSpamShield,
    getEscrowClient, getGatewayRedisClient,
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
)
from ..negotiation.bidStateMachine import (
    RubinsteinStahlNegotiator,
)
from ..negotiation.merchantTerms import (
    MerchantNegotiationTerms,
    clampSellerAskPaise,
    resolveMerchantNegotiationTerms,
)
from ..schemas.bidRequestSchema import (
    NegotiateTurnRequest,
    NegotiateTurnResponse,
    NegotiationStepResult,
)
from ..schemas.contractAstSchema import CommercialContractAst

logger = logging.getLogger(__name__)

defaultMerchantFallbackDid: str = "did:agent:merchant_default"
activeNegotiators: Dict[str, RubinsteinStahlNegotiator] = {}

negotiateRouter = APIRouter(tags=["negotiate"])


@negotiateRouter.get(endpointChallenge, response_model=Http402ChallengeResponse)
async def getPowChallenge(
    request: Request,
    antiSpamShield: AntiSpamSybilShield = Depends(getAntiSpamShield),
) -> Http402ChallengeResponse:
    """Generates fresh SHA-256 PoW challenge."""
    clientIp = request.client.host if request.client else defaultClientHost
    return antiSpamShield.generateChallenge(clientIp)


@negotiateRouter.post(endpointNegotiate, response_model=NegotiateTurnResponse)
async def negotiateTurn(
    payload: NegotiateTurnRequest,
    powChallenge: Optional[str] = Header(None, alias=headerPowChallenge),
    powSolution: Optional[str] = Header(None, alias=headerPowSolution),
    escrowToken: Optional[str] = Header(None, alias=headerEscrowToken),
    redisClient: Optional[Any] = Depends(getGatewayRedisClient),
    antiSpamShield: AntiSpamSybilShield = Depends(getAntiSpamShield),
    escrowClient: EscrowClient = Depends(getEscrowClient),
) -> NegotiateTurnResponse:
    """Processes single negotiation turn under PoW and micro-escrow verification."""
    _requireX402Headers(powChallenge, powSolution, escrowToken)

    # Resolved BEFORE the escrow debit. A buyer must not be charged the per-turn micro-fee for a
    # negotiation the merchant never agreed to hold.
    terms = await resolveMerchantNegotiationTerms(payload.skuId, redisClient)
    if not terms.negotiationEnabled:
        raise HTTPException(status_code=httpStatusForbidden, detail=terms.refusalReason)
    if payload.turnNumber > terms.maxTurns:
        raise HTTPException(
            status_code=httpStatusConflict,
            detail=(
                f"This merchant allows {terms.maxTurns} negotiation turns; turn "
                f"{payload.turnNumber} is past that. Accept the last ask or buy at list price."
            ),
        )

    debitReceipt = await verifyPoWAndDebitEscrow(
        powChallenge,
        powSolution,
        escrowToken,
        payload.turnNumber,
        antiSpamShield=antiSpamShield,
        escrowClient=escrowClient,
    )
    sessionKey = f"{payload.buyerAgentDid}:{payload.skuId}"
    negotiator = getOrCreateNegotiator(
        sessionKey,
        payload.skuId,
        payload.quantity,
        debitReceipt.remainingBalancePaise,
        sellerCostFloorPaise=terms.floorPricePaise,
    )
    # The buyer proposed both sides of this turn. Only its own bid survives verbatim; the ask is
    # pulled back into the merchant's band, so a bid at or above the merchant's floor converges
    # and one below it does not -- which is what makes this a negotiation rather than a form the
    # buyer fills in on the seller's behalf.
    effectiveSellerAskPaise = clampSellerAskPaise(payload.sellerAskPaise, terms)
    step = _executeNegotiationRound(
        negotiator, payload.turnNumber, payload.buyerBidPaise, effectiveSellerAskPaise
    )
    contractAst, astHash = compileContractIfConverged(step, payload, sessionKey, terms)
    return _buildNegotiateTurnResponse(step, debitReceipt, contractAst, astHash)


def _requireX402Headers(
    powChallenge: Optional[str],
    powSolution: Optional[str],
    escrowToken: Optional[str],
) -> None:
    """Refuses a turn that arrives without the x402 headers, before any other work.

    Split out of verifyPoWAndDebitEscrow so the route can run this gate first and the policy gate
    second, and still not debit the escrow until both have passed.
    """
    if not powChallenge or not powSolution or not escrowToken:
        raise HTTPException(
            status_code=httpStatusPaymentRequired,
            detail="x402-INR authentication required: PoW solution and escrow token missing",
        )


def _executeNegotiationRound(
    negotiator: RubinsteinStahlNegotiator,
    turnNumber: int,
    buyerBidPaise: int,
    sellerAskPaise: int,
) -> NegotiationStepResult:
    """Executes state machine turn and translates domain violations to HTTP errors."""
    try:
        return negotiator.executeTurn(
            turnNumber=turnNumber,
            buyerBidPaise=buyerBidPaise,
            sellerAskPaise=sellerAskPaise,
        )
    except NonMonotonicConcessionViolation as err:
        raise HTTPException(status_code=httpStatusBadRequest, detail=str(err))
    except NegotiationExhaustedException as err:
        raise HTTPException(status_code=httpStatusConflict, detail=str(err))


def _buildNegotiateTurnResponse(
    step: NegotiationStepResult,
    debitReceipt: DebitReceipt,
    contractAst: Optional[CommercialContractAst],
    astHash: Optional[str],
) -> NegotiateTurnResponse:
    """Assembles final API response for negotiation turn."""
    return NegotiateTurnResponse(
        stepResult=step,
        debitReceipt=debitReceipt,
        contractAst=contractAst,
        contractAstHash=astHash,
    )


async def verifyPoWAndDebitEscrow(
    powChallenge: Optional[str],
    powSolution: Optional[str],
    escrowToken: Optional[str],
    turnNumber: int,
    antiSpamShield: Optional[AntiSpamSybilShield] = None,
    escrowClient: Optional[EscrowClient] = None,
) -> DebitReceipt:
    """Verifies PoW headers and debits turn fee from active escrow session."""
    _requireX402Headers(powChallenge, powSolution, escrowToken)
    activeShield = antiSpamShield if antiSpamShield is not None else defaultAntiSpamShield
    activeEscrow = escrowClient if escrowClient is not None else defaultEscrowClient
    try:
        solNonce = int(powSolution)
        activeShield.validatePoWSubmission(powChallenge, solNonce)
    except (ValueError, InvalidProofOfWorkException, PowChallengeExpiredException) as err:
        raise HTTPException(status_code=httpStatusForbidden, detail=f"Invalid PoW solution: {err}")
    except PowReplayDetectedException as err:
        raise HTTPException(status_code=httpStatusConflict, detail=f"Replay detected: {err}")

    try:
        return await activeEscrow.debitTurnFee(
            sessionToken=escrowToken,
            turnIndex=turnNumber,
        )
    except (EscrowSessionNotFoundException, InsufficientEscrowBalanceException) as err:
        raise HTTPException(status_code=httpStatusPaymentRequired, detail=str(err))


def getOrCreateNegotiator(
    sessionKey: str,
    skuId: str,
    quantity: int,
    balancePaise: int,
    sellerCostFloorPaise: Optional[int] = None,
) -> RubinsteinStahlNegotiator:
    """Retrieves or instantiates active session negotiator."""
    if sessionKey not in activeNegotiators:
        activeNegotiators[sessionKey] = RubinsteinStahlNegotiator(
            skuId=skuId,
            quantity=quantity,
            escrowBalancePaise=balancePaise,
            sellerCostFloorPaise=sellerCostFloorPaise,
        )
    return activeNegotiators[sessionKey]


def compileContractIfConverged(
    step: NegotiationStepResult,
    payload: NegotiateTurnRequest,
    sessionKey: str,
    terms: MerchantNegotiationTerms,
) -> Tuple[Optional[CommercialContractAst], Optional[str]]:
    """Compiles immutable AST if negotiation has reached convergence.

    Both commercially meaningful values come from `terms` and `step`, not from `payload`. The
    merchant is whoever the SKU listing says owns the item, and the agreed price is the ask the
    route clamped into that merchant's band -- so the hash a buyer walks away with commits the
    merchant only to a price their own policy allowed.
    """
    if not step.isConverged:
        return None, None
    now = int(time.time())
    merchantDid = terms.merchantDid or defaultMerchantFallbackDid
    contractAst, astHash = compileCommercialContractAst(
        skuId=payload.skuId,
        quantity=payload.quantity,
        agreedUnitPrice=step.sellerAskPaise,
        turns=payload.turnNumber,
        buyerDid=payload.buyerAgentDid,
        merchantDid=merchantDid,
        timestamp=now,
    )
    activeNegotiators.pop(sessionKey, None)
    return contractAst, astHash


def getPolicyRedisClient() -> Optional[Any]:
    """Retrieves or initializes Redis client for merchant dynamic policy lookup."""
    global defaultPolicyRedisClient
    if defaultPolicyRedisClient is not None:
        return defaultPolicyRedisClient
    settings = getGatewaySettings()
    redisUrl = settings.redisUrl
    if not redisUrl:
        return None
    try:
        import redis.asyncio as aioredis

        defaultPolicyRedisClient = aioredis.from_url(redisUrl, decode_responses=True)
        return defaultPolicyRedisClient
    except Exception as err:
        logger.warning("Policy Redis initialization failed: %s", err)
        return None


__all__ = [
    "activeNegotiators",
    "compileContractIfConverged",
    "defaultAntiSpamShield",
    "defaultEscrowClient",
    "defaultPolicyRedisClient",
    "getOrCreateNegotiator",
    "getPolicyRedisClient",
    "getPowChallenge",
    "negotiateRouter",
    "negotiateTurn",
    "verifyPoWAndDebitEscrow",
]
