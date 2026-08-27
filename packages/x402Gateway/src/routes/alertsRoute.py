"""Price-drop alert webhook subscription API routes for Layer 2 x402Gateway."""

import time
from fastapi import APIRouter, Depends, HTTPException, status

from ..alerts.priceDropAlertManager import (
    PriceDropAlertCancelResponse,
    PriceDropAlertManager,
    PriceDropAlertRegisterRequest,
    PriceDropAlertResponse,
)
from ..dependencies import (
    defaultAlertManager,
    getAlertManager,
)

alertsRouter = APIRouter(prefix="/api/v1/alerts", tags=["alerts"])


@alertsRouter.post(
    "/price-drop",
    response_model=PriceDropAlertResponse,
    status_code=status.HTTP_201_CREATED,
)
async def registerPriceDropAlert(
    payload: PriceDropAlertRegisterRequest,
    alertManager: PriceDropAlertManager = Depends(getAlertManager),
) -> PriceDropAlertResponse:
    """Registers an autonomous price-drop alert subscription with temporal TTL."""
    now = int(time.time())
    if payload.expiresAtUnix <= now:
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail="Expiry timestamp must be in the future",
        )
    if payload.targetPricePaise <= 0:
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail="Target price must be positive integer paise",
        )

    alert = await alertManager.registerPriceDropAlert(
        skuId=payload.skuId,
        targetPricePaise=payload.targetPricePaise,
        callbackUrl=payload.callbackUrl,
        buyerAgentId=payload.buyerAgentId,
        expiresAtUnix=payload.expiresAtUnix,
    )

    return PriceDropAlertResponse(
        alertId=alert.alertId,
        skuId=alert.skuId,
        targetPricePaise=alert.targetPricePaise,
        callbackUrl=alert.callbackUrl,
        buyerAgentId=alert.buyerAgentId,
        expiresAtUnix=alert.expiresAtUnix,
        createdAtUnix=alert.createdAtUnix,
        status=alert.status,
    )


@alertsRouter.delete(
    "/price-drop/{alertId}",
    response_model=PriceDropAlertCancelResponse,
    status_code=status.HTTP_200_OK,
)
async def cancelPriceDropAlert(
    alertId: str,
    alertManager: PriceDropAlertManager = Depends(getAlertManager),
) -> PriceDropAlertCancelResponse:
    """Cancels an active price-drop alert subscription."""
    isCancelled = await alertManager.cancelPriceDropAlert(alertId)
    if not isCancelled:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail=f"Alert '{alertId}' not found",
        )

    return PriceDropAlertCancelResponse(
        alertId=alertId,
        status="cancelled",
        cancelled=True,
    )


__all__ = [
    "alertsRouter",
    "cancelPriceDropAlert",
    "defaultAlertManager",
    "registerPriceDropAlert",
]
