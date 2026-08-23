"""FastAPI Application for Layer 2 x402-INR Negotiation Gateway."""

from contextlib import asynccontextmanager
import time
from typing import Any, AsyncGenerator, Dict
from fastapi import FastAPI
from fastapi.middleware.cors import CORSMiddleware

from .constants.negotiationConstants import (
    endpointHealth,
    protocolName,
)
from .routes.escrowRoute import (
    defaultEscrowClient,
    escrowRouter,
)
from .routes.negotiateRoute import (
    activeNegotiators,
    defaultAntiSpamShield,
    negotiateRouter,
)


class GatewayState:
    """Aggregated gateway state wrapper for backwards compatibility."""

    def __init__(self) -> None:
        self.escrowClient = defaultEscrowClient
        self.antiSpamShield = defaultAntiSpamShield
        self.activeNegotiators = activeNegotiators


gatewayState = GatewayState()


@asynccontextmanager
async def lifespan(app: FastAPI) -> AsyncGenerator[None, None]:
    """Lifespan context manager for startup and graceful shutdown."""
    yield


def createGatewayApp() -> FastAPI:
    """App factory initializing FastAPI instance with routes and middleware."""
    gatewayApp = FastAPI(
        title="RazorAgent Mesh x402 Gateway",
        version="2.0.0",
        description="HTTP 402-INR micro-metered negotiation and AST compilation service",
        lifespan=lifespan,
    )

    gatewayApp.add_middleware(
        CORSMiddleware,
        allow_origins=["*"],
        allow_credentials=True,
        allow_methods=["*"],
        allow_headers=["*"],
    )

    @gatewayApp.get(endpointHealth)
    async def healthCheck() -> Dict[str, Any]:
        """Service health and operational metrics."""
        return {
            "status": "healthy",
            "protocol": protocolName,
            "activeSessions": len(activeNegotiators),
            "timestamp": int(time.time()),
        }

    gatewayApp.include_router(escrowRouter)
    gatewayApp.include_router(negotiateRouter)

    return gatewayApp


app = createGatewayApp()

__all__ = [
    "GatewayState",
    "app",
    "createGatewayApp",
    "gatewayState",
    "lifespan",
]
