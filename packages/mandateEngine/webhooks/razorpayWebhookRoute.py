"""Inbound Razorpay webhook receiver for the Mandate & Settlement Engine.

Why this exists: `settlement/webhookVerifier.py` implemented HMAC-SHA256 verification with a
replay window, was covered by `tests/testWebhookVerifier.py`, and was mounted on no route -- so
Razorpay had nowhere to deliver, and payment state could only ever come from the synchronous
settle call this mesh initiates. A module that works, has green tests and is reachable from
nothing is the repository's dominant failure shape (AUDIT_ARCHIVE items 19, 23, 24); this is the
route that makes the verifier load-bearing.

What it deliberately does NOT do: update an order. `SettlementResult` is never persisted -- the
only settlement keys in Redis are existence flags for replay defence -- so there is no record for
a `payment.failed` or `refund.created` delivery to amend. Reconciliation is blocked on order
persistence and is recorded as such in README.md. What this route owes Razorpay today is a
verified, idempotent, correctly-status-coded acknowledgement, and that is what it gives.
"""

import json
import logging
import time
from typing import Any, Dict, Optional

from fastapi import Depends, FastAPI, Request, Response, status

from ..config import getMandateEngineSettings
from ..dependencies import getRedisClient
from ..settlement.webhookVerifier import (
    verifyRazorpayWebhookSignature,
    webhookFreshnessWindowSeconds,
)

logger = logging.getLogger(__name__)

endpointRazorpayWebhook: str = "/api/v1/webhooks/razorpay"

headerSignature: str = "X-Razorpay-Signature"
headerEventId: str = "X-Razorpay-Event-Id"
headerEventTime: str = "X-Razorpay-Event-Time"

deliveryRedisKeyPrefix: str = "razoragent:webhook:delivery:"
# A delivery is remembered well past the freshness window, because Razorpay retries a failed
# delivery for hours: the replay window stops a captured payload being replayed at us, and this
# stops an honest retry being processed twice.
deliveryTtlSeconds: int = 86400
maxWebhookBodyBytes: int = 262144

statusAccepted: str = "accepted"
statusDuplicate: str = "duplicate"

secretMissingDetail: str = (
    "RAZORPAY_WEBHOOK_SECRET is not configured, so no delivery can be verified. The endpoint "
    "refuses rather than accepting an unverifiable payload."
)
signatureInvalidDetail: str = "Signature verification failed."
staleDeliveryDetail: str = (
    f"Delivery timestamp is outside the {webhookFreshnessWindowSeconds}s freshness window."
)
bodyTooLargeDetail: str = "Webhook body exceeds the accepted size."


def registerWebhookRoutes(app: FastAPI) -> None:
    """Binds the inbound Razorpay webhook receiver onto the FastAPI app."""

    @app.post(
        endpointRazorpayWebhook,
        summary="Receive a signed Razorpay webhook delivery",
        status_code=status.HTTP_200_OK,
    )
    async def receiveRazorpayWebhook(
        request: Request,
        redisClient: Any = Depends(getRedisClient),
    ) -> Response:
        """Verifies, de-duplicates and acknowledges one Razorpay delivery.

        Every refusal is a distinct status so a misconfiguration is not read as an attack: 503
        means this mesh holds no secret, 401 means the signature did not match, 400 means the
        delivery is outside the replay window.
        """
        secret = getMandateEngineSettings().razorpayWebhookSecret
        if not secret:
            return _jsonResponse(status.HTTP_503_SERVICE_UNAVAILABLE, {"detail": secretMissingDetail})

        payloadBytes = await request.body()
        if len(payloadBytes) > maxWebhookBodyBytes:
            return _jsonResponse(status.HTTP_413_REQUEST_ENTITY_TOO_LARGE, {"detail": bodyTooLargeDetail})

        eventTimestamp = _readEventTimestamp(request)
        if not verifyRazorpayWebhookSignature(
            payloadBytes=payloadBytes,
            signatureHeader=request.headers.get(headerSignature, ""),
            webhookSecret=secret,
            eventTimestamp=eventTimestamp,
        ):
            return _jsonResponse(*_refusalFor(eventTimestamp))

        eventId = request.headers.get(headerEventId, "")
        if await _isDuplicateDelivery(redisClient, eventId):
            # 200, not 409: a non-2xx tells Razorpay to retry, and retrying a delivery we have
            # already accepted is precisely what this branch exists to stop.
            return _jsonResponse(status.HTTP_200_OK, {"status": statusDuplicate, "eventId": eventId})

        return _jsonResponse(status.HTTP_200_OK, _acknowledge(payloadBytes, eventId))


