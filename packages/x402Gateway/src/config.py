"""Configuration settings for Layer 2 x402Gateway."""

import os
from pydantic import BaseModel, ConfigDict, Field


class X402GatewaySettings(BaseModel):
    """Runtime configuration settings for x402 Gateway."""

    model_config = ConfigDict(frozen=True, extra="forbid")

    redisUrl: str = Field(
        default_factory=lambda: os.getenv("REDIS_URL", "redis://localhost:6379/0"),
        description="Redis connection URL for gateway policies and sessions",
    )


def getGatewaySettings() -> X402GatewaySettings:
    """Instantiates and returns frozen X402GatewaySettings instance."""
    return X402GatewaySettings()


defaultGatewaySettings = getGatewaySettings()

__all__ = [
    "X402GatewaySettings",
    "defaultGatewaySettings",
    "getGatewaySettings",
]
