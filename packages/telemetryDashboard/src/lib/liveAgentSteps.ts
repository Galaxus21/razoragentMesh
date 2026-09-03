// Turns the live telemetry stream into the same ProtocolStepRecord shape the Layer Explorer
// renders, so PackagePipeline, PackagesTouchedStrip and StepDetailPanel are reused unchanged.
//
// Two things this deliberately does NOT do:
//
// It does not synthesise wire exchanges or cryptographic artifacts. The driver captures those
// because it makes the HTTP calls itself; telemetry does not carry them. Fabricating a plausible
// request/response pair here would put invented bytes in a panel whose whole purpose is showing
// what really went over the wire, so `exchanges` and `artifacts` stay empty and the real payload
// is surfaced through `resultSummary`.
//
// It does not invent steps. A session contains exactly the events that arrived.

import {
  eventPresentation,
  ignoredEventTypes,
  liveAgentStepIdPrefix,
  protocolRefusalStatusCodes,
  serverErrorFloor,
  toolPresentation,
  unknownToolPresentation,
  type LiveEventPresentation
} from "@/constants/liveAgentConstants";
import type { ProtocolStepRecord, ProtocolStepStatus } from "@/types/protocolRunTypes";
import type { TelemetryEvent } from "@/types/telemetryEventTypes";

export interface LiveAgentSession {
  readonly sessionId: string;
  readonly steps: readonly ProtocolStepRecord[];
  readonly startedAtMs: number;
  readonly lastEventAtMs: number;
  readonly callerAgentId: string | null;
  readonly refusalCount: number;
}

interface RefusalBody {
  readonly error?: string;
  readonly exceptionCode?: number | string | null;
}

interface PayloadView {
  readonly toolName?: string;
  readonly callId?: string;
  readonly callerAgentId?: string;
  readonly success?: boolean;
  readonly durationMs?: number;
  readonly parameters?: Record<string, unknown>;
  readonly result?: Record<string, unknown>;
}

function readPayload(event: TelemetryEvent): PayloadView {
  return (event.payload ?? {}) as PayloadView;
}

function presentationFor(event: TelemetryEvent, toolName: string | undefined): LiveEventPresentation {
  if (toolName) {
    return toolPresentation[toolName] ?? { ...unknownToolPresentation, title: toolName };
  }
  return (
    eventPresentation[event.eventType] ?? {
      ...unknownToolPresentation,
      title: event.eventType
    }
  );
}

/**
 * A refusal is a passing outcome, not a crash: the mesh rejecting a replayed nonce or an
 * over-budget cart is the protocol working. It maps to REFUSED so the pipeline renders it in
 * accent, never in error red.
 */
function resolveStatus(event: TelemetryEvent, result: TelemetryEvent | undefined): ProtocolStepStatus {
  if (event.eventType === "BUDGET_BLOCKED" || event.eventType === "ROUTE_ROLLBACK_TRIGGERED") {
    return "REFUSED";
  }
  if (event.eventType !== "MCP_TOOL_CALL") {
    return "SUCCEEDED";
  }
  if (!result) {
    return "RUNNING";
  }
  if (readPayload(result).success !== false) {
    return "SUCCEEDED";
  }
  return classifyFailure(result);
}

/**
 * Separates a refusal from a breakage.
 *
 * The mesh's own refusals -- an over-budget cart, a replayed nonce, a signature that does not
 * verify -- come back either with a 4xx from the settlement engine or, for a check made locally
 * inside the tool, with no code at all. A 5xx means a service actually fell over.
 *
 * The codeless case is therefore read as REFUSED, which is right for every local protocol check
 * but not for a locally-thrown infrastructure error such as an unreachable catalog search. That
 * residual ambiguity cannot be settled from telemetry alone: the publisher records `code` only
 * when the thrown error carried one.
 */
function classifyFailure(result: TelemetryEvent): ProtocolStepStatus {
  const body = (readPayload(result).result ?? {}) as RefusalBody;
  const code = typeof body.exceptionCode === "number" ? body.exceptionCode : null;
  if (code === null) {
    return "REFUSED";
  }
  if (protocolRefusalStatusCodes.includes(code)) {
    return "REFUSED";
  }
  return code >= serverErrorFloor ? "FAILED" : "REFUSED";
}

function buildRefusal(result: TelemetryEvent | undefined): ProtocolStepRecord["refusal"] {
  if (!result) {
    return undefined;
  }
  const payload = readPayload(result);
  if (payload.success !== false) {
    return undefined;
  }
  const body = (payload.result ?? {}) as RefusalBody;
  const message = typeof body.error === "string" ? body.error : "The mesh refused this call.";
  const code = typeof body.exceptionCode === "number" ? body.exceptionCode : undefined;
  const broke = code !== undefined && code >= serverErrorFloor && !protocolRefusalStatusCodes.includes(code);
  return {
    errorName: broke ? "MeshError" : "MeshRefusal",
    message,
    ...(code !== undefined ? { statusCode: code } : {})
  };
}

