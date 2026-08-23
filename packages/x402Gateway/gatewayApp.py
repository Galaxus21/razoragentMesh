"""FastAPI Application for Layer 2 x402-INR Negotiation Gateway."""

from contextlib import asynccontextmanager
import time
from typing import Any, AsyncGenerator, Dict, Optional
from fastapi import FastAPI, Header, HTTPException, Request, Response
from fastapi.middleware.cors import CORSMiddleware
from pydantic import BaseModel, ConfigDict, Field

from razoragentMesh.packages.mandateEngine.arithmeticEnclave import validateIntegerPaise
from razoragentMesh.packages.x402Gateway.astContractCompiler import (
    CommercialContractAst,
    compileCommercialContractAst,
)
from razoragentMesh.packages.x402Gateway.bidStateMachine import (
    NegotiationStepResult,
    RubinsteinStahlNegotiator,
)
from razoragentMesh.packages.x402Gateway.gatewayConstants import (
    defaultGstRatePercent,
    headerEscrowToken,
    headerPowChallenge,
    headerPowSolution,
    initialEscrowPoolPaise,
    maxNegotiationTurns,
    microFeePerTurnPaise,
    protocolName,
)
from razoragentMesh.packages.x402Gateway.gatewayExceptions import (
    EscrowSessionNotFoundException,
    InsufficientEscrowBalanceException,
    InvalidProofOfWorkException,
    NegotiationExhaustedException,
    NonMonotonicConcessionViolation,
    PowChallengeExpiredException,
    PowReplayDetectedException,
)
from razoragentMesh.packages.x402Gateway.microEscrowClient import (
    DebitReceipt,
    EscrowRefundReceipt,
    EscrowSession,
    MicroEscrowClient,
)
from razoragentMesh.packages.x402Gateway.proofOfWorkMiddleware import (
    Http402ChallengeResponse,
    IngressAntiSpamShield,
)


class EscrowCreateRequest(BaseModel):
    model_config = ConfigDict(frozen=True, extra="forbid")
    buyerAgentDid: str = Field(min_length=1)
    initialHoldPaise: int = Field(default=initialEscrowPoolPaise, gt=0)


class NegotiateTurnRequest(BaseModel):
    model_config = ConfigDict(frozen=True, extra="forbid")
    skuId: str = Field(min_length=1)
    quantity: int = Field(gt=0)
    turnNumber: int = Field(ge=1, le=maxNegotiationTurns)
    buyerBidPaise: int = Field(gt=0)
    sellerAskPaise: int = Field(gt=0)
    buyerAgentDid: str = Field(min_length=1)
    merchantDid: str = Field(min_length=1)


class NegotiateTurnResponse(BaseModel):
    model_config = ConfigDict(frozen=True, extra="forbid")
    stepResult: NegotiationStepResult
    debitReceipt: Optional[DebitReceipt] = None
    contractAst: Optional[CommercialContractAst] = None
    contractAstHash: Optional[str] = None


class GatewayState:
    def __init__(self) -> None:
        self.escrowClient = MicroEscrowClient()
        self.antiSpamShield = IngressAntiSpamShield()
        self.activeNegotiators: Dict[str, RubinsteinStahlNegotiator] = {}


gatewayState = GatewayState()


@asynccontextmanager
async def lifespan(app: FastAPI) -> AsyncGenerator[None, None]:
    """Lifespan context manager for startup and graceful shutdown."""
    yield


app = FastAPI(
    title="RazorAgent Mesh x402 Gateway",
    version="2.0.0",
    description="HTTP 402-INR micro-metered negotiation and AST compilation service",
    lifespan=lifespan,
)

app.add_middleware(
    CORSMiddleware,
    allow_origins=["*"],
    allow_credentials=True,
    allow_methods=["*"],
    allow_headers=["*"],
)


