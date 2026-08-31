"""Real-time Server-Sent Events (SSE) telemetry emitter for RazorAgent Mesh."""

import asyncio
import json
import time
from typing import Any, AsyncGenerator, Dict, Optional, Set
from pydantic import BaseModel, ConfigDict, Field

heartbeatIntervalSeconds: int = 15
defaultQueueCapacity: int = 500
sseDataPrefix: str = "data: "
sseDataSuffix: str = "\n\n"
sseHeartbeatFrame: str = ": heartbeat\n\n"

# Provenance marks whether an event was produced by a real protocol execution or by a scripted
# fixture replay. Without it the dashboard can only observe that the SSE socket opened, which
# says nothing about whether the events flowing through it describe real work -- so a seeded
# demo used to render identically to a live settlement.
provenanceLive: str = "LIVE"
provenanceSynthetic: str = "SYNTHETIC"
provenanceUnknown: str = "UNKNOWN"
provenancePattern: str = "^(LIVE|SYNTHETIC|UNKNOWN)$"


class TelemetryEventModel(BaseModel):
    """Immutable telemetry event payload frame."""

    model_config = ConfigDict(frozen=True, extra="forbid")

    eventId: str = Field(min_length=1)
    eventType: str = Field(min_length=1)
    timestampMs: int = Field(gt=0)
    sessionId: str = Field(min_length=1)
    payload: Dict[str, Any] = Field(default_factory=dict)
    # Defaults to UNKNOWN, never to LIVE: a publisher that does not declare its provenance has
    # not proven the event is real, and an undeclared event must not be able to light up a
    # "live" indicator by omission.
    provenance: str = Field(default=provenanceUnknown, pattern=provenancePattern)


class TelemetryEventEmitter:
    """Manages asynchronous pub-sub queues for broadcasting telemetry events over SSE."""

    def __init__(self, queueCapacity: int = defaultQueueCapacity) -> None:
        self._queueCapacity: int = queueCapacity
        self._subscribers: Set[asyncio.Queue[str]] = set()
        self._lock: asyncio.Lock = asyncio.Lock()

    async def registerSubscriber(self) -> asyncio.Queue[str]:
        """Registers a new SSE listener queue."""
        clientQueue: asyncio.Queue[str] = asyncio.Queue(maxsize=self._queueCapacity)
        async with self._lock:
            self._subscribers.add(clientQueue)
        return clientQueue

    async def removeSubscriber(self, clientQueue: asyncio.Queue[str]) -> None:
        """Removes a disconnected SSE listener queue."""
        async with self._lock:
            self._subscribers.discard(clientQueue)

    async def publishEvent(self, event: TelemetryEventModel) -> int:
        """Broadcasts a telemetry event to all active subscriber queues."""
        serializedData: str = json.dumps(event.model_dump(), separators=(",", ":"))
        frame: str = f"{sseDataPrefix}{serializedData}{sseDataSuffix}"
        deliveredCount: int = 0

        async with self._lock:
            staleQueues: Set[asyncio.Queue[str]] = set()
            for subscriberQueue in self._subscribers:
                try:
                    subscriberQueue.put_nowait(frame)
                    deliveredCount += 1
                except asyncio.QueueFull:
                    # Drop frame if client buffer is overwhelmed to preserve server stability
                    staleQueues.add(subscriberQueue)

            for staleQueue in staleQueues:
                self._subscribers.discard(staleQueue)

        return deliveredCount

    async def subscribeStream(self) -> AsyncGenerator[str, None]:
        """Async generator yielding formatted SSE text chunks and periodic heartbeats."""
        clientQueue: asyncio.Queue[str] = await self.registerSubscriber()
        try:
            while True:
                try:
                    eventChunk: str = await asyncio.wait_for(
                        clientQueue.get(), timeout=float(heartbeatIntervalSeconds)
                    )
                    yield eventChunk
                except asyncio.TimeoutError:
                    yield sseHeartbeatFrame
        finally:
            await self.removeSubscriber(clientQueue)

    @property
    def activeSubscriberCount(self) -> int:
        """Returns the current number of active listeners."""
        return len(self._subscribers)


# Global singleton instance for easy dependency injection across FastAPI routers
globalTelemetryEmitter: TelemetryEventEmitter = TelemetryEventEmitter()
