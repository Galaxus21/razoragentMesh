"""FastAPI Application factory for RazorAgent Mesh Mandate & Settlement Engine."""

from contextlib import asynccontextmanager
from typing import Any, AsyncGenerator, Dict
from fastapi import FastAPI, Request
from fastapi.middleware.cors import CORSMiddleware
from fastapi.responses import StreamingResponse
from pydantic import BaseModel, Field

from .telemetryEmitter import (
    TelemetryEventModel,
    globalTelemetryEmitter,
)

mandateEnginePort: int = 8000


class ExecuteSettlementRequest(BaseModel):
    """Payload for initiating 2PC mandate execution and Route split."""

    orderId: str
    amountPaise: int = Field(gt=0)
    customerPhone: str = "9876543210"
    merchantRouteAccountId: str
    metadata: Dict[str, Any] = Field(default_factory=dict)


@asynccontextmanager
async def mandateAppLifespan(app: FastAPI) -> AsyncGenerator[None, None]:
    """Lifespan context for Mandate Engine service."""
    yield


def createMandateApp() -> FastAPI:
    """Creates and configures the FastAPI Mandate & Settlement service."""
    app = FastAPI(
        title="RazorAgent Mesh — Mandate & Settlement Engine",
        version="2.0.0",
        lifespan=mandateAppLifespan,
    )

    app.add_middleware(
        CORSMiddleware,
        allow_origins=["*"],
        allow_credentials=True,
        allow_methods=["*"],
        allow_headers=["*"],
    )

    @app.get("/health", summary="Health check")
    async def healthCheck() -> Dict[str, str]:
        return {
            "status": "healthy",
            "service": "mandate-engine",
            "version": "2.0.0",
        }

    @app.get(
        "/api/v1/telemetry/stream",
        summary="Subscribe to live SSE telemetry event stream",
    )
    async def telemetryStream(request: Request) -> StreamingResponse:
        """Streams real-time agent thought traces, cryptographic proofs, and settlement events."""
        return StreamingResponse(
            globalTelemetryEmitter.subscribeStream(),
            media_type="text/event-stream",
            headers={
                "Cache-Control": "no-cache",
                "Connection": "keep-alive",
                "X-Accel-Buffering": "no",
            },
        )

    @app.post(
        "/api/v1/telemetry/events",
        summary="Publish a new telemetry event into the stream",
    )
    async def publishTelemetryEvent(event: TelemetryEventModel) -> Dict[str, Any]:
        """Broadcasts a telemetry event to connected dashboard subscribers."""
        delivered = await globalTelemetryEmitter.publishEvent(event)
        return {"status": "broadcasted", "subscribers": delivered}

    return app


mandateApp: FastAPI = createMandateApp()

__all__ = [
    "createMandateApp",
    "mandateApp",
    "mandateEnginePort",
]
