// Publishes each completed step onto the mandate engine's existing SSE bus, so the five
// pre-existing dashboard pages (agent-observability, security-audit, infrastructure, ...)
// populate from real runs without any change to useSseStream or telemetryContext.
//
// Mirroring is strictly best-effort: a run must not fail because the telemetry bus is down,
// and it must not be slowed down waiting for it.

import type { ProtocolStepRecord } from "@/types/protocolRunTypes";
import type { TelemetryEventType } from "@/types/telemetryEventTypes";
import { resolveServiceUrls } from "./driverConfig";

const telemetryEventsPath = "/api/v1/telemetry/events";
const mirrorTimeoutMs = 1500;

// This mirror is the only publisher that can honestly claim liveness: every event it sends
// describes a step the driver just executed against the real services. The seeder stamps
// SYNTHETIC, and anything undeclared is treated as UNKNOWN, so the header's LIVE badge is
// reachable only from here.
const liveProvenanceValue = "LIVE";

// Maps a driver step onto the event vocabulary the existing panels already know how to render.
const stepEventTypeMap: Readonly<Record<string, TelemetryEventType>> = {
  fetchQuote: "MCP_TOOL_RESULT",
  verifySla: "MCP_TOOL_RESULT",
  reserveLock: "INVENTORY_LOCKED",
  signIntent: "MANDATE_SIGNED",
  signCart: "MANDATE_SIGNED",
  signExecution: "MANDATE_SIGNED",
  tamperCart: "MANDATE_SIGNED",
  verifyChain: "MANDATE_SIGNED",
  settle: "PAYMENT_CAPTURED"
};

const refusalEventTypeMap: Readonly<Record<string, TelemetryEventType>> = {
  "INV-03": "BUDGET_BLOCKED",
  "INV-02": "ROUTE_ROLLBACK_TRIGGERED"
};

function resolveEventType(step: ProtocolStepRecord): TelemetryEventType {
  if (step.status === "REFUSED" && step.refusal?.invariantViolated) {
    const mapped = refusalEventTypeMap[step.refusal.invariantViolated];
    if (mapped) {
      return mapped;
    }
  }
  return stepEventTypeMap[step.stepId] ?? "HEARTBEAT";
}

export async function mirrorStepToTelemetryBus(
  runId: string,
  step: ProtocolStepRecord
): Promise<void> {
  const { mandateEngineUrl } = resolveServiceUrls();
  const event = {
    eventId: `${runId}-${step.stepId}`,
    eventType: resolveEventType(step),
    timestampMs: Date.now(),
    sessionId: runId,
    provenance: liveProvenanceValue,
    payload: {
      stepId: step.stepId,
      title: step.title,
      status: step.status,
      durationMs: step.durationMs,
      protocolLayer: step.protocolLayer,
      sdkMethod: step.sdkCall.methodName,
      ...(step.resultSummary ?? {}),
      ...(step.refusal ? { refusal: step.refusal } : {})
    }
  };

  try {
    await fetch(`${mandateEngineUrl}${telemetryEventsPath}`, {
      method: "POST",
      headers: { "Content-Type": "application/json" },
      body: JSON.stringify(event),
      signal: AbortSignal.timeout(mirrorTimeoutMs)
    });
  } catch {
    // Intentionally swallowed: the run's own result is the source of truth, and the mirror
    // is a convenience for the legacy panels. A dead bus must not abort a live demo.
  }
}
