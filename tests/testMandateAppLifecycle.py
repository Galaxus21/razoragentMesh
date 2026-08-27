"""Tests for FastAPI Mandate Engine application lifespan and module exports."""

import httpx
from httpx import ASGITransport
import pytest

from razoragentMesh.packages.mandateEngine.mandateApp import (
    createMandateApp,
    mandateAppLifespan,
)
from razoragentMesh.packages.mandateEngine.telemetryEmitter import (
    TelemetryEventModel,
)


@pytest.mark.asyncio
async def testMandateAppLifespanAndTelemetryLifecycle() -> None:
    """Verifies mandateAppLifespan startup/shutdown lifecycle and telemetry event publishing."""
    app = createMandateApp()
    async with mandateAppLifespan(app):
        assert getattr(app.state, "nonceLedger", None) is not None
        assert getattr(app.state, "routeClient", None) is not None
        assert getattr(app.state, "settlementOrchestrator", None) is not None

        transport = ASGITransport(app=app)
        async with httpx.AsyncClient(transport=transport, base_url="http://test") as client:
            telemetryEvt = TelemetryEventModel(
                eventId="evt_manual_001",
                eventType="MCP_TOOL_CALL",
                timestampMs=1700000000000,
                sessionId="sess_test_001",
                payload={"toolName": "get_live_sku_quote"},
            )
            pubResp = await client.post("/api/v1/telemetry/events", json=telemetryEvt.model_dump())
            assert pubResp.status_code == 200
            assert pubResp.json()["status"] == "broadcasted"


def testMandateEngineRootExports() -> None:
    """Verifies all required symbols are exported in razoragentMesh.packages.mandateEngine."""
    import razoragentMesh.packages.mandateEngine as mandateEngineModule

    requiredSymbols = [
        "createMandateApp",
        "mandateApp",
        "mandateAppLifespan",
        "mandateEnginePort",
        "ExecuteSettlementRequest",
        "ExecuteSettlementRequestSchema",
        "SettlementOrchestrator",
        "SettlementResult",
        "TwoPhaseCommitSaga",
        "SplitTransferManifest",
        "buildSplitManifest",
        "RazorpayRouteClient",
        "computeCartSettlementTotal",
    ]
    for sym in requiredSymbols:
        assert hasattr(mandateEngineModule, sym), f"Missing symbol on module: {sym}"
        assert sym in mandateEngineModule.__all__, f"Missing symbol from __all__: {sym}"
