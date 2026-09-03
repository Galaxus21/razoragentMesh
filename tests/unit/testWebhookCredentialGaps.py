"""Coverage-gap tests for the Razorpay webhook signature verifier.

Each test here pins a specific line whose mutation a prior mutation-score run showed the suite
accepting in silence. The production code is CORRECT and fails closed in every missing-credential
case; these are missing assertions, not a live acceptance vulnerability.
"""

import pytest

from razoragentMesh.packages.mandateEngine.settlement.webhookVerifier import (
    computeWebhookSignature,
    verifyRazorpayWebhookSignature,
    verifyWebhookFreshness,
    webhookFreshnessWindowSeconds,
)
from razoragentMesh.packages.mandateEngine.settlement.settlementExceptions import (
    WebhookSignatureVerificationException,
)

# A shared secret/payload so a "credential present" case can produce a genuinely valid signature.
_secret = "whsec_razorpay_test_secret"
_payload = b'{"event":"payment.captured","id":"pay_abc123"}'
_validSignature = computeWebhookSignature(_payload, _secret)
# A signature that IS a correct HMAC for the empty secret. If the early credential check is ever
# weakened so an empty-secret delivery falls through to HMAC comparison, this header would match
# and the forged event would be accepted -- so it is the only header that distinguishes the intended
# fail-closed behaviour from the `or` -> `and` mutation on L50.
_emptySecretSignature = computeWebhookSignature(_payload, "")


def testMissingSignatureWithSecretPresentIsRejected():
    """GAP 1 (L50 `or` -> `and`): a delivery carrying a secret but NO signature header must be
    rejected up front. Under the `and` mutation this case would fall through to HMAC comparison
    against an empty header. Real-world: an unsigned forged webhook would trigger a payout."""
    assert verifyRazorpayWebhookSignature(_payload, "", _secret) is False


def testPresentSignatureWithMissingSecretIsRejected():
    """GAP 1 (L50 `or` -> `and`): a delivery whose signature is present but the configured secret
    is empty must be rejected up front, NOT fall through to HMAC comparison. The header here is a
    valid HMAC for the empty secret, so under the `and` mutation the fall-through comparison would
    succeed and return True -- this is the case that actually kills the mutant. Real-world: a
    misconfigured (empty-secret) deployment must never accept an attacker's empty-secret signature."""
    assert verifyRazorpayWebhookSignature(_payload, _emptySecretSignature, "") is False


def testBothCredentialsMissingIsRejected():
    """GAP 1 (L50): with neither signature nor secret the function must reject. This is the ONE
    case the `and` mutation still rejects, pinned so the trio is exhaustive."""
    assert verifyRazorpayWebhookSignature(_payload, "", "") is False


def testMissingSignatureRaisesWhenRaiseOnFailureTrue():
    """GAP 2 (L52 `raise` -> `pass`): a caller opting into raiseOnFailure must get the exception on
    a missing-credential delivery, not a silent fall-through returning a truthy path. Under `pass`
    the raise vanishes. Real-world: a strict caller relying on the exception would treat an unsigned
    webhook as processable."""
    with pytest.raises(WebhookSignatureVerificationException):
        verifyRazorpayWebhookSignature(_payload, "", _secret, raiseOnFailure=True)


def testMissingSignatureReturnsFalseWhenRaiseOnFailureFalse():
    """GAP 2 (L52): the default raiseOnFailure=False path must return False (not raise) for the
    same missing-signature input, pinning that the raise sits behind the flag."""
    assert verifyRazorpayWebhookSignature(_payload, "", _secret, raiseOnFailure=False) is False


def testFreshnessAcceptsExactlyAtWindowEdge():
    """GAP 3 (L33 `<=` -> `<`): an event exactly windowSeconds old must still be ACCEPTED. Under
    `<` the boundary delivery is wrongly rejected. Real-world: legitimate retries arriving at the
    edge of the 300s window would be dropped, silently discarding valid payment events."""
    now = 1_700_000_000
    stale = now - webhookFreshnessWindowSeconds
    future = now + webhookFreshnessWindowSeconds
    assert verifyWebhookFreshness(stale, serverTime=now) is True
    assert verifyWebhookFreshness(future, serverTime=now) is True


def testFreshnessRejectsOneSecondPastWindowStaleSide():
    """GAP 3 (L33): an event one second older than the window must be REJECTED as a replay. This
    fixes the boundary so `<=` and `<` diverge in a test. Real-world: a captured webhook replayed
    just outside the window must not settle a second time."""
    now = 1_700_000_000
    stale = now - (webhookFreshnessWindowSeconds + 1)
    assert verifyWebhookFreshness(stale, serverTime=now) is False


def testFreshnessRejectsOneSecondPastWindowFutureSide():
    """GAP 3 (L33): the window bounds BOTH directions -- an event one second into the future beyond
    the window must be rejected as forged or badly clock-skewed. Real-world: a timestamp from a
    tampered sender must not be trusted."""
    now = 1_700_000_000
    future = now + (webhookFreshnessWindowSeconds + 1)
    assert verifyWebhookFreshness(future, serverTime=now) is False


def testFreshnessBoundaryFlowsThroughFullVerifier():
    """GAP 3 end-to-end: the same edge, driven through verifyRazorpayWebhookSignature with a valid
    signature, must accept at the window edge and reject one second past it -- proving the freshness
    gate, not just the standalone helper, honours the boundary. Real-world: replay defence lives on
    the public entry point callers actually use."""
    now = 1_700_000_000
    edge = now - webhookFreshnessWindowSeconds
    past = now - (webhookFreshnessWindowSeconds + 1)
    assert verifyRazorpayWebhookSignature(
        _payload, _validSignature, _secret, eventTimestamp=edge, serverTime=now
    ) is True
    assert verifyRazorpayWebhookSignature(
        _payload, _validSignature, _secret, eventTimestamp=past, serverTime=now
    ) is False
