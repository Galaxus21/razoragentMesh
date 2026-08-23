"""Unit tests for telemetryEmitter SSE engine."""

import asyncio
import json
import pytest
from razoragentMesh.packages.mandateEngine.telemetryEmitter import (
    TelemetryEventEmitter,
    TelemetryEventModel,
)


@pytest.mark.asyncio
async def testTelemetryEventEmitterPublishAndSubscribe() -> None:
    emitter = TelemetryEventEmitter(queueCapacity=10)
    assert emitter.activeSubscriberCount == 0

    subscriberQueue = await emitter.registerSubscriber()
    assert emitter.activeSubscriberCount == 1

    testEvent = TelemetryEventModel(
        eventId="evt-test-101",
        eventType="PAYMENT_CAPTURED",
        timestampMs=1700000000000,
        sessionId="session-xyz-1",
        payload={"amountPaise": 420000, "status": "captured"},
    )

    deliveredCount = await emitter.publishEvent(testEvent)
    assert deliveredCount == 1

    receivedChunk = await subscriberQueue.get()
    assert receivedChunk.startswith("data: ")
    assert receivedChunk.endswith("\n\n")

    jsonPayload = receivedChunk[len("data: ") : -len("\n\n")]
    parsed = json.loads(jsonPayload)
    assert parsed["eventId"] == "evt-test-101"
    assert parsed["eventType"] == "PAYMENT_CAPTURED"
    assert parsed["payload"]["amountPaise"] == 420000

    await emitter.removeSubscriber(subscriberQueue)
    assert emitter.activeSubscriberCount == 0
