"""Razorpay HMAC-SHA256 webhook signature verifier with replay defence."""

import hashlib
import hmac
import time
from typing import Optional

from .settlementExceptions import WebhookSignatureVerificationException

# A captured webhook stays signature-valid forever, so HMAC alone does not stop replay.
# Razorpay sends the delivery time in X-Razorpay-Event-Time (Unix seconds); anything outside
# this window is rejected. Generous enough to absorb clock skew and delivery retries.
webhookFreshnessWindowSeconds: int = 300


def computeWebhookSignature(payloadBytes: bytes, webhookSecret: str) -> str:
    """Computes HMAC-SHA256 signature for raw webhook payload."""
    secretBytes = webhookSecret.encode("utf-8")
    return hmac.new(secretBytes, payloadBytes, hashlib.sha256).hexdigest()


def verifyWebhookFreshness(
    eventTimestamp: int,
    serverTime: Optional[int] = None,
    windowSeconds: int = webhookFreshnessWindowSeconds,
) -> bool:
    """Returns True when an event timestamp falls inside the accepted freshness window.

    Bounds both directions: a stale timestamp indicates a replayed delivery, and one too far
    in the future indicates a forged or badly-skewed sender.
    """
    now = serverTime if serverTime is not None else int(time.time())
    return abs(now - int(eventTimestamp)) <= windowSeconds


def verifyRazorpayWebhookSignature(
    payloadBytes: bytes,
    signatureHeader: str,
    webhookSecret: str,
    raiseOnFailure: bool = False,
    eventTimestamp: Optional[int] = None,
    serverTime: Optional[int] = None,
) -> bool:
    """Validates webhook signature using timing-attack safe comparison, and rejects deliveries
    outside the freshness window when an eventTimestamp is supplied.

    eventTimestamp is optional so existing callers keep working, but callers that have the
    X-Razorpay-Event-Time header SHOULD pass it -- a valid signature alone never expires.
    """
    if not signatureHeader or not webhookSecret:
        if raiseOnFailure:
            raise WebhookSignatureVerificationException("Missing signature or secret")
        return False

    if eventTimestamp is not None and not verifyWebhookFreshness(eventTimestamp, serverTime):
        if raiseOnFailure:
            raise WebhookSignatureVerificationException(
                f"Webhook outside {webhookFreshnessWindowSeconds}s freshness window: "
                f"possible replay of event timestamped {eventTimestamp}"
            )
        return False

    expectedSignature = computeWebhookSignature(payloadBytes, webhookSecret)
    isValid = hmac.compare_digest(expectedSignature, signatureHeader.strip())

    if not isValid and raiseOnFailure:
        raise WebhookSignatureVerificationException("Webhook signature verification failed")

    return isValid
