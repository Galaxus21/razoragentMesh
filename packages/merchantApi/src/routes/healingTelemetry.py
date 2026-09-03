"""Publishes measured Layer 3 healing onto the mandate engine's SSE bus.

Before this, `OOS_HEALED` had exactly one producer in the repository:
`scripts/seedTelemetryStream.py`, which emits a fixed `healingDurationMs` of 214 stamped
SYNTHETIC. So the dashboard's "Sub-300ms Vector Self-Healing" tile showed 214ms whatever the
healer did -- including when `packages/vectorHealer` was in no Docker image at all and could not
have run. `metricsBar.tsx` now excludes SYNTHETIC events from that average, which is correct and
also means the tile reads "no measured heals yet" until something real publishes. This is that
something.

Best-effort by contract, copied deliberately from `mcpServer/src/telemetry/telemetryPublisher.ts`:
the publish is never awaited by the route, and every failure is swallowed. A dead telemetry bus
must not fail or delay a substitution search. Telemetry is a view of the system, not part of it.
"""

import asyncio
import logging
import os
import time
import uuid
from typing import Any, Dict, Optional

import httpx

logger = logging.getLogger(__name__)

oosHealedEventType: str = "OOS_HEALED"
millisecondsPerSecond: int = 1000

# Same variable, fallback and path the MCP server's publisher uses
# (mcpServer/src/constants/telemetryConstants.ts). Two services publishing to two different
# buses would split the dashboard's event stream in half.
mandateEngineUrlEnvVar: str = "MANDATE_ENGINE_URL"
fallbackMandateEngineUrl: str = "http://localhost:8000"
mandateEngineTelemetryPath: str = "/api/v1/telemetry/events"
liveProvenanceValue: str = "LIVE"
healingTelemetryTimeoutSeconds: float = 1.5


def resolveMandateEngineUrl() -> str:
    """Reads the engine URL from the environment, falling back to the local default."""
    configured = (os.environ.get(mandateEngineUrlEnvVar) or "").strip()
    return configured if configured else fallbackMandateEngineUrl


def publishOosHealed(
    failedSkuId: str,
    substitutePayload: Dict[str, Any],
    cosineScore: float,
    healingDurationMs: float,
    embeddingMode: str,
    sessionId: Optional[str] = None,
    originalPricePaise: int = 0,
) -> None:
    """Fires an OOS_HEALED event describing a heal that actually happened.

    `embeddingMode` travels with the score because a 'hash' score is character-code overlap and
    not a semantic similarity; a consumer that renders the two identically is reporting a number
    it cannot justify.
    """
    event = {
        "eventId": f"evt-oos-heal-{uuid.uuid4().hex[:12]}",
        "eventType": oosHealedEventType,
        "timestampMs": int(time.time() * millisecondsPerSecond),
        "sessionId": sessionId or f"merchant-api-{uuid.uuid4().hex[:8]}",
        "payload": {
            "originalSkuId": failedSkuId,
            "substituteSkuId": str(substitutePayload.get("skuId", "")),
            "cosineSimilarity": cosineScore,
            # The three fields below are what healingDiffViewer.tsx actually renders, and they
            # were absent. Nobody noticed because no real heal had ever reached the panel (see
            # AUDIT_TODO 50); the first one that did showed the failed SKU at "Price: Rs 0.00",
            # a price delta of "NaN%", and an AST audit reading "Failed" on a successful heal.
            "originalPricePaise": originalPricePaise,
            "priceDeltaPaise": (
                int(substitutePayload.get("baseUnitPricePaise") or 0) - originalPricePaise
            ),
            # Vacuously true: this route passes no NegativeConstraintManifest, so no constraint
            # was evaluated and none was breached. Reporting the absence as a FAILED audit --
            # which is what an omitted field rendered as -- claims a violation that never
            # happened. A caller that does supply a manifest should pass its real verdict.
            "negativeConstraintsPassed": True,
            "substitutePricePaise": substitutePayload.get("baseUnitPricePaise"),
            # Measured with time.perf_counter around the ANN query and the constraint AST, and
            # nothing else. Mandate signing is not in it -- see OosInterceptor.findSubstitute.
            "healingDurationMs": healingDurationMs,
            "embeddingMode": embeddingMode,
        },
        # LIVE is the whole point: TelemetryEventModel defaults to UNKNOWN, and the dashboard
        # counts only non-SYNTHETIC events toward the measured latency figure.
        "provenance": liveProvenanceValue,
    }
    try:
        _fireAndForget(event)
    except Exception as scheduleError:
        # The module contract is that NOTHING here can fail a heal, and the guard belongs at
        # this boundary rather than inside `_fireAndForget`: the caller must be safe whatever
        # the scheduling path does, including a future one that raises something new.
        logger.debug("OOS_HEALED telemetry could not be scheduled: %s", scheduleError)


def _fireAndForget(event: Dict[str, Any]) -> None:
    """Schedules the POST without making the caller wait for it."""
    try:
        asyncio.get_running_loop().create_task(_postEvent(event))
    except RuntimeError:
        # No running loop: called from synchronous code, so there is nothing to schedule onto.
        # Dropping the event is correct here -- blocking a search on a telemetry POST is not.
        logger.debug("No event loop for OOS_HEALED telemetry; event dropped")


async def _postEvent(event: Dict[str, Any]) -> None:
    """Posts one event, swallowing every failure."""
    url = f"{resolveMandateEngineUrl().rstrip('/')}{mandateEngineTelemetryPath}"
    try:
        async with httpx.AsyncClient(timeout=healingTelemetryTimeoutSeconds) as client:
            await client.post(url, json=event)
    except Exception as publishError:
        logger.debug("OOS_HEALED telemetry publish failed: %s", publishError)


__all__ = ["publishOosHealed", "oosHealedEventType"]