def _refusalFor(eventTimestamp: Optional[int]) -> tuple:
    """Separates a stale delivery from a forged one, which are different failures."""
    if eventTimestamp is not None and not _isFresh(eventTimestamp):
        return status.HTTP_400_BAD_REQUEST, {"detail": staleDeliveryDetail}
    return status.HTTP_401_UNAUTHORIZED, {"detail": signatureInvalidDetail}


def _isFresh(eventTimestamp: int) -> bool:
    return abs(int(time.time()) - eventTimestamp) <= webhookFreshnessWindowSeconds


def _readEventTimestamp(request: Request) -> Optional[int]:
    """The delivery time Razorpay stamps, or None when the header is absent or unparsable.

    None disables the freshness check rather than failing the delivery: the signature is still
    required, and refusing a correctly signed payload because a header was missing would drop
    real events on a header this mesh does not control.
    """
    raw = request.headers.get(headerEventTime, "")
    if not raw:
        return None
    try:
        return int(raw)
    except ValueError:
        return None


async def _isDuplicateDelivery(redisClient: Any, eventId: str) -> bool:
    """True when this delivery id has been seen before.

    An absent id or an absent Redis both answer False: without one there is nothing to
    de-duplicate on, and refusing the delivery would be worse than processing it twice.
    """
    if not eventId or redisClient is None:
        return False
    try:
        wasSet = await redisClient.set(
            f"{deliveryRedisKeyPrefix}{eventId}", "1", ex=deliveryTtlSeconds, nx=True
        )
    except Exception as redisError:
        logger.warning("Webhook de-duplication unavailable: %s", redisError)
        return False
    return not wasSet


def _acknowledge(payloadBytes: bytes, eventId: str) -> Dict[str, Any]:
    """Logs a verified delivery and reports back what was understood of it."""
    event, paymentId = _readEventFacts(payloadBytes)
    logger.info(
        "Verified Razorpay webhook: event=%s eventId=%s paymentId=%s", event, eventId, paymentId
    )
    return {
        "status": statusAccepted,
        "eventId": eventId,
        "event": event,
        "paymentId": paymentId,
        # Stated on every acknowledgement rather than assumed: a caller must not read a 200 here
        # as "the mesh has updated the order". See the module docstring.
        "reconciled": False,
    }


def _readEventFacts(payloadBytes: bytes) -> tuple:
    """The event name and payment id, or (None, None) when the body is not a Razorpay envelope.

    A verified but unrecognised body is still accepted: the signature proves it came from
    Razorpay, and refusing a shape this mesh has not met would make new event types look like
    forgeries.
    """
    try:
        body = json.loads(payloadBytes.decode("utf-8"))
    except (json.JSONDecodeError, UnicodeDecodeError):
        return None, None
    if not isinstance(body, dict):
        return None, None
    entity = body.get("payload", {}).get("payment", {}).get("entity", {})
    paymentId = entity.get("id") if isinstance(entity, dict) else None
    return body.get("event"), paymentId


def _jsonResponse(statusCode: int, body: Dict[str, Any]) -> Response:
    """Builds the response by hand so a refusal is not re-serialised through a response model."""
    return Response(
        content=json.dumps(body),
        status_code=statusCode,
        media_type="application/json",
    )
