"""FastAPI Application factory for RazorAgent Mesh Merchant Ingestion API."""

from contextlib import asynccontextmanager
import logging
import os
from typing import AsyncGenerator, Dict
from fastapi import FastAPI, Request
from fastapi.middleware.cors import CORSMiddleware
from fastapi.responses import JSONResponse
import redis.asyncio as aioredis

from .config import getMerchantApiSettings
from .constants.merchantConstants import (
    defaultApiTitle,
    defaultApiVersion,
    merchantApiDefaultPort,
)
from .exceptions.merchantExceptions import MerchantApiException
from .routes.bulkIngestRoute import bulkIngestRouter
from .routes.catalogRoute import catalogRouter
from .routes.policyRoute import policyRouter
from .routes.registrationRoute import registrationRouter

logger = logging.getLogger(__name__)

defaultRedisUrl: str = "redis://localhost:6379/0"
environmentRedisKey: str = "REDIS_URL"
endpointHealth: str = "/health"
merchantServiceName: str = "merchant-api"


@asynccontextmanager
async def merchantApiLifespan(app: FastAPI) -> AsyncGenerator[None, None]:
    """Lifespan context manager initializing and terminating Redis client state."""
    if not getattr(app.state, "redis", None):
        settings = getMerchantApiSettings()
        try:
            app.state.redis = aioredis.from_url(settings.redisUrl)
        except Exception as err:
            logger.warning(
                "Redis connection failed, continuing with in-memory fallback: %s",
                err,
                exc_info=True,
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


async def merchantApiExceptionHandler(request: Request, exc: MerchantApiException) -> JSONResponse:
    """Translates domain exceptions into standard JSON error responses."""
    return JSONResponse(status_code=exc.statusCode, content={"detail": exc.message})


def createMerchantApp() -> FastAPI:
    """Instantiates and configures the FastAPI Merchant API application."""
    app = FastAPI(
        title=defaultApiTitle,
        version=defaultApiVersion,
        lifespan=merchantApiLifespan,
    )

    app.add_exception_handler(MerchantApiException, merchantApiExceptionHandler)

    app.add_middleware(
        CORSMiddleware,
        allow_origins=["*"],
        allow_credentials=True,
        allow_methods=["*"],
        allow_headers=["*"],
    )

    app.include_router(registrationRouter)
    app.include_router(catalogRouter)
    app.include_router(policyRouter)
    app.include_router(bulkIngestRouter)
    _registerHealthRoute(app)

    return app


def _registerHealthRoute(app: FastAPI) -> None:
    """Registers the liveness probe.

    This service was the only one in the mesh without one, so the protocol map had no way to
    tell "merchant API is down" from "merchant API has no probe". Shape matches the mandate
    engine's /health so a single client can read either.
    """

    @app.get(endpointHealth, summary="Health check")
    async def healthCheck() -> Dict[str, str]:
        return {"status": "healthy", "service": merchantServiceName, "version": defaultApiVersion}


merchantApp: FastAPI = createMerchantApp()

__all__ = [
    "createMerchantApp",
    "merchantApiExceptionHandler",
    "merchantApiLifespan",
    "merchantApp",
]
