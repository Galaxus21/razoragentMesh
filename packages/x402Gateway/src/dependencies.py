"""Dependency injection providers for Layer 2 x402Gateway routes."""

import logging
import os
from typing import Any, Optional
from fastapi import Request
import redis.asyncio as aioredis

from .alerts.priceDropAlertManager import PriceDropAlertManager
from .config import getGatewaySettings
from .escrow.microEscrowClient import MicroEscrowClient
from .middleware.proofOfWorkMiddleware import IngressAntiSpamShield

logger = logging.getLogger(__name__)

# Type aliases for clean DI interfaces
EscrowClient = MicroEscrowClient
AntiSpamSybilShield = IngressAntiSpamShield

defaultEscrowClient = MicroEscrowClient()
defaultAlertManager = PriceDropAlertManager()
defaultAntiSpamShield = IngressAntiSpamShield()
defaultPolicyRedisClient: Optional[Any] = None


async def getGatewayRedisClient(request: Request = None) -> Optional[Any]:
    """Provides asynchronous Redis client from application state or environment."""
    if request is not None and hasattr(request, "app") and getattr(request.app.state, "redis", None) is not None:
        return request.app.state.redis
    global defaultPolicyRedisClient
    if defaultPolicyRedisClient is not None:
        return defaultPolicyRedisClient
    settings = getGatewaySettings()
    redisUrl = settings.redisUrl
    if not redisUrl:
        return None
    try:
        defaultPolicyRedisClient = aioredis.from_url(redisUrl, decode_responses=True)
        return defaultPolicyRedisClient
    except Exception as err:
        logger.warning("Policy Redis initialization failed: %s", err)
        return None


async def getEscrowClient(request: Request = None) -> EscrowClient:
    """Provides EscrowClient instance from application state or default singleton."""
    if request is not None and hasattr(request, "app") and getattr(request.app.state, "escrowClient", None) is not None:
        return request.app.state.escrowClient
    return defaultEscrowClient


async def getAlertManager(request: Request = None) -> PriceDropAlertManager:
    """Provides PriceDropAlertManager instance from application state or default singleton."""
    if request is not None and hasattr(request, "app") and getattr(request.app.state, "alertManager", None) is not None:
        return request.app.state.alertManager
    return defaultAlertManager


async def getAntiSpamShield(request: Request = None) -> AntiSpamSybilShield:
    """Provides AntiSpamSybilShield instance from application state or default singleton."""
    if request is not None and hasattr(request, "app") and getattr(request.app.state, "antiSpamShield", None) is not None:
        return request.app.state.antiSpamShield
    return defaultAntiSpamShield


__all__ = [
    "AntiSpamSybilShield",
    "EscrowClient",
    "defaultAlertManager",
    "defaultAntiSpamShield",
    "defaultEscrowClient",
    "defaultPolicyRedisClient",
    "getAlertManager",
    "getAntiSpamShield",
    "getEscrowClient",
    "getGatewayRedisClient",
]
