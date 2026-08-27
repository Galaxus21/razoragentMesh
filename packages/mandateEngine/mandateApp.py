"""FastAPI Application factory for RazorAgent Mesh Mandate & Settlement Engine."""

from contextlib import asynccontextmanager
import time
from typing import Any, AsyncGenerator, Dict, Optional
import uuid
from fastapi import Depends, FastAPI, HTTPException, Request, status
from fastapi.middleware.cors import CORSMiddleware
from fastapi.responses import StreamingResponse
from pydantic import BaseModel, ConfigDict, Field
import redis.asyncio as aioredis

from .config import getMandateEngineSettings
from .constants.settlementConstants import (
    defaultEngineTitle, defaultEngineVersion, millisecondsPerSecond, transferIdPrefix,
)
from .mandates.cartMandateSchema import CartMandate
from .mandates.executionMandateSchema import ExecutionMandate
from .mandates.intentMandateSchema import IntentMandate
from .nonce.nonceLedger import NonceLedger
from .settlement.razorpayRouteClient import RazorpayRouteClient
from .settlement.settlementExceptions import (
    ArithmeticDriftException, ArithmeticEnclaveMismatchException,
    BudgetExceededViolation, CategoryNotAuthorizedException,
    FutureTimestampException, InvalidPincodeException, MandateEngineException,
    MandateExpiredException, MandateHashChainMismatchException,
    NonceReplayException, PaymentBlockedException,
    SettlementCompensationTriggeredException, SignatureVerificationFailedException,
    SingleTransactionLimitExceededException, TimestampExpiredException,
)
from .settlement.settlementOrchestrator import SettlementOrchestrator, SettlementResult
from .settlement.splitManifestBuilder import (
    defaultLogisticsAccount, defaultProtocolFeeAccount, defaultProtocolFeePaise,
)
from .telemetryEmitter import (
    TelemetryEventEmitter, TelemetryEventModel, globalTelemetryEmitter,
)


class ExecuteSettlementRequestSchema(BaseModel):
    """Payload for initiating 2PC mandate execution and Route split."""

    model_config = ConfigDict(frozen=True, extra="forbid")

    intentMandate: IntentMandate = Field(description="Principal spending intent mandate (M_I)")
    cartMandate: CartMandate = Field(description="Merchant cart quote and reservation (M_C)")
    executionMandate: ExecutionMandate = Field(description="Buyer agent execution commitment (M_E)")
    merchantAccount: str = Field(min_length=1, description="Linked vendor account ID (acc_...)")
    paymentId: str = Field(min_length=1, description="Primary Razorpay/UPI payment identifier")
    serverTime: Optional[int] = Field(default=None, description="Optional server timestamp")
    metadata: Dict[str, Any] = Field(default_factory=dict, description="Custom metadata")


ExecuteSettlementRequest = ExecuteSettlementRequestSchema

mandateEnginePort: int = 8000
defaultRedisUrl: str = "redis://localhost:6379/0"
environmentRedisKey: str = "REDIS_URL"
endpointSettlementExecute: str = "/api/v1/settlement/execute"
endpointTelemetryStream: str = "/api/v1/telemetry/stream"
endpointTelemetryEvents: str = "/api/v1/telemetry/events"
endpointHealth: str = "/health"
eventTypePaymentCaptured: str = "PAYMENT_CAPTURED"
eventTypeRouteRollback: str = "ROUTE_ROLLBACK_TRIGGERED"
eventTypeBudgetBlocked: str = "BUDGET_BLOCKED"


def createMandateApp() -> FastAPI:
    """Creates and configures the FastAPI Mandate & Settlement service."""
    app = FastAPI(title=defaultEngineTitle, version=defaultEngineVersion, lifespan=mandateAppLifespan)
    app.add_middleware(
        CORSMiddleware, allow_origins=["*"], allow_credentials=True,
        allow_methods=["*"], allow_headers=["*"],
    )
    _registerHealthRoutes(app)
    _registerSettlementRoutes(app)
    _registerTelemetryRoutes(app)
    return app


def _registerHealthRoutes(app: FastAPI) -> None:
    """Registers health check endpoint for liveness and readiness probes."""

    @app.get(endpointHealth, summary="Health check")
    async def healthCheck() -> Dict[str, str]:
        return {"status": "healthy", "service": "mandate-engine", "version": defaultEngineVersion}


