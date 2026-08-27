"""Price-drop alert manager with Redis persistence and HMAC-SHA256 webhook dispatch."""

import hashlib
import hmac
import json
import time
import uuid
from typing import Any, Dict, List, Optional, Tuple
import httpx

from ..constants.arithmeticUtils import validateIntegerPaise
from ..constants.alertConstants import (
    defaultWebhookTimeoutSeconds,
    eventPriceDropTriggered,
    headerMeshDeliveryId,
    headerMeshEvent,
    headerMeshSignature,
    headerRazorpaySignature,
    httpStatusOkMax,
    httpStatusOkMin,
    idPrefixAlert,
    idPrefixDelivery,
    minTtlSeconds,
    redisAlertLookupPrefix,
    redisAlertPriceDropPrefix,
    statusAlertActive,
    statusAlertCancelled,
    statusDispatchFailed,
    statusDispatchSuccess,
)
from ..constants.negotiationConstants import defaultGatewaySecret
from ..schemas.alertSchema import (
    PriceDropAlert,
    PriceDropAlertCancelResponse,
    PriceDropAlertRegisterRequest,
    PriceDropAlertResponse,
    PriceDropDispatchResult,
    PriceDropWebhookPayload,
)


class PriceDropAlertManager:
    """Manages price-drop alert subscriptions, Redis persistence, and webhook dispatch."""

    def __init__(
        self,
        redisClient: Optional[Any] = None,
        webhookSecret: str = defaultGatewaySecret,
        httpClient: Optional[Any] = None,
    ) -> None:
        self._redisClient = redisClient
        self._webhookSecret = webhookSecret
        self._httpClient = httpClient
        self._inMemoryAlerts: Dict[str, List[Dict[str, Any]]] = {}
        self._inMemoryLookup: Dict[str, str] = {}

    async def registerPriceDropAlert(
        self,
        skuId: str,
        targetPricePaise: int,
        callbackUrl: str,
        buyerAgentId: str,
        expiresAtUnix: int,
    ) -> PriceDropAlert:
        """Registers a price-drop alert subscription with dynamic TTL."""
        validateIntegerPaise(targetPricePaise, "targetPricePaise")
        if targetPricePaise <= 0:
            raise ValueError("Target price must be positive integer paise")
        now = int(time.time())
        if expiresAtUnix <= now:
            raise ValueError("Alert expiry timestamp must be in the future")

        alertId = f"{idPrefixAlert}{uuid.uuid4().hex[:16]}"
        alert = PriceDropAlert(
            alertId=alertId,
            skuId=skuId,
            targetPricePaise=targetPricePaise,
            callbackUrl=callbackUrl,
            buyerAgentId=buyerAgentId,
            expiresAtUnix=expiresAtUnix,
            createdAtUnix=now,
            status=statusAlertActive,
        )
        await self._storeAlert(alert, now)
        return alert

    async def _storeAlert(self, alert: PriceDropAlert, now: int) -> None:
        """Persists alert record to Redis or in-memory dictionary."""
        alertDict = alert.model_dump()
        if self._redisClient is not None:
            bucketKey = f"{redisAlertPriceDropPrefix}{alert.skuId}"
            lookupKey = f"{redisAlertLookupPrefix}{alert.alertId}"
            raw = await self._redisClient.get(bucketKey)
            existing: List[Dict[str, Any]] = json.loads(raw) if raw else []
            active = [a for a in existing if a.get("expiresAtUnix", 0) > now]
            active.append(alertDict)
            maxTtl = max(a["expiresAtUnix"] - now for a in active)
            await self._redisClient.set(bucketKey, json.dumps(active), ex=max(minTtlSeconds, maxTtl))
            ttlLookup = alert.expiresAtUnix - now
            await self._redisClient.set(lookupKey, alert.skuId, ex=max(minTtlSeconds, ttlLookup))
            return

        existingMem = self._inMemoryAlerts.get(alert.skuId, [])
        activeMem = [a for a in existingMem if a.get("expiresAtUnix", 0) > now]
        activeMem.append(alertDict)
        self._inMemoryAlerts[alert.skuId] = activeMem
        self._inMemoryLookup[alert.alertId] = alert.skuId

    async def cancelPriceDropAlert(self, alertId: str) -> bool:
        """Cancels an active alert by alertId and purges lookup indexes."""
        now = int(time.time())
        if self._redisClient is not None:
            lookupKey = f"{redisAlertLookupPrefix}{alertId}"
            skuId = await self._redisClient.get(lookupKey)
            if not skuId:
                return False
            resolvedSkuId = skuId.decode("utf-8") if isinstance(skuId, bytes) else str(skuId)
            bucketKey = f"{redisAlertPriceDropPrefix}{resolvedSkuId}"
            raw = await self._redisClient.get(bucketKey)
            if raw:
                alerts: List[Dict[str, Any]] = json.loads(raw) if isinstance(raw, (str, bytes)) else raw
                remaining = [a for a in alerts if a.get("alertId") != alertId and a.get("expiresAtUnix", 0) > now]
                if remaining:
                    maxTtl = max(a["expiresAtUnix"] - now for a in remaining)
                    await self._redisClient.set(bucketKey, json.dumps(remaining), ex=max(minTtlSeconds, maxTtl))
                else:
                    await self._deleteRedisKey(bucketKey)
            await self._deleteRedisKey(lookupKey)
            return True

        skuIdMem = self._inMemoryLookup.pop(alertId, None)
        if not skuIdMem:
            return False
        existingMem = self._inMemoryAlerts.get(skuIdMem, [])
        remainingMem = [a for a in existingMem if a.get("alertId") != alertId and a.get("expiresAtUnix", 0) > now]
        if remainingMem:
            self._inMemoryAlerts[skuIdMem] = remainingMem
        else:
            self._inMemoryAlerts.pop(skuIdMem, None)
        return True

    async def getAlertsForSku(self, skuId: str) -> List[PriceDropAlert]:
        """Retrieves and filters active non-expired alerts for a given SKU."""
        now = int(time.time())
        if self._redisClient is not None:
            bucketKey = f"{redisAlertPriceDropPrefix}{skuId}"
            raw = await self._redisClient.get(bucketKey)
            if not raw:
                return []
            data: List[Dict[str, Any]] = json.loads(raw) if isinstance(raw, (str, bytes)) else raw
            return [PriceDropAlert(**a) for a in data if a.get("expiresAtUnix", 0) > now]

        dataMem = self._inMemoryAlerts.get(skuId, [])
        return [PriceDropAlert(**a) for a in dataMem if a.get("expiresAtUnix", 0) > now]

    async def dispatchPriceDropAlerts(
        self,
        skuId: str,
        activePricePaise: int,
    ) -> List[PriceDropDispatchResult]:
        """Evaluates price drop, filters matching alerts, and dispatches HMAC-signed webhooks."""
        validateIntegerPaise(activePricePaise, "activePricePaise")
        alerts = await self.getAlertsForSku(skuId)
        matching = [a for a in alerts if a.targetPricePaise >= activePricePaise]
        if not matching:
            return []

        results: List[PriceDropDispatchResult] = []
        now = int(time.time())
        for alert in matching:
            result = await self._sendSingleWebhook(alert, activePricePaise, now)
            results.append(result)
        return results

    async def _sendSingleWebhook(
        self,
        alert: PriceDropAlert,
        activePricePaise: int,
        now: int,
    ) -> PriceDropDispatchResult:
        """Constructs signed webhook payload and sends HTTP POST to callback URL."""
        payload = _buildWebhookPayload(alert, activePricePaise, now)
        payloadBytes, headers, sig = _signWebhookPayload(payload, self._webhookSecret)
        isOk, statusCode, errorMsg = await _executeWebhookPost(
            alert.callbackUrl, payloadBytes, headers, self._httpClient
        )
        return PriceDropDispatchResult(
            alertId=alert.alertId,
            callbackUrl=alert.callbackUrl,
            status=statusDispatchSuccess if isOk else statusDispatchFailed,
            statusCode=statusCode,
            signatureHeader=sig,
            error=errorMsg,
        )

    async def _deleteRedisKey(self, key: str) -> None:
        """Safely removes key across real Redis client or in-memory mock."""
        if self._redisClient is None:
            return
        if hasattr(self._redisClient, "delete"):
            await self._redisClient.delete(key)
        elif hasattr(self._redisClient, "store"):
            self._redisClient.store.pop(key, None)
            if hasattr(self._redisClient, "expirations"):
                self._redisClient.expirations.pop(key, None)
        elif hasattr(self._redisClient, "set"):
            await self._redisClient.set(key, "")


