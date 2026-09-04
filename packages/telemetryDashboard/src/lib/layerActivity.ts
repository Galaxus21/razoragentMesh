// Folds the live telemetry stream onto the six-layer stack, so a reader can watch WHERE in the
// protocol an agent currently is rather than only WHAT it called.
//
// The session view answers "what did this agent do, in order". This answers a different question
// that the session view cannot: which layer is doing work right now, which layers have already
// finished, which refused, and which never ran at all. A run that never reaches Negotiation and a
// run that negotiated and settled look similar as a list of steps; as a lit-up stack they do not.
//
// Nothing here is synthesised. A layer with no events is idle and says so -- it is never
// backfilled with a plausible-looking step, because the point of the graph is that an empty
// Resilience layer means the healer genuinely did not fire.

import {
  eventPresentation,
  toolPresentation,
  unknownToolPresentation
} from "@/constants/liveAgentConstants";
import { protocolLayerNodes, type ProtocolLayerNode } from "@/constants/protocolLayerMap";
import type { TelemetryEvent, ToolFailureKind } from "@/types/telemetryEventTypes";

/** How long after its last event a layer still reads as working. */
export const layerActiveWindowMs = 6_000;

/** Per-layer log cap. Newest wins; the telemetry layer would otherwise be all heartbeats. */
export const layerLogLimit = 40;

export type LayerStatus = "idle" | "active" | "done" | "refused";

/**
 * The layer whose work is the stream itself.
 *
 * Its map entry declares HEARTBEAT as its only event, and nothing in the mesh emits one -- so
 * read literally, the Telemetry node sits dark through a run it is demonstrably carrying, which
 * reads as a broken service rather than as an idle one. It is credited with every event instead,
 * because delivering them IS its work: each row in another layer's log reached the browser
 * through this one. That is a description of what happened, not a synthetic event.
 */
const streamCarryingLayerId = "telemetry";

/**
 * Every MCP tool invocation publishes a CALL and a RESULT, so without this the log printed each
 * step twice at the same second under the same label, with nothing to say why.
 */
export type LayerLogOutcome = "call" | "ok" | "invalid" | "refused" | "event";

export interface LayerLogEntry {
  readonly eventId: string;
  readonly timestampMs: number;
  readonly title: string;
  /** The tool name where there is one, else the raw event type. Always the real wire label. */
  readonly detail: string;
  readonly outcome: LayerLogOutcome;
  readonly isRefusal: boolean;
  readonly sessionId: string;
}

export interface LayerActivity {
  readonly node: ProtocolLayerNode;
  readonly status: LayerStatus;
  readonly eventCount: number;
  /**
   * How many calls this layer turned down. Carried separately from `status` on purpose: a
   * refusal is the headline of this project -- the mesh saying no is the protocol working -- but
   * it is a fact about the layer's history, not about what it is doing now. Folded into the
   * status it made a busy layer read as "refused" for the rest of the run.
   */
  readonly refusalCount: number;
  /**
   * Calls this layer rejected as malformed. Reported next to the refusal count rather than
   * merged into it: one says the agent misdialled, the other says the mesh said no, and only
   * the second is evidence of anything.
   */
  readonly invalidRequestCount: number;
  readonly lastEventAtMs: number | null;
  readonly log: readonly LayerLogEntry[];
}

interface PayloadView {
  readonly toolName?: string;
  readonly success?: boolean;
  readonly failureKind?: ToolFailureKind;
  readonly result?: { readonly error?: unknown };
}

function readPayload(event: TelemetryEvent): PayloadView {
  return (event.payload ?? {}) as PayloadView;
}

/**
 * Resolves the layer an event belongs to, by title.
 *
 * Tool calls are resolved by TOOL first and event type second, and the order matters: every MCP
 * tool call is an MCP_TOOL_CALL, so resolving by event type alone would file execute_settlement
 * and negotiate_price under Discovery along with the catalog search, and the Settlement and
 * Negotiation layers would never light up at all.
 */
function resolveLayerTitle(event: TelemetryEvent): string | null {
  const { toolName } = readPayload(event);
  if (toolName) {
    return (toolPresentation[toolName] ?? unknownToolPresentation).protocolLayer;
  }

  const byEvent = eventPresentation[event.eventType]?.protocolLayer;
  if (byEvent) {
    return byEvent;
  }

  // Last resort: the layer map itself declares which events each layer emits. This catches
  // HEARTBEAT, which has no presentation entry because the session view drops it, but which is
  // exactly what proves the Telemetry layer is alive.
  const declaring = protocolLayerNodes.find((node) =>
    node.eventsEmitted.includes(event.eventType)
  );
  return declaring?.title ?? null;
}

/**
 * A failed tool call that the agent simply got wrong.
 *
 * The MCP server stamps `failureKind` on the payload, but events published before that field
 * existed carry only the error text. Zod serialises its issues as a JSON array, so a leading
 * bracket plus an issue code is a reliable second read on the same fact rather than a guess.
 */