def _registerSettlementRoutes(app: FastAPI) -> None:
    """Registers 2PC settlement saga execution endpoint."""

    @app.post(
        endpointSettlementExecute, summary="Execute 2PC settlement saga",
        response_model=SettlementResult, status_code=status.HTTP_200_OK,
    )
    async def executeSettlement(
        payload: ExecuteSettlementRequestSchema,
        orchestrator: SettlementOrchestrator = Depends(getSettlementOrchestrator),
        emitter: TelemetryEventEmitter = Depends(getTelemetryEmitter),
    ) -> SettlementResult:
        """Executes full 2PC cryptographic mandate verification and Route split payout."""
        try:
            result = await orchestrator.executeSettlementSaga(
                intentMandate=payload.intentMandate, cartMandate=payload.cartMandate,
                executionMandate=payload.executionMandate, merchantAccount=payload.merchantAccount,
                paymentId=payload.paymentId, serverTime=payload.serverTime,
            )
            await emitPaymentCapturedTelemetry(emitter, payload, result)
            return result
        except Exception as err:
            await _handleSettlementException(err, emitter, payload)
            raise


async def _handleSettlementException(
    err: Exception, emitter: TelemetryEventEmitter, payload: ExecuteSettlementRequestSchema,
) -> None:
    """Translates settlement domain exceptions to HTTP responses and emits telemetry."""
    if isinstance(err, SettlementCompensationTriggeredException):
        await emitRollbackTelemetry(emitter, payload, str(err))
        raise HTTPException(status.HTTP_502_BAD_GATEWAY, f"Settlement compensation rollback triggered: {err}")
    if isinstance(err, NonceReplayException):
        raise HTTPException(status.HTTP_409_CONFLICT, str(err))
    if isinstance(err, (BudgetExceededViolation, PaymentBlockedException, CategoryNotAuthorizedException, SingleTransactionLimitExceededException)):
        await emitBudgetBlockedTelemetry(emitter, payload, str(err))
        raise HTTPException(status.HTTP_400_BAD_REQUEST, str(err))
    if isinstance(err, (
        TimestampExpiredException, FutureTimestampException, MandateExpiredException,
        SignatureVerificationFailedException, MandateHashChainMismatchException,
        ArithmeticEnclaveMismatchException, ArithmeticDriftException, InvalidPincodeException, MandateEngineException,
    )):
        raise HTTPException(status.HTTP_400_BAD_REQUEST, str(err))
    raise HTTPException(status.HTTP_500_INTERNAL_SERVER_ERROR, f"Internal settlement error: {err}")


def _registerTelemetryRoutes(app: FastAPI) -> None:
    """Registers real-time SSE telemetry stream and event publication endpoints."""

    @app.get(endpointTelemetryStream, summary="Subscribe to live SSE telemetry event stream")
    async def telemetryStream(
        request: Request, emitter: TelemetryEventEmitter = Depends(getTelemetryEmitter),
    ) -> StreamingResponse:
        return StreamingResponse(
            emitter.subscribeStream(), media_type="text/event-stream",
            headers={"Cache-Control": "no-cache", "Connection": "keep-alive", "X-Accel-Buffering": "no"},
        )

    @app.post(endpointTelemetryEvents, summary="Publish a new telemetry event into the stream")
    async def publishTelemetryEvent(
        event: TelemetryEventModel, emitter: TelemetryEventEmitter = Depends(getTelemetryEmitter),
    ) -> Dict[str, Any]:
        delivered = await emitter.publishEvent(event)
        return {"status": "broadcasted", "subscribers": delivered}


def getRedisClient(request: Request) -> Any:
    """Retrieves Redis client instance from application state."""
    return getattr(request.app.state, "redis", None)


def getNonceLedger(request: Request) -> NonceLedger:
    """Retrieves or instantiates NonceLedger from application state."""
    ledger = getattr(request.app.state, "nonceLedger", None)
    return ledger if ledger is not None else NonceLedger(getRedisClient(request))


def getTelemetryEmitter(request: Request) -> TelemetryEventEmitter:
    """Retrieves active telemetry emitter instance from application state."""
    return getattr(request.app.state, "telemetryEmitter", globalTelemetryEmitter)


def getSettlementOrchestrator(request: Request) -> SettlementOrchestrator:
    """Retrieves or builds SettlementOrchestrator from application state."""
    orchestrator = getattr(request.app.state, "settlementOrchestrator", None)
    if orchestrator is not None:
        return orchestrator
    routeClient = getattr(request.app.state, "routeClient", None)
    if routeClient is None:
        routeClient = RazorpayRouteClient(isMockMode=True)
        request.app.state.routeClient = routeClient
    nonceLedger = getNonceLedger(request)
    orchestrator = SettlementOrchestrator(
        routeClient=routeClient, nonceLedger=nonceLedger,
        protocolFeeAccount=defaultProtocolFeeAccount,
        protocolFeePaise=defaultProtocolFeePaise,
        logisticsAccount=defaultLogisticsAccount,
    )
    request.app.state.settlementOrchestrator = orchestrator
    return orchestrator


