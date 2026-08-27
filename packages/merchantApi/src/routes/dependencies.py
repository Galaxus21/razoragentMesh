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


__all__ = [
    "getRedisClient",
]
