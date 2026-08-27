"""Configuration settings for Layer 4 mandateEngine."""

import os
from pydantic import BaseModel, ConfigDict, Field


class MandateEngineSettings(BaseModel):
    """Runtime configuration settings for Mandate & Settlement Engine."""

    model_config = ConfigDict(frozen=True, extra="forbid")

    redisUrl: str = Field(
        default_factory=lambda: os.getenv("REDIS_URL", "redis://localhost:6379/0"),
        description="Redis connection URL for nonce ledger and state",
    )
    port: int = Field(
        default_factory=lambda: int(os.getenv("MANDATE_ENGINE_PORT", "4004")),
        description="Port for mandateEngine service",
    )
    environment: str = Field(
        default_factory=lambda: os.getenv("ENVIRONMENT", "development"),
        description="Runtime environment name",
    )
    mockRazorpayMode: bool = Field(
        default_factory=lambda: os.getenv("MOCK_RAZORPAY_MODE", "true").lower() in ("true", "1", "yes"),
        description="Whether to run Razorpay Route Client in mock mode",
    )


def getMandateEngineSettings() -> MandateEngineSettings:
    """Instantiates and returns frozen MandateEngineSettings instance."""
    return MandateEngineSettings()


defaultMandateSettings = getMandateEngineSettings()

__all__ = [
    "MandateEngineSettings",
    "defaultMandateSettings",
    "getMandateEngineSettings",
]
