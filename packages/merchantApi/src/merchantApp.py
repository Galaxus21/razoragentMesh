"""FastAPI Application factory for RazorAgent Mesh Merchant Ingestion API."""

from contextlib import asynccontextmanager
import logging
import os
from typing import Any, AsyncGenerator, Dict
from fastapi import FastAPI, Request
from fastapi.middleware.cors import CORSMiddleware
from fastapi.responses import JSONResponse
import redis.asyncio as aioredis

from .config import getMerchantApiSettings
from .catalog.autoVectorizer import AutoVectorizer
from .constants.merchantConstants import (
    defaultApiTitle,
    defaultApiVersion,
    defaultQdrantHost,
    defaultQdrantPort,
    merchantApiDefaultPort,
    qdrantHostEnvVar,
    qdrantPortEnvVar,
)
from .exceptions.merchantExceptions import MerchantApiException
from .routes.bulkIngestRoute import bulkIngestRouter
from .routes.oosHealingRoute import oosHealingRouter
from .routes.catalogRoute import catalogRouter
from .routes.catalogSearchRoute import catalogSearchRouter
from .routes.policyRoute import policyRouter
from .routes.registrationRoute import registrationRouter

logger = logging.getLogger(__name__)

defaultRedisUrl: str = "redis://localhost:6379/0"
environmentRedisKey: str = "REDIS_URL"
endpointHealth: str = "/health"
merchantServiceName: str = "merchant-api"


def _buildQdrantClient() -> Any:
    """Constructs the Qdrant client the catalog routes vectorise through.

    Returns None when the client library or the server is unavailable. That is deliberate:
    a merchant must still be able to publish a listing when the vector index is down --
    the listing reaches Redis and the mesh either way, only semantic discovery degrades.
    """
    host = os.getenv(qdrantHostEnvVar, defaultQdrantHost)
    port = int(os.getenv(qdrantPortEnvVar, str(defaultQdrantPort)))
    try:
        from qdrant_client import QdrantClient

        return QdrantClient(host=host, port=port)
    except Exception as err:
        logger.warning(
            "Qdrant client unavailable at %s:%s; catalog writes will not be vectorised "
            "and semantic search will return nothing: %s",
            host,
            port,
            err,
        )
        return None


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
    # The vectorizer was fully implemented but constructed by nothing outside its own tests,
    # so no published product was ever indexed and an agent could only quote a SKU id it had
    # already been told. This is where that gets connected.
    if not getattr(app.state, "vectorizer", None):
        app.state.vectorizer = AutoVectorizer(qdrantClient=_buildQdrantClient())
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
    app.include_router(catalogSearchRouter)
    app.include_router(policyRouter)
    app.include_router(bulkIngestRouter)
    # Until this line the vector healer was a library nothing constructed.
    app.include_router(oosHealingRouter)
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
