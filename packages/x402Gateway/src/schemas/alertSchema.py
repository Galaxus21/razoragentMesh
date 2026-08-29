"""Pydantic schemas for price-drop alert subscriptions and webhook payloads."""

import os
from typing import Optional
from pydantic import BaseModel, ConfigDict, Field, field_validator

from ..constants.alertConstants import allowLocalhostCallbackEnvVar
from .callbackUrlValidator import validateCallbackUrl


def _validateCallbackUrlField(candidateUrl: str) -> str:
    """Applies the shared SSRF guard. Reads the opt-in flag directly from the
    environment, matching the lightweight os.getenv pattern X402GatewaySettings
    already uses, rather than importing the settings singleton into a schema module."""
    allowLocalhostCallback = os.getenv(allowLocalhostCallbackEnvVar, "").lower() in ("1", "true")
    return validateCallbackUrl(candidateUrl, allowLocalhostCallback=allowLocalhostCallback)


class PriceDropAlert(BaseModel):
    """Internal immutable model representing a price-drop alert subscription."""

    model_config = ConfigDict(frozen=True, extra="forbid")

    alertId: str = Field(min_length=1)
    skuId: str = Field(min_length=1)
    targetPricePaise: int = Field(gt=0)
    callbackUrl: str = Field(min_length=1)
    buyerAgentId: str = Field(min_length=1)
    expiresAtUnix: int = Field(gt=0)
    createdAtUnix: int = Field(gt=0)
    status: str = Field(default="active")

    _validateCallbackUrl = field_validator("callbackUrl")(_validateCallbackUrlField)


class PriceDropDispatchResult(BaseModel):
    """Result record for an individual webhook dispatch attempt."""

    model_config = ConfigDict(frozen=True, extra="forbid")

    alertId: str
    callbackUrl: str
    status: str
    statusCode: Optional[int] = None
    signatureHeader: str
    error: Optional[str] = None


class PriceDropAlertRegisterRequest(BaseModel):
    """Request payload for registering a new price-drop alert."""

    model_config = ConfigDict(frozen=True, extra="forbid")

    skuId: str = Field(min_length=1)
    targetPricePaise: int = Field(gt=0)
    callbackUrl: str = Field(min_length=1)
    buyerAgentId: str = Field(min_length=1)
    expiresAtUnix: int = Field(gt=0)

    _validateCallbackUrl = field_validator("callbackUrl")(_validateCallbackUrlField)


class PriceDropAlertResponse(BaseModel):
    """Response returned upon successful alert registration."""

    model_config = ConfigDict(frozen=True, extra="forbid")

    alertId: str
    skuId: str
    targetPricePaise: int
    callbackUrl: str
    buyerAgentId: str
    expiresAtUnix: int
    createdAtUnix: int
    status: str = "active"


class PriceDropAlertCancelResponse(BaseModel):
    """Response returned upon alert cancellation."""

    model_config = ConfigDict(frozen=True, extra="forbid")

    alertId: str
    status: str = "cancelled"
    cancelled: bool = True


class PriceDropWebhookPayload(BaseModel):
    """Payload schema dispatched in outbound price-drop webhook POST."""

    model_config = ConfigDict(frozen=True, extra="forbid")

    event: str = "mesh.price_drop.triggered"
    alertId: str
    skuId: str
    buyerAgentId: str
    targetPricePaise: int
    activePricePaise: int
    savingsPaise: int
    triggeredAtUnix: int
    callbackUrl: str


__all__ = [
    "PriceDropAlert",
    "PriceDropAlertCancelResponse",
    "PriceDropAlertRegisterRequest",
    "PriceDropAlertResponse",
    "PriceDropDispatchResult",
    "PriceDropWebhookPayload",
]