async def emitPaymentCapturedTelemetry(
    emitter: TelemetryEventEmitter, payload: ExecuteSettlementRequestSchema, result: SettlementResult,
) -> None:
    """Publishes PAYMENT_CAPTURED telemetry event upon successful 2PC settlement."""
    transfersList = [
        {"transferId": t.id, "recipientAccountId": t.account, "amountPaise": t.amount, "feePaise": 0}
        for t in result.transfers
    ]
    event = TelemetryEventModel(
        eventId=f"evt_{uuid.uuid4().hex[:12]}", eventType=eventTypePaymentCaptured,
        timestampMs=int(time.time() * millisecondsPerSecond), sessionId=payload.paymentId,
        payload={
            "paymentId": result.paymentId, "orderId": payload.executionMandate.executionId,
            "amountPaise": result.amountPaise, "currency": "INR", "status": "captured",
            "transfers": transfersList, "gstrInvoiceHash": result.invoice.cryptographicAuditHash,
            "cgstPaise": result.invoice.totalCgstPaise, "sgstPaise": result.invoice.totalSgstPaise,
            "igstPaise": result.invoice.totalIgstPaise,
        },
    )
    await emitter.publishEvent(event)


async def emitRollbackTelemetry(
    emitter: TelemetryEventEmitter, payload: ExecuteSettlementRequestSchema, reason: str,
) -> None:
    """Publishes ROUTE_ROLLBACK_TRIGGERED telemetry event upon 2PC transfer compensation."""
    event = TelemetryEventModel(
        eventId=f"evt_{uuid.uuid4().hex[:12]}", eventType=eventTypeRouteRollback,
        timestampMs=int(time.time() * millisecondsPerSecond), sessionId=payload.paymentId,
        payload={
            "transferId": f"{transferIdPrefix}{payload.paymentId[:10]}", "failureReason": reason,
            "compensationAction": "reverse_transfer", "rollbackStatus": "COMPLETED",
        },
    )
    await emitter.publishEvent(event)


async def emitBudgetBlockedTelemetry(
    emitter: TelemetryEventEmitter, payload: ExecuteSettlementRequestSchema, reason: str,
) -> None:
    """Publishes BUDGET_BLOCKED telemetry event when settlement exceeds budget constraints."""
    delta = max(0, payload.executionMandate.settlementAmountPaise - payload.intentMandate.maxBudgetPaise)
    event = TelemetryEventModel(
        eventId=f"evt_{uuid.uuid4().hex[:12]}", eventType=eventTypeBudgetBlocked,
        timestampMs=int(time.time() * millisecondsPerSecond), sessionId=payload.paymentId,
        payload={
            "intentBudgetPaise": payload.intentMandate.maxBudgetPaise,
            "attemptedAmountPaise": payload.executionMandate.settlementAmountPaise,
            "deltaPaise": delta, "blockedReason": reason, "razorpayCallsCount": 0,
        },
    )
    await emitter.publishEvent(event)


@asynccontextmanager
async def mandateAppLifespan(app: FastAPI) -> AsyncGenerator[None, None]:
    """Lifespan context manager for initializing and terminating Redis and settlement state."""
    if not getattr(app.state, "redis", None):
        settings = getMandateEngineSettings()
        try:
            app.state.redis = aioredis.from_url(settings.redisUrl, decode_responses=True)
        except Exception:
            app.state.redis = None

    if not getattr(app.state, "nonceLedger", None):
        app.state.nonceLedger = NonceLedger(app.state.redis)
    if not getattr(app.state, "telemetryEmitter", None):
        app.state.telemetryEmitter = globalTelemetryEmitter
    if not getattr(app.state, "routeClient", None):
        app.state.routeClient = RazorpayRouteClient(isMockMode=True)
    if not getattr(app.state, "settlementOrchestrator", None):
        app.state.settlementOrchestrator = SettlementOrchestrator(
            routeClient=app.state.routeClient, nonceLedger=app.state.nonceLedger,
            protocolFeeAccount=defaultProtocolFeeAccount,
            protocolFeePaise=defaultProtocolFeePaise,
            logisticsAccount=defaultLogisticsAccount,
        )

    yield

    if getattr(app.state, "redis", None) is not None:
        client = app.state.redis
        if hasattr(client, "aclose"):
            await client.aclose()
        elif hasattr(client, "close"):
            res = client.close()
            if hasattr(res, "__await__"):
                await res

    if getattr(app.state, "routeClient", None) is not None and hasattr(app.state.routeClient, "close"):
        await app.state.routeClient.close()


mandateApp: FastAPI = createMandateApp()

__all__ = [
    "ExecuteSettlementRequest",
    "ExecuteSettlementRequestSchema",
    "createMandateApp",
    "mandateApp",
    "mandateAppLifespan",
    "mandateEnginePort",
]
