"""FastAPI dependency providers for the Mandate & Settlement Engine.

Each provider lazily builds its resource from `request.app.state` on first use and
caches it there, so a request handled before `mandateAppLifespan` has populated
`app.state` (as in a test client constructed without running the lifespan) still
gets a working instance instead of an AttributeError.
"""

from typing import Any
from fastapi import Request

from .nonce.nonceLedger import NonceLedger
from .settlement.compensationDlq import CompensationDlq
from .settlement.routeClientFactory import buildRouteClient
from .settlement.settlementOrchestrator import SettlementOrchestrator
from .settlement.splitManifestBuilder import (
    defaultLogisticsAccount, defaultProtocolFeeAccount, defaultProtocolFeePaise,
)
from .telemetryEmitter import TelemetryEventEmitter, globalTelemetryEmitter
from .verification.settlementLedger import SettlementLedger

__all__ = [
    "getCompensationDlq",
    "getNonceLedger",
    "getRedisClient",
    "getSettlementLedger",
    "getSettlementOrchestrator",
    "getTelemetryEmitter",
]


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


def getCompensationDlq(request: Request) -> CompensationDlq:
    """Retrieves or builds the durable 2PC compensation DLQ from application state.

    Backed by Redis when available, and by an in-memory queue otherwise -- either way,
    a failed rollback reversal is recorded for retry instead of being silently dropped.
    """
    dlq = getattr(request.app.state, "compensationDlq", None)
    if dlq is not None:
        return dlq
    dlq = CompensationDlq(redisClient=getRedisClient(request))
    request.app.state.compensationDlq = dlq
    return dlq


def getSettlementLedger(request: Request) -> SettlementLedger:
    """Retrieves or builds the cumulative-spend and cart-replay ledger from application state."""
    ledger = getattr(request.app.state, "settlementLedger", None)
    if ledger is not None:
        return ledger
    ledger = SettlementLedger(redisClient=getRedisClient(request))
    request.app.state.settlementLedger = ledger
    return ledger


def getSettlementOrchestrator(request: Request) -> SettlementOrchestrator:
    """Retrieves or builds SettlementOrchestrator from application state."""
    orchestrator = getattr(request.app.state, "settlementOrchestrator", None)
    if orchestrator is not None:
        return orchestrator
    routeClient = getattr(request.app.state, "routeClient", None)
    if routeClient is None:
        routeClient = buildRouteClient()
        request.app.state.routeClient = routeClient
    orchestrator = SettlementOrchestrator(
        routeClient=routeClient, nonceLedger=getNonceLedger(request),
        protocolFeeAccount=defaultProtocolFeeAccount,
        protocolFeePaise=defaultProtocolFeePaise,
        logisticsAccount=defaultLogisticsAccount,
        dlq=getCompensationDlq(request),
        settlementLedger=getSettlementLedger(request),
    )
    request.app.state.settlementOrchestrator = orchestrator
    return orchestrator