def _buildWebhookPayload(
    alert: PriceDropAlert,
    activePricePaise: int,
    now: int,
) -> PriceDropWebhookPayload:
    """Constructs structured webhook payload for price drop event."""
    savingsPaise = max(0, alert.targetPricePaise - activePricePaise)
    return PriceDropWebhookPayload(
        event=eventPriceDropTriggered,
        alertId=alert.alertId,
        skuId=alert.skuId,
        buyerAgentId=alert.buyerAgentId,
        targetPricePaise=alert.targetPricePaise,
        activePricePaise=activePricePaise,
        savingsPaise=savingsPaise,
        triggeredAtUnix=now,
        callbackUrl=alert.callbackUrl,
    )


def _signWebhookPayload(
    payload: PriceDropWebhookPayload,
    secret: str,
) -> Tuple[bytes, Dict[str, str], str]:
    """Serializes payload to canonical JSON and generates HMAC-SHA256 headers."""
    payloadBytes = json.dumps(payload.model_dump(), separators=(",", ":"), sort_keys=True).encode("utf-8")
    sig = hmac.new(secret.encode("utf-8"), payloadBytes, hashlib.sha256).hexdigest()
    deliveryId = f"{idPrefixDelivery}{uuid.uuid4().hex[:16]}"
    headers = {
        "Content-Type": "application/json",
        headerMeshSignature: sig,
        headerRazorpaySignature: sig,
        headerMeshEvent: eventPriceDropTriggered,
        headerMeshDeliveryId: deliveryId,
    }
    return payloadBytes, headers, sig


