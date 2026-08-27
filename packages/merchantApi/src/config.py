"""Configuration settings for Layer 1 merchantApi."""

import os
from pydantic import BaseModel, ConfigDict, Field


class MerchantApiSettings(BaseModel):
    """Runtime configuration settings for Merchant Ingestion API."""

    model_config = ConfigDict(frozen=True, extra="forbid")

    redisUrl: str = Field(
        default_factory=lambda: os.getenv("REDIS_URL", "redis://localhost:6379/0"),
        description="Redis connection URL for merchant catalog and profiles",
    )
    port: int = Field(
        default_factory=lambda: int(os.getenv("MERCHANT_API_PORT", "4002")),
        description="Port for merchantApi service",
    )
    qdrantHost: str = Field(
        default_factory=lambda: os.getenv("QDRANT_HOST", "localhost"),
        description="Qdrant vector database hostname",
    )
    qdrantPort: int = Field(
        default_factory=lambda: int(os.getenv("QDRANT_PORT", "6333")),
        description="Qdrant vector database port",
    )
    environment: str = Field(
        default_factory=lambda: os.getenv("ENVIRONMENT", "development"),
        description="Runtime environment name",
    )


def getMerchantApiSettings() -> MerchantApiSettings:
    """Instantiates and returns frozen MerchantApiSettings instance."""
    return MerchantApiSettings()


defaultMerchantSettings = getMerchantApiSettings()

__all__ = [
    "MerchantApiSettings",
    "defaultMerchantSettings",
    "getMerchantApiSettings",
]
