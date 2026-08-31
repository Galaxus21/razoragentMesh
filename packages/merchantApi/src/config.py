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


def getMerchantApiSettings() -> MerchantApiSettings:
    """Instantiates and returns frozen MerchantApiSettings instance."""
    return MerchantApiSettings()


defaultMerchantSettings = getMerchantApiSettings()

__all__ = [
    "MerchantApiSettings",
    "defaultMerchantSettings",
    "getMerchantApiSettings",
]