async def _executeWebhookPost(
    callbackUrl: str,
    payloadBytes: bytes,
    headers: Dict[str, str],
    httpClient: Optional[Any] = None,
) -> Tuple[bool, Optional[int], Optional[str]]:
    """Dispatches signed webhook payload via HTTP POST to callback endpoint."""
    try:
        if httpClient is not None:
            resp = await httpClient.post(
                callbackUrl,
                content=payloadBytes,
                headers=headers,
                timeout=defaultWebhookTimeoutSeconds,
            )
            isOk = httpStatusOkMin <= resp.status_code < httpStatusOkMax
            return isOk, resp.status_code, None if isOk else f"HTTP {resp.status_code}"
        async with httpx.AsyncClient(timeout=defaultWebhookTimeoutSeconds) as client:
            resp = await client.post(
                callbackUrl,
                content=payloadBytes,
                headers=headers,
            )
            isOk = httpStatusOkMin <= resp.status_code < httpStatusOkMax
            return isOk, resp.status_code, None if isOk else f"HTTP {resp.status_code}"
    except Exception as err:
        return False, None, str(err)


__all__ = [
    "PriceDropAlert",
    "PriceDropAlertCancelResponse",
    "PriceDropAlertManager",
    "PriceDropAlertRegisterRequest",
    "PriceDropAlertResponse",
    "PriceDropDispatchResult",
    "PriceDropWebhookPayload",
    "eventPriceDropTriggered",
    "headerMeshDeliveryId",
    "headerMeshEvent",
    "headerMeshSignature",
    "headerRazorpaySignature",
    "redisAlertLookupPrefix",
    "redisAlertPriceDropPrefix",
    "statusAlertActive",
    "statusAlertCancelled",
    "statusDispatchFailed",
    "statusDispatchSuccess",
]
