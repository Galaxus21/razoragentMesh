"""Unit tests for Razorpay Webhook HMAC-SHA256 signature verification."""

import pytest
from razoragentMesh.packages.mandateEngine.settlement.settlementExceptions import (
    WebhookSignatureVerificationException,
)
from razoragentMesh.packages.mandateEngine.settlement.webhookVerifier import (
    computeWebhookSignature,
    verifyRazorpayWebhookSignature,
)


def testWebhookSignatureVerification() -> None:
    """Verifies timing-attack safe HMAC-SHA256 webhook validation."""
    payloadBytes = b'{"event":"payment.captured","payload":{"payment":{"id":"pay_123"}}}'
    secret = "rzp_webhook_secret_key"

    signature = computeWebhookSignature(payloadBytes, secret)
    assert len(signature) == 64

    # Valid signature
    assert verifyRazorpayWebhookSignature(payloadBytes, signature, secret) is True

    # Tampered signature
    badSignature = "0" * 64
    assert verifyRazorpayWebhookSignature(payloadBytes, badSignature, secret) is False

    with pytest.raises(WebhookSignatureVerificationException):
        verifyRazorpayWebhookSignature(payloadBytes, badSignature, secret, raiseOnFailure=True)
