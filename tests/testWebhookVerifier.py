"""Unit tests for Razorpay Webhook HMAC-SHA256 signature verification."""

import pytest
from razoragentMesh.packages.mandateEngine.settlement.settlementExceptions import (
    WebhookSignatureVerificationException,
)
from razoragentMesh.packages.mandateEngine.settlement.webhookVerifier import (
    computeWebhookSignature,
    verifyRazorpayWebhookSignature,
    verifyWebhookFreshness,
    webhookFreshnessWindowSeconds,
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


# --- replay defence -----------------------------------------------------------------------

def testFreshWebhookInsideWindowIsAccepted() -> None:
    now = 1_800_000_000
    assert verifyWebhookFreshness(now - 10, serverTime=now) is True
    assert verifyWebhookFreshness(now, serverTime=now) is True


def testStaleWebhookOutsideWindowIsRejected() -> None:
    """A captured webhook stays signature-valid forever, so freshness is the only replay bound."""
    now = 1_800_000_000
    stale = now - (webhookFreshnessWindowSeconds + 1)
    assert verifyWebhookFreshness(stale, serverTime=now) is False


def testFutureDatedWebhookIsRejected() -> None:
    """Bounds the future side too: a far-future timestamp indicates forgery or bad skew."""
    now = 1_800_000_000
    future = now + (webhookFreshnessWindowSeconds + 1)
    assert verifyWebhookFreshness(future, serverTime=now) is False


def testReplayedWebhookRejectedDespiteValidSignature() -> None:
    """The whole point: a correct HMAC must not be sufficient once the delivery is stale."""
    payload = b'{"event":"payment.captured","id":"evt_replay_001"}'
    secret = "whsec_test_key"
    signature = computeWebhookSignature(payload, secret)
    now = 1_800_000_000
    stale = now - (webhookFreshnessWindowSeconds + 60)

    # Signature alone still verifies, which is exactly why the timestamp bound is required.
    assert verifyRazorpayWebhookSignature(payload, signature, secret) is True

    assert verifyRazorpayWebhookSignature(
        payload, signature, secret, eventTimestamp=stale, serverTime=now,
    ) is False

    with pytest.raises(WebhookSignatureVerificationException):
        verifyRazorpayWebhookSignature(
            payload, signature, secret, raiseOnFailure=True,
            eventTimestamp=stale, serverTime=now,
        )