function isInvalidRequest(event: TelemetryEvent): boolean {
  if (event.eventType !== "MCP_TOOL_RESULT") {
    return false;
  }
  const payload = readPayload(event);
  if (payload.success !== false) {
    return false;
  }
  if (payload.failureKind) {
    return payload.failureKind === "invalid_request";
  }
  const errorText = (payload.result as { error?: unknown } | undefined)?.error;
  return (
    typeof errorText === "string" &&
    errorText.trimStart().startsWith("[") &&
    /"(?:code|validation)"\s*:/.test(errorText)
  );
}

/**
 * A refusal is the mesh declining a call it understood.
 *
 * A schema violation is deliberately NOT one. Counting it as a refusal inflates the claim this
 * whole dashboard rests on -- a live run turned eleven missing-argument retries into "11 refused
 * -- protocol worked", which the log itself contradicts the moment anyone opens it.
 */
function isRefusal(event: TelemetryEvent): boolean {
  if (event.eventType === "BUDGET_BLOCKED" || event.eventType === "ROUTE_ROLLBACK_TRIGGERED") {
    return true;
  }
  return (
    event.eventType === "MCP_TOOL_RESULT" &&
    readPayload(event).success === false &&
    !isInvalidRequest(event)
  );
}

/** What a log row actually reports, so a call and its result stop reading as one event twice. */
function entryOutcome(event: TelemetryEvent): LayerLogOutcome {
  if (event.eventType === "MCP_TOOL_CALL") {
    return "call";
  }
  if (isRefusal(event)) {
    return "refused";
  }
  if (isInvalidRequest(event)) {
    return "invalid";
  }
  if (event.eventType === "MCP_TOOL_RESULT") {
    return "ok";
  }
  return "event";
}

function entryTitle(event: TelemetryEvent): string {
  const { toolName } = readPayload(event);
  if (toolName) {
    return (toolPresentation[toolName] ?? { title: toolName }).title;
  }
  return eventPresentation[event.eventType]?.title ?? event.eventType;
}

/**
 * Groups the stream by layer and stamps each layer with a status as of `nowMs`.
 *
 * `nowMs` is passed in rather than read from the clock so the caller controls the tick: the graph
 * re-renders on a timer to let "active" decay back to "done" when an agent stops working, and a
 * function that read Date.now() itself could not be tested or driven from a fixed frame.
 */
export function buildLayerActivity(
  events: readonly TelemetryEvent[],
  nowMs: number
): readonly LayerActivity[] {
  const byLayerTitle = new Map<string, TelemetryEvent[]>();

  for (const event of events) {
    const layerTitle = resolveLayerTitle(event);
    if (!layerTitle) {
      continue;
    }
    const bucket = byLayerTitle.get(layerTitle) ?? [];
    bucket.push(event);
    byLayerTitle.set(layerTitle, bucket);
  }

  return protocolLayerNodes.map((node) => {
    // The stream hook prepends, so a bucket arrives newest-first; the log wants that order but
    // the bounds do not, so sort explicitly rather than trusting arrival order.
    const source =
      node.layerId === streamCarryingLayerId ? events : (byLayerTitle.get(node.title) ?? []);
    const bucket = [...source].sort((left, right) => right.timestampMs - left.timestampMs);

    if (bucket.length === 0) {
      return {
        node,
        status: "idle" as const,
        eventCount: 0,
        refusalCount: 0,
        invalidRequestCount: 0,
        lastEventAtMs: null,
        log: []
      };
    }

    const lastEventAtMs = bucket[0].timestampMs;
    // Counted only for the layer that actually refused. The stream-carrying layer transports
    // every refusal in the run, and crediting it with them would paint the bus red for failures
    // that happened somewhere else entirely.
    const refusalCount =
      node.layerId === streamCarryingLayerId ? 0 : bucket.filter(isRefusal).length;
    const invalidRequestCount =
      node.layerId === streamCarryingLayerId ? 0 : bucket.filter(isInvalidRequest).length;

    // Active outranks refused. A layer that turned one call down and is still working must read
    // as working -- the refusal is not lost, it is on the node's own badge and in its log.
    const status: LayerStatus =
      nowMs - lastEventAtMs <= layerActiveWindowMs
        ? "active"
        : refusalCount > 0
          ? "refused"
          : "done";

    const log: LayerLogEntry[] = bucket.slice(0, layerLogLimit).map((event) => ({
      eventId: event.eventId,
      timestampMs: event.timestampMs,
      title: entryTitle(event),
      detail: readPayload(event).toolName ?? event.eventType,
      outcome: entryOutcome(event),
      isRefusal: isRefusal(event),
      sessionId: event.sessionId
    }));

    return {
      node,
      status,
      eventCount: bucket.length,
      refusalCount,
      invalidRequestCount,
      lastEventAtMs,
      log
    };
  });
}
