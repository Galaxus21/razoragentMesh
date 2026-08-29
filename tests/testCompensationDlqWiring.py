"""Proves the durable compensation DLQ is actually wired into the running mandateApp,
not merely an optional constructor parameter that defaults to None and is never supplied.

Before this fix, SettlementOrchestrator.__init__'s `dlq` parameter was never passed by
mandateApp.py, so a failed rollback reversal was silently dropped (twoPhaseCommitSaga.py's
compensateTransfers appends None and moves on). These tests exercise the exact dependency
providers production traffic uses (getSettlementOrchestrator / mandateAppLifespan) and
confirm a failed reversal now lands in the DLQ instead of vanishing.
"""

from typing import Any

import pytest

from razoragentMesh.packages.mandateEngine.mandateApp import createMandateApp, getSettlementOrchestrator, mandateAppLifespan
from razoragentMesh.packages.mandateEngine.settlement.compensationDlq import CompensationDlq
from razoragentMesh.packages.mandateEngine.settlement.razorpayRouteClient import RouteTransferResponse


class _FakeRequest:
    def __init__(self, application: Any) -> None:
        self.app = application


class _ReversalAlwaysFailsRouteClient:
    """Minimal route client double whose reverseTransfer always raises, simulating a
    Route API timeout or 5xx during rollback compensation."""

    async def reverseTransfer(self, transferId: str, amountPaise: int) -> Any:
        raise RuntimeError("Route reversal dispatch failed: simulated 5xx")


def _completedTransfer(transferId: str, amountPaise: int) -> RouteTransferResponse:
    return RouteTransferResponse(id=transferId, account="acc_merchant_test", amount=amountPaise, createdAt=1)


@pytest.mark.asyncio
async def testGetSettlementOrchestratorWiresARealCompensationDlq() -> None:
    """The lazily-built orchestrator's saga must hold a non-None DLQ, not the None default."""
    app = createMandateApp()
    orchestrator = getSettlementOrchestrator(_FakeRequest(app))
    assert isinstance(orchestrator._dlq, CompensationDlq)
    assert orchestrator._saga._dlq is orchestrator._dlq


@pytest.mark.asyncio
async def testFailedReversalIsEnqueuedNotSilentlyDropped() -> None:
    """A reversal failure through the production dependency-injection path must produce
    a retrievable CompensationEvent, proving the DLQ is live rather than merely present."""
    app = createMandateApp()
    orchestrator = getSettlementOrchestrator(_FakeRequest(app))
    orchestrator._routeClient = _ReversalAlwaysFailsRouteClient()
    orchestrator._saga._routeClient = orchestrator._routeClient

    results = await orchestrator._compensateTransfers(
        completedTransfers=[_completedTransfer("trf_wiring_test_1", 50000)],
        failureReason="wiring test: simulated secondary transfer failure",
        paymentId="pay_wiring_test",
    )
    assert results == [None]  # the reversal itself still failed and is not silently retried inline

    enqueuedEvent = await orchestrator._dlq.popPendingEvent()
    assert enqueuedEvent is not None
    assert enqueuedEvent.transferId == "trf_wiring_test_1"
    assert enqueuedEvent.amountPaise == 50000
    assert enqueuedEvent.paymentId == "pay_wiring_test"


@pytest.mark.asyncio
async def testMandateAppLifespanWiresTheSameCompensationDlqIntoTheOrchestrator() -> None:
    """The eager lifespan-time construction path (used by the real running service, as
    opposed to the lazy per-request fallback) must wire the identical DLQ instance."""
    app = createMandateApp()
    async with mandateAppLifespan(app):
        assert isinstance(app.state.compensationDlq, CompensationDlq)
        assert app.state.settlementOrchestrator._dlq is app.state.compensationDlq
        assert app.state.settlementOrchestrator._saga._dlq is app.state.compensationDlq
