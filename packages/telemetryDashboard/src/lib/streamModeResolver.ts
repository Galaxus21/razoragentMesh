// Decides what the connection badge is allowed to claim.
//
// The badge used to read CONNECTED -> "LIVE MESH SSE", which only ever proved that an
// EventSource had opened. `scripts/seedTelemetryStream.py` POSTs scripted fixtures onto the
// same bus, so a laptop with no mesh running at all could display a full "live" settlement.
// Liveness is a property of the events, not of the socket, so it is derived here from the
// provenance each publisher stamps.

import type {
  SseConnectionState,
  TelemetryEvent,
  TelemetryProvenance,
  TelemetryStreamMode
} from "@/types/telemetryEventTypes";

export const liveProvenance: TelemetryProvenance = "LIVE";
export const syntheticProvenance: TelemetryProvenance = "SYNTHETIC";
export const unknownProvenance: TelemetryProvenance = "UNKNOWN";

const heartbeatEventType = "HEARTBEAT";

export interface StreamProvenanceCounts {
  readonly liveCount: number;
  readonly syntheticCount: number;
  readonly unknownCount: number;
}

// An event that never declared its provenance has not proven it is real, so it is UNKNOWN and
// counts against liveness. Defaulting the other way would let any publisher claim liveness by
// simply omitting the field, which is the failure this whole module exists to prevent.
export function resolveEventProvenance(event: TelemetryEvent): TelemetryProvenance {
  return event.provenance ?? unknownProvenance;
}

// Heartbeats are transport keepalives emitted by the SSE server itself, not descriptions of
// protocol work, so they must not make an idle stream look busy.
export function selectMeaningfulEvents(
  events: ReadonlyArray<TelemetryEvent>
): ReadonlyArray<TelemetryEvent> {
  return events.filter((event) => event.eventType !== heartbeatEventType);
}

export function summarizeStreamProvenance(
  events: ReadonlyArray<TelemetryEvent>
): StreamProvenanceCounts {
  let liveCount = 0;
  let syntheticCount = 0;
  let unknownCount = 0;

  for (const event of selectMeaningfulEvents(events)) {
    const provenance = resolveEventProvenance(event);
    if (provenance === liveProvenance) {
      liveCount += 1;
    } else if (provenance === syntheticProvenance) {
      syntheticCount += 1;
    } else {
      unknownCount += 1;
    }
  }

  return { liveCount, syntheticCount, unknownCount };
}

export function resolveStreamMode(
  connectionState: SseConnectionState,
  events: ReadonlyArray<TelemetryEvent>
): TelemetryStreamMode {
  if (connectionState === "CONNECTING") {
    return "CONNECTING";
  }
  if (connectionState !== "CONNECTED") {
    return "OFFLINE";
  }

  const { liveCount, syntheticCount, unknownCount } = summarizeStreamProvenance(events);
  const unprovenCount = syntheticCount + unknownCount;

  if (liveCount === 0 && unprovenCount === 0) {
    return "IDLE";
  }
  // Reported rather than hidden: a fixture that arrives during a real run must not be masked
  // by the live events around it.
  if (liveCount > 0 && unprovenCount > 0) {
    return "MIXED";
  }
  return liveCount > 0 ? "LIVE" : "REPLAY";
}
