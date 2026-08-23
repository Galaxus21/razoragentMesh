"""Razorpay HMAC-SHA256 webhook signature verifier."""

import hashlib
import hmac

from .settlementExceptions import WebhookSignatureVerificationException


def computeWebhookSignature(payloadBytes: bytes, webhookSecret: str) -> str:
    """Computes HMAC-SHA256 signature for raw webhook payload."""
    secretBytes = webhookSecret.encode("utf-8")
    return hmac.new(secretBytes, payloadBytes, hashlib.sha256).hexdigest()


def verifyRazorpayWebhookSignature(
    payloadBytes: bytes,
    signatureHeader: str,
    webhookSecret: str,
    raiseOnFailure: bool = False,
) -> bool:
    """Validates webhook signature using timing-attack safe comparison."""
    if not signatureHeader or not webhookSecret:
        if raiseOnFailure:
            raise WebhookSignatureVerificationException("Missing signature or secret")
        return False

    expectedSignature = computeWebhookSignature(payloadBytes, webhookSecret)
    isValid = hmac.compare_digest(expectedSignature, signatureHeader.strip())

    if not isValid and raiseOnFailure:
        raise WebhookSignatureVerificationException("Webhook signature verification failed")

    return isValid