@app.get("/api/v1/mesh/health")
async def healthCheck() -> Dict[str, Any]:
    """Service health and operational metrics."""
    return {
        "status": "healthy",
        "protocol": protocolName,
        "activeSessions": len(gatewayState.activeNegotiators),
        "timestamp": int(time.time()),
    }


@app.get("/api/v1/mesh/challenge")
async def getPowChallenge(request: Request) -> Http402ChallengeResponse:
    """Generates fresh SHA-256 PoW challenge."""
    clientIp = request.client.host if request.client else "127.0.0.1"
    return gatewayState.antiSpamShield.generateChallenge(clientIp)


@app.post("/api/v1/mesh/escrow")
async def createEscrowSession(payload: EscrowCreateRequest) -> EscrowSession:
    """Allocates ₹50 micro-escrow session on UPI Circle rails."""
    return await gatewayState.escrowClient.createEscrowSession(
        buyerAgentDid=payload.buyerAgentDid,
        initialHoldPaise=payload.initialHoldPaise,
    )


@app.post("/api/v1/mesh/escrow/release")
async def releaseEscrow(
    sessionToken: str = Header(..., alias=headerEscrowToken),
) -> EscrowRefundReceipt:
    """Releases unspent escrow balance back to buyer pool."""
    try:
        return await gatewayState.escrowClient.releaseUnspentEscrow(sessionToken)
    except EscrowSessionNotFoundException as err:
        raise HTTPException(status_code=404, detail=str(err))


async def _verifyPoWAndDebitEscrow(
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
        gatewayState.antiSpamShield.validatePoWSubmission(powChallenge, solNonce)
    except (ValueError, InvalidProofOfWorkException, PowChallengeExpiredException) as err:
        raise HTTPException(status_code=403, detail=f"Invalid PoW solution: {err}")
    except PowReplayDetectedException as err:
        raise HTTPException(status_code=409, detail=f"Replay detected: {err}")

    try:
        return await gatewayState.escrowClient.debitTurnFee(
            sessionToken=escrowToken,
            turnIndex=turnNumber,
        )
    except (EscrowSessionNotFoundException, InsufficientEscrowBalanceException) as err:
        raise HTTPException(status_code=402, detail=str(err))


def _getOrCreateNegotiator(
    sessionKey: str,
    skuId: str,
    quantity: int,
    balancePaise: int,
) -> RubinsteinStahlNegotiator:
    """Retrieves or instantiates active session negotiator."""
    if sessionKey not in gatewayState.activeNegotiators:
        gatewayState.activeNegotiators[sessionKey] = RubinsteinStahlNegotiator(
            skuId=skuId,
            quantity=quantity,
            escrowBalancePaise=balancePaise,
        )
    return gatewayState.activeNegotiators[sessionKey]


def _compileContractIfConverged(
    step: NegotiationStepResult,
    payload: NegotiateTurnRequest,
    sessionKey: str,
) -> tuple[Optional[CommercialContractAst], Optional[str]]:
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
    gatewayState.activeNegotiators.pop(sessionKey, None)
    return contractAst, astHash


@app.post("/api/v1/mesh/negotiate")
async def negotiateTurn(
    payload: NegotiateTurnRequest,
    powChallenge: Optional[str] = Header(None, alias=headerPowChallenge),
    powSolution: Optional[str] = Header(None, alias=headerPowSolution),
    escrowToken: Optional[str] = Header(None, alias=headerEscrowToken),
) -> NegotiateTurnResponse:
    """Processes single negotiation turn under PoW and micro-escrow verification."""
    debitReceipt = await _verifyPoWAndDebitEscrow(
        powChallenge, powSolution, escrowToken, payload.turnNumber
    )
    sessionKey = f"{payload.buyerAgentDid}:{payload.skuId}"
    negotiator = _getOrCreateNegotiator(
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

    contractAst, astHash = _compileContractIfConverged(step, payload, sessionKey)

    return NegotiateTurnResponse(
        stepResult=step,
        debitReceipt=debitReceipt,
        contractAst=contractAst,
        contractAstHash=astHash,
    )
