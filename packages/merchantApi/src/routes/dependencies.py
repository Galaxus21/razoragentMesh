"""Dependency injection providers for merchant API routes."""

from typing import Any
from fastapi import HTTPException, Request, status


async def getRedisClient(request: Request) -> Any:
    """Extracts asynchronous Redis client from the FastAPI application state."""
    redisClient = getattr(request.app.state, "redis", None)
    if redisClient is None:
        raise HTTPException(
            status_code=status.HTTP_503_SERVICE_UNAVAILABLE,
            detail="Redis storage service is unavailable",
        )
    return redisClient


__all__ = [
    "getRedisClient",
]
