"""Dependency injection providers for merchant API routes."""

from typing import Any
from fastapi import Request

from ..exceptions.merchantExceptions import MerchantStorageUnavailableException


async def getRedisClient(request: Request) -> Any:
    """Extracts asynchronous Redis client from the FastAPI application state."""
    redisClient = getattr(request.app.state, "redis", None)
    if redisClient is None:
        raise MerchantStorageUnavailableException("Redis storage service is unavailable")
    return redisClient


async def getVectorizer(request: Request) -> Any:
    """Extracts the catalog vectorizer from application state.

    Unlike Redis this may be absent, and that is not an error: catalog writes must still
    succeed when the vector index is unavailable. Callers are expected to treat None as
    "indexing is off" rather than failing the request.
    """
    return getattr(request.app.state, "vectorizer", None)


__all__ = [
    "getRedisClient",
    "getVectorizer",
]
