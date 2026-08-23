"""FastAPI Application factory for RazorAgent Mesh Merchant Ingestion API."""

from contextlib import asynccontextmanager
import os
from typing import AsyncGenerator
from fastapi import FastAPI
from fastapi.middleware.cors import CORSMiddleware
import redis.asyncio as aioredis

from .constants.merchantConstants import merchantApiDefaultPort
from .routes.bulkIngestRoute import bulkIngestRouter
from .routes.catalogRoute import catalogRouter
from .routes.policyRoute import policyRouter
from .routes.registrationRoute import registrationRouter

defaultRedisUrl: str = "redis://localhost:6379/0"
environmentRedisKey: str = "REDIS_URL"


@asynccontextmanager
async def merchantApiLifespan(app: FastAPI) -> AsyncGenerator[None, None]:
    """Lifespan context manager initializing and terminating Redis client state."""
    if not getattr(app.state, "redis", None):
        redisUrl = os.environ.get(environmentRedisKey, defaultRedisUrl)
        try:
            app.state.redis = aioredis.from_url(redisUrl)
        except Exception:
            pass
    yield
    if getattr(app.state, "redis", None) is not None:
        client = app.state.redis
        if hasattr(client, "aclose"):
            await client.aclose()
        elif hasattr(client, "close"):
            res = client.close()
            if hasattr(res, "__await__"):
                await res


def createMerchantApp() -> FastAPI:
    """Instantiates and configures the FastAPI Merchant API application."""
    app = FastAPI(
        title="RazorAgent Mesh — Merchant Ingestion API",
        version="2.0.0",
        lifespan=merchantApiLifespan,
    )

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

    return app


merchantApp: FastAPI = createMerchantApp()

__all__ = [
    "createMerchantApp",
    "merchantApiLifespan",
    "merchantApp",
]
