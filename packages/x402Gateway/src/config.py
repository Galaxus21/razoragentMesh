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
    port: int = Field(
        default_factory=lambda: int(os.getenv("X402_GATEWAY_PORT", "4003")),
        description="Port for x402Gateway service",
    )
    gatewaySecret: str = Field(
        default_factory=lambda: os.getenv("GATEWAY_SECRET", "test_gateway_secret_key_32bytes!"),
        description="HMAC secret for micro-escrow receipts and alerts",
    )
    environment: str = Field(
        default_factory=lambda: os.getenv("ENVIRONMENT", "development"),
        description="Runtime environment name",
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
