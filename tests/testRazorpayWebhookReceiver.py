"""The inbound Razorpay webhook route, and the fact that it exists at all.

`webhookVerifier.py` was written, exported and covered by `testWebhookVerifier.py` while being
mounted on no route -- so nothing could deliver to it and payment state could only ever come from
the settle call this mesh initiates (AUDIT_TODO item 52). These tests hold the route in place and
pin the four answers it owes a sender: verified, unverifiable, stale, and already seen.
"""

import hashlib
import hmac
import json
import time

import fakeredis.aioredis
import httpx
import pytest
from httpx import ASGITransport

from razoragentMesh.packages.mandateEngine import createMandateApp
from razoragentMesh.packages.mandateEngine.webhooks import endpointRazorpayWebhook

testWebhookSecret = "whsec_razoragent_test_9f21"
secretEnvVar = "RAZORPAY_WEBHOOK_SECRET"


def _capturedPaymentBody(paymentId: str = "pay_LiveCapture001") -> bytes:
    """A Razorpay payment.captured envelope, serialized exactly as it would be delivered."""
    return json.dumps(
        {
            "entity": "event",
            "event": "payment.captured",
            "contains": ["payment"],
            "payload": {"payment": {"entity": {"id": paymentId, "amount": 410000, "status": "captured"}}},
            "created_at": int(time.time()),
        }
    ).encode("utf-8")


def _sign(payloadBytes: bytes, secret: str = testWebhookSecret) -> str:
    return hmac.new(secret.encode("utf-8"), payloadBytes, hashlib.sha256).hexdigest()


def _headers(payloadBytes: bytes, eventId: str, eventTime: int | None = None) -> dict:
    headers = {
        "Content-Type": "application/json",
        "X-Razorpay-Signature": _sign(payloadBytes),
        "X-Razorpay-Event-Id": eventId,
    }
    if eventTime is not None:
        headers["X-Razorpay-Event-Time"] = str(eventTime)
    return headers


def _appWithRedis():
    app = createMandateApp()
    app.state.redis = fakeredis.aioredis.FakeRedis()
    return app


def _client(app) -> httpx.AsyncClient:
    return httpx.AsyncClient(transport=ASGITransport(app=app), base_url="http://test")


def testWebhookRouteIsActuallyMounted() -> None:
    """The finding itself: a verifier no route calls cannot receive anything."""
    paths = {getattr(route, "path", None) for route in createMandateApp().routes}
    assert endpointRazorpayWebhook in paths


@pytest.mark.asyncio
async def testVerifiedDeliveryIsAcceptedAndUnderstood(monkeypatch) -> None:
    monkeypatch.setenv(secretEnvVar, testWebhookSecret)
    body = _capturedPaymentBody()

    async with _client(_appWithRedis()) as client:
        response = await client.post(
            endpointRazorpayWebhook, content=body, headers=_headers(body, "evt_ok_1", int(time.time()))
        )

    assert response.status_code == 200
    delivered = response.json()
    assert delivered["status"] == "accepted"
    assert delivered["event"] == "payment.captured"
    assert delivered["paymentId"] == "pay_LiveCapture001"
    # A 200 acknowledges receipt and nothing more: no order is persisted for it to amend.
    assert delivered["reconciled"] is False


@pytest.mark.asyncio
async def testTamperedBodyIsRefusedWithUnauthorized(monkeypatch) -> None:
    monkeypatch.setenv(secretEnvVar, testWebhookSecret)
    body = _capturedPaymentBody()
    headers = _headers(body, "evt_tampered_1", int(time.time()))
    tampered = body.replace(b'"amount": 410000', b'"amount": 1')

    async with _client(_appWithRedis()) as client:
        response = await client.post(endpointRazorpayWebhook, content=tampered, headers=headers)

    assert response.status_code == 401
    assert "Signature" in response.json()["detail"]


@pytest.mark.asyncio
async def testStaleDeliveryIsRefusedAsBadRequestNotAsForgery(monkeypatch) -> None:
    """A replay of a genuinely signed payload is a different failure from a forged one."""
    monkeypatch.setenv(secretEnvVar, testWebhookSecret)
    body = _capturedPaymentBody()
    staleTime = int(time.time()) - 3600

    async with _client(_appWithRedis()) as client:
        response = await client.post(
            endpointRazorpayWebhook, content=body, headers=_headers(body, "evt_stale_1", staleTime)
        )

    assert response.status_code == 400
    assert "freshness window" in response.json()["detail"]


@pytest.mark.asyncio
async def testUnconfiguredSecretRefusesRatherThanAccepting(monkeypatch) -> None:
    """Fail closed. An endpoint that 200s what it cannot verify is worse than no endpoint."""
    monkeypatch.delenv(secretEnvVar, raising=False)
    body = _capturedPaymentBody()

    async with _client(_appWithRedis()) as client:
        response = await client.post(
            endpointRazorpayWebhook, content=body, headers=_headers(body, "evt_nosecret_1")
        )

    assert response.status_code == 503
    assert "RAZORPAY_WEBHOOK_SECRET" in response.json()["detail"]


@pytest.mark.asyncio
async def testRetriedDeliveryIsDeduplicatedAndStillAcknowledged(monkeypatch) -> None:
    """Razorpay retries until it gets a 2xx, so a duplicate must be 200 -- never 409."""
    monkeypatch.setenv(secretEnvVar, testWebhookSecret)
    body = _capturedPaymentBody()
    headers = _headers(body, "evt_retry_1", int(time.time()))
    app = _appWithRedis()

    async with _client(app) as client:
        first = await client.post(endpointRazorpayWebhook, content=body, headers=headers)
        second = await client.post(endpointRazorpayWebhook, content=body, headers=headers)

    assert first.json()["status"] == "accepted"
    assert second.status_code == 200
    assert second.json()["status"] == "duplicate"


@pytest.mark.asyncio
async def testVerifiedButUnrecognisedEnvelopeIsStillAccepted(monkeypatch) -> None:
    """The signature proves the sender. Refusing an unmet shape would make new event types
    from Razorpay look like forgeries."""
    monkeypatch.setenv(secretEnvVar, testWebhookSecret)
    body = json.dumps({"event": "subscription.charged", "payload": {}}).encode("utf-8")

    async with _client(_appWithRedis()) as client:
        response = await client.post(
            endpointRazorpayWebhook, content=body, headers=_headers(body, "evt_unknown_1", int(time.time()))
        )

    assert response.status_code == 200
    assert response.json()["event"] == "subscription.charged"
    assert response.json()["paymentId"] is None
