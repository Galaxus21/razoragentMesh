"""Negotiation and PoW challenge API routes for Layer 2 x402-INR gateway."""

import json
import logging
import time
from typing import Any, Dict, Optional, Tuple
from fastapi import APIRouter, Depends, Header, HTTPException, Request

from ..compiler.astContractCompiler import compileCommercialContractAst
from ..config import getGatewaySettings
from ..constants.gatewayConstants import (
    basisPointsDivisor, httpStatusBadRequest, httpStatusConflict,
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
from ..schemas.bidRequestSchema import (
    NegotiateTurnRequest,
    NegotiateTurnResponse,
    NegotiationStepResult,
)
from ..schemas.contractAstSchema import CommercialContractAst

logger = logging.getLogger(__name__)

merchantPolicyRedisKeyPrefix: str = "mesh:merchant:policy:"
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
    debitReceipt = await verifyPoWAndDebitEscrow(
        powChallenge,
        powSolution,
        escrowToken,
        payload.turnNumber,
        antiSpamShield=antiSpamShield,
        escrowClient=escrowClient,
    )
    sessionKey = f"{payload.buyerAgentDid}:{payload.skuId}"
    sellerCostFloor = await _resolveSellerCostFloor(
        payload.merchantDid, payload.sellerAskPaise, redisClient=redisClient
    )
    negotiator = getOrCreateNegotiator(
        sessionKey,
        payload.skuId,
        payload.quantity,
        debitReceipt.remainingBalancePaise,
        sellerCostFloorPaise=sellerCostFloor,
    )
    step = _executeNegotiationRound(
        negotiator, payload.turnNumber, payload.buyerBidPaise, payload.sellerAskPaise
    )
    contractAst, astHash = compileContractIfConverged(step, payload, sessionKey)
    return _buildNegotiateTurnResponse(step, debitReceipt, contractAst, astHash)


async def _resolveSellerCostFloor(
    merchantDid: Optional[str],
    sellerAskPaise: int,
    redisClient: Optional[Any] = None,
) -> Optional[int]:
    """Resolves seller cost floor in paise from merchant policy or margin BPS."""
    if not merchantDid:
        return None
    policyValue = await lookupMerchantFloorPolicy(merchantDid, redisClient=redisClient)
    if policyValue is None:
        return None
    if policyValue <= basisPointsDivisor and sellerAskPaise > 0:
        return (sellerAskPaise * (basisPointsDivisor - policyValue)) // basisPointsDivisor
    return policyValue


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


async def lookupMerchantFloorPolicy(
    merchantDid: Optional[str],
    redisClient: Optional[Any] = None,
) -> Optional[int]:
    """Queries Redis for merchant dynamic pricing policy and margin floor in paise/bps."""
    if not merchantDid:
        return None
    client = redisClient if redisClient is not None else await getGatewayRedisClient()
    if client is None:
        return None
    try:
        policyKey = f"{merchantPolicyRedisKeyPrefix}{merchantDid}"
        rawPolicy = await client.get(policyKey)
        if not rawPolicy:
            return None
        policyData = json.loads(rawPolicy) if isinstance(rawPolicy, (str, bytes)) else rawPolicy
        if isinstance(policyData, dict):
            if "marginFloorBps" in policyData:
                return int(policyData["marginFloorBps"])
            if "sellerCostFloorPaise" in policyData:
                return int(policyData["sellerCostFloorPaise"])
            if "costFloorPaise" in policyData:
                return int(policyData["costFloorPaise"])
        return None
    except Exception as err:
        logger.warning("Policy lookup failed for merchant %s: %s", merchantDid, err)
        return None


async def verifyPoWAndDebitEscrow(
    powChallenge: Optional[str],
    powSolution: Optional[str],
    escrowToken: Optional[str],
    turnNumber: int,
    antiSpamShield: Optional[AntiSpamSybilShield] = None,
    escrowClient: Optional[EscrowClient] = None,
) -> DebitReceipt:
    """Verifies PoW headers and debits turn fee from active escrow session."""
    if not powChallenge or not powSolution or not escrowToken:
        raise HTTPException(
            status_code=httpStatusPaymentRequired,
            detail="x402-INR authentication required: PoW solution and escrow token missing",
        )
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
) -> Tuple[Optional[CommercialContractAst], Optional[str]]:
    """Compiles immutable AST if negotiation has reached convergence."""
    if not step.isConverged:
        return None, None
    now = int(time.time())
    merchantDid = payload.merchantDid or defaultMerchantFallbackDid
    contractAst, astHash = compileCommercialContractAst(
        skuId=payload.skuId,
        quantity=payload.quantity,
        agreedUnitPrice=payload.sellerAskPaise,
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
    "lookupMerchantFloorPolicy",
    "negotiateRouter",
    "negotiateTurn",
    "verifyPoWAndDebitEscrow",
]
