"""Unit tests for telemetryEmitter SSE engine."""

import asyncio
import json
import pytest
from pydantic import ValidationError
from razoragentMesh.packages.mandateEngine.telemetryEmitter import (
    TelemetryEventEmitter,
    TelemetryEventModel,
    provenanceLive,
    provenanceSynthetic,
    provenanceUnknown,
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


@pytest.mark.asyncio
async def testUndeclaredProvenanceDefaultsToUnknownNotLive() -> None:
    """An event that never declares provenance must not be able to imply liveness.

    The dashboard badge reads this field to decide whether it may say LIVE. Defaulting to LIVE
    -- or omitting the field from the wire frame -- would let any publisher, including the
    fixture seeder, light up a live indicator by simply saying nothing.
    """
    emitter = TelemetryEventEmitter(queueCapacity=4)
    subscriberQueue = await emitter.registerSubscriber()

    undeclaredEvent = TelemetryEventModel(
        eventId="evt-undeclared-1",
        eventType="MANDATE_SIGNED",
        timestampMs=1700000000000,
        sessionId="session-undeclared",
        payload={},
    )
    assert undeclaredEvent.provenance == provenanceUnknown

    await emitter.publishEvent(undeclaredEvent)
    receivedChunk = await subscriberQueue.get()
    parsed = json.loads(receivedChunk[len("data: ") : -len("\n\n")])

    assert parsed["provenance"] == provenanceUnknown
    assert parsed["provenance"] != provenanceLive

    await emitter.removeSubscriber(subscriberQueue)


@pytest.mark.asyncio
async def testDeclaredProvenanceSurvivesOntoTheWire() -> None:
    emitter = TelemetryEventEmitter(queueCapacity=4)
    subscriberQueue = await emitter.registerSubscriber()

    for declaredValue in (provenanceLive, provenanceSynthetic, provenanceUnknown):
        await emitter.publishEvent(
            TelemetryEventModel(
                eventId=f"evt-{declaredValue.lower()}",
                eventType="MANDATE_SIGNED",
                timestampMs=1700000000000,
                sessionId="session-declared",
                payload={},
                provenance=declaredValue,
            )
        )
        receivedChunk = await subscriberQueue.get()
        parsed = json.loads(receivedChunk[len("data: ") : -len("\n\n")])
        assert parsed["provenance"] == declaredValue

    await emitter.removeSubscriber(subscriberQueue)


def testUnrecognizedProvenanceValueIsRejected() -> None:
    """Free-text provenance would let a publisher invent a label the dashboard cannot map."""
    with pytest.raises(ValidationError):
        TelemetryEventModel(
            eventId="evt-bogus-1",
            eventType="MANDATE_SIGNED",
            timestampMs=1700000000000,
            sessionId="session-bogus",
            payload={},
            provenance="TOTALLY_LIVE_TRUST_ME",
        )