function buildStep(
  event: TelemetryEvent,
  result: TelemetryEvent | undefined,
  ordinal: number
): ProtocolStepRecord {
  const payload = readPayload(event);
  const presentation = presentationFor(event, payload.toolName);
  const resultPayload = result ? readPayload(result) : undefined;
  const summary = resultPayload?.result ?? (event.eventType === "MCP_TOOL_CALL" ? undefined : payload);

  return {
    stepId: `${liveAgentStepIdPrefix}-${event.eventId}`,
    ordinal,
    title: presentation.title,
    narrative: presentation.narrative,
    protocolLayer: presentation.protocolLayer,
    implementedBy: presentation.implementedBy,
    sdkCall: {
      methodName: payload.toolName ?? event.eventType,
      argumentSummary: payload.parameters ?? {},
      isPureCrypto: false
    },
    status: resolveStatus(event, result),
    durationMs: resultPayload?.durationMs ?? 0,
    exchanges: [],
    artifacts: [],
    ...(buildRefusal(result) ? { refusal: buildRefusal(result) } : {}),
    ...(summary ? { resultSummary: summary as Readonly<Record<string, unknown>> } : {})
  };
}

/**
 * Pairs each MCP_TOOL_CALL with the MCP_TOOL_RESULT carrying the same callId, so one call and
 * its outcome render as a single stage with a duration rather than two adjacent rows.
 */
function buildSessionSteps(events: readonly TelemetryEvent[]): readonly ProtocolStepRecord[] {
  const resultsByCallId = new Map<string, TelemetryEvent>();
  for (const event of events) {
    const { callId } = readPayload(event);
    if (event.eventType === "MCP_TOOL_RESULT" && callId) {
      resultsByCallId.set(callId, event);
    }
  }

  const steps: ProtocolStepRecord[] = [];
  for (const event of events) {
    // The result is folded into its call, so it must not also stand as its own stage.
    if (event.eventType === "MCP_TOOL_RESULT") {
      continue;
    }
    const { callId } = readPayload(event);
    const result = callId ? resultsByCallId.get(callId) : undefined;
    steps.push(buildStep(event, result, steps.length + 1));
  }
  return steps;
}

/**
 * Maps each settlement's paymentId back to the MCP session that produced it, read out of the
 * execute_settlement result the agent already received.
 */
function mapPaymentIdsToSessions(
  events: readonly TelemetryEvent[]
): ReadonlyMap<string, string> {
  const sessionByPaymentId = new Map<string, string>();
  for (const event of events) {
    if (event.eventType !== "MCP_TOOL_RESULT") {
      continue;
    }
    const paymentId = readPayload(event).result?.paymentId;
    if (typeof paymentId === "string" && paymentId && event.sessionId) {
      sessionByPaymentId.set(paymentId, event.sessionId);
    }
  }
  return sessionByPaymentId;
}

/**
 * Groups the stream into one session per agent, newest session first.
 *
 * `sessionId` is the MCP transport's own session id, which the server stamps on every tool call
 * it publishes -- so one agent's run groups together even while another agent is connected.
 */
export function buildLiveAgentSessions(
  events: readonly TelemetryEvent[]
): readonly LiveAgentSession[] {
  const ignored = new Set<string>(ignoredEventTypes);
  const bySession = new Map<string, TelemetryEvent[]>();
  const sessionByPaymentId = mapPaymentIdsToSessions(events);

  for (const event of events) {
    if (ignored.has(event.eventType) || !event.sessionId) {
      continue;
    }
    // The mandate engine stamps PAYMENT_CAPTURED with the PAYMENT id where a session id belongs,
    // so the capture -- the event a reader most wants attached to the run -- arrived as a
    // separate one-stage session. Re-keying it here joins the two on a value both already
    // carry, rather than changing the settlement wire contract to thread a session id through.
    const sessionId = sessionByPaymentId.get(event.sessionId) ?? event.sessionId;
    const bucket = bySession.get(sessionId) ?? [];
    bucket.push(event);
    bySession.set(sessionId, bucket);
  }

  const sessions: LiveAgentSession[] = [];
  for (const [sessionId, bucket] of bySession) {
    // The stream hook prepends, so a bucket arrives newest-first; ordinals need the opposite.
    const ordered = [...bucket].sort((left, right) => left.timestampMs - right.timestampMs);
    const steps = buildSessionSteps(ordered);
    const callerAgentId =
      ordered.map((event) => readPayload(event).callerAgentId).find((id) => Boolean(id)) ?? null;

    sessions.push({
      sessionId,
      steps,
      startedAtMs: ordered[0]?.timestampMs ?? 0,
      lastEventAtMs: ordered[ordered.length - 1]?.timestampMs ?? 0,
      callerAgentId: callerAgentId ?? null,
      refusalCount: steps.filter((step) => step.status === "REFUSED").length
    });
  }

  return sessions.sort((left, right) => right.lastEventAtMs - left.lastEventAtMs);
}
