"""FastAPI Application for Layer 2 x402-INR Negotiation Gateway."""

from contextlib import asynccontextmanager
import logging
import time
from typing import Any, AsyncGenerator, Dict
from fastapi import FastAPI
from fastapi.middleware.cors import CORSMiddleware
import redis.asyncio as aioredis

from .constants.gatewayConstants import (
    defaultGatewayDescription,
    defaultGatewayTitle,
    defaultGatewayVersion,
)
from .constants.negotiationConstants import (
    endpointHealth,
    protocolName,
)
from .routes.alertsRoute import (
    alertsRouter,
    defaultAlertManager,
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
from .alerts.catalogPriceWatcher import CatalogPriceWatcher
from .alerts.priceDropAlertManager import PriceDropAlertManager
from .config import getGatewaySettings

logger = logging.getLogger(__name__)


@asynccontextmanager
async def lifespan(app: FastAPI) -> AsyncGenerator[None, None]:
    """Opens the Redis-backed alert manager and starts the price watcher.

    This used to be a bare `yield`, which left two things broken at once. `defaultAlertManager`
    is constructed with no Redis client, so every registered alert lived in a process-local dict:
    invisible to any other process and gone on restart. And nothing subscribed to the catalog
    channel, so `dispatchPriceDropAlerts` had no caller and no alert could ever fire. Fixing
    either alone changes nothing observable -- a wired dispatcher would still find an empty
    bucket, and a Redis-backed bucket would still never be read.
    """
    watcher = None
    redisClient = None
    try:
        redisClient = aioredis.from_url(getGatewaySettings().redisUrl, decode_responses=True)
        app.state.redis = redisClient
        alertManager = PriceDropAlertManager(redisClient=redisClient)
        app.state.alertManager = alertManager
        watcher = CatalogPriceWatcher(alertManager, redisClient)
        watcher.start()
    except Exception as err:
        # Negotiation, escrow and proof-of-work do not need Redis, so a gateway that cannot reach
        # it must still serve them. Alerts degrade to the in-memory manager rather than taking
        # the whole service down at boot.
        logger.warning("Price-drop alert watcher not started: %s", err)

    try:
        yield
    finally:
        if watcher is not None:
            await watcher.stop()
        if redisClient is not None:
            try:
                await redisClient.aclose()
            except Exception:
                pass


def createGatewayApp() -> FastAPI:
    """App factory initializing FastAPI instance with routes and middleware."""
    gatewayApp = FastAPI(
        title=defaultGatewayTitle,
        version=defaultGatewayVersion,
        description=defaultGatewayDescription,
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
    gatewayApp.include_router(alertsRouter)

    return gatewayApp


app = createGatewayApp()

__all__ = [
    "app",
    "createGatewayApp",
    "lifespan",
]
