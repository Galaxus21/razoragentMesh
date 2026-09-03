// Publishes MCP tool activity onto the mandate engine's SSE bus.
//
// Why this exists: this package previously held no HTTP client at all, so an external agent
// calling a tool produced nothing the dashboard could render. MCP_TOOL_CALL / MCP_TOOL_RESULT
// were only ever produced by the seeder (stamped SYNTHETIC) or by the dashboard's own driver
// describing steps it had run itself. A judge watching the dashboard while their own agent
// worked saw an empty screen until settlement.
//
// Best-effort by contract: nothing here is awaited by a tool call, and every failure is
// swallowed. A dead telemetry bus must not fail, delay, or alter a purchase.

import { randomUUID } from "node:crypto";
import {
  liveProvenanceValue,
  millisecondsPerSecond,
  resolveMandateEngineUrl,
  telemetryEventsPath,
  telemetryTimeoutMs
} from "../constants/telemetryConstants.js";
import { toolReserveInventoryLock } from "../constants/protocolConstants.js";

/** The six root keys the engine's TelemetryEventModel accepts. It is extra="forbid". */
interface TelemetryEvent {
  readonly eventId: string;
  readonly eventType: string;
  readonly timestampMs: number;
  readonly sessionId: string;
  readonly payload: Record<string, unknown>;
  readonly provenance: string;
}

const eventTypeToolCall = "MCP_TOOL_CALL";
const eventTypeToolResult = "MCP_TOOL_RESULT";
const eventTypeInventoryLocked = "INVENTORY_LOCKED";
const unknownAgentId = "unknown";

/**
 * Fire-and-forget POST. Deliberately not awaited by callers and deliberately silent on
 * failure -- see the module header. Errors reach stderr only, never stdout, which on the
 * stdio transport carries the JSON-RPC stream and would be corrupted by stray writes.
 */
function publishEvent(event: TelemetryEvent): void {
  const url = `${resolveMandateEngineUrl()}${telemetryEventsPath}`;
  void fetch(url, {
    method: "POST",
    headers: { "Content-Type": "application/json" },
    body: JSON.stringify(event),
    signal: AbortSignal.timeout(telemetryTimeoutMs)
  }).catch(() => {
    // Swallowed by design. The tool's own result is the source of truth.
  });
}

/** timestampMs must be a positive integer: the engine validates it with gt=0. */
function nowMs(): number {
  return Math.floor(Date.now());
}

function asRecord(value: unknown): Record<string, unknown> {
  return value !== null && typeof value === "object" ? (value as Record<string, unknown>) : {};
}

/**
 * The agent's own identifier, so the dashboard can attribute a call to whoever made it.
 * Tools accept both snake_case (MCP manifest) and camelCase (buyer SDK) spellings.
 */
function extractCallerAgentId(toolArguments: unknown): string {
  const args = asRecord(toolArguments);
  const candidate = args.buyer_agent_id ?? args.buyerAgentId ?? args.buyerAgentDid;
  return typeof candidate === "string" && candidate.length > 0 ? candidate : unknownAgentId;
}

export function newCallId(): string {
  return randomUUID();
}

/** MCP_TOOL_CALL -- payload shape is McpToolCallPayload in the dashboard's type union. */
export function publishToolCall(
  toolName: string,
  toolArguments: unknown,
  sessionId: string,
  callId: string
): void {
  publishEvent({
    eventId: `${callId}-call`,
    eventType: eventTypeToolCall,
    timestampMs: nowMs(),
    sessionId,
    provenance: liveProvenanceValue,
    payload: {
      toolName,
      callId,
      callerAgentId: extractCallerAgentId(toolArguments),
      parameters: asRecord(toolArguments)
    }
  });
}

/** MCP_TOOL_RESULT, plus INVENTORY_LOCKED when a lock was actually taken. */
export function publishToolResult(
  toolName: string,
  toolArguments: unknown,
  output: unknown,
  sessionId: string,
  callId: string,
  durationMs: number
): void {
  const result = asRecord(output);
  publishEvent({
    eventId: `${callId}-result`,
    eventType: eventTypeToolResult,
    timestampMs: nowMs(),
    sessionId,
    provenance: liveProvenanceValue,
    payload: { toolName, callId, success: true, result, durationMs }
  });

  if (toolName === toolReserveInventoryLock) {
    publishInventoryLocked(result, asRecord(toolArguments), sessionId, callId);
  }
}

/**
 * A refusal is still a result: success=false rather than a missing event. The dashboard shows
 * a refusal as the protocol working, so dropping these would hide the most convincing thing
 * an external agent can demonstrate.
 */
export function publishToolRefusal(
  toolName: string,
  error: unknown,
  sessionId: string,
  callId: string,
  durationMs: number
): void {
  const err = error as Error & { code?: string | number };
  publishEvent({
    eventId: `${callId}-result`,
    eventType: eventTypeToolResult,
    timestampMs: nowMs(),
    sessionId,
    provenance: liveProvenanceValue,
    payload: {
      toolName,
      callId,
      success: false,
      result: { error: err?.message ?? String(error), exceptionCode: err?.code ?? null },
      durationMs
    }
  });
}

/**
 * INVENTORY_LOCKED -- payload shape is InventoryLockedPayload, whose ttlSeconds is a required
 * number. The lock tool's response carries expires_at_unix_ms but no ttl, so the TTL is taken
 * from the request (authoritative, it is what was asked for) and derived from the expiry only
 * as a fallback. Publishing null here would put a null into a field the dashboard types as a
 * number.
 */
function resolveLockTtlSeconds(
  result: Record<string, unknown>,
  toolArguments: Record<string, unknown>
): number {
  const requested = toolArguments.lock_ttl_seconds ?? toolArguments.lockTtlSeconds;
  if (typeof requested === "number" && Number.isFinite(requested)) {
    return Math.trunc(requested);
  }
  const expiresAt = result.expires_at_unix_ms;
  if (typeof expiresAt === "number" && Number.isFinite(expiresAt)) {
    return Math.max(0, Math.round((expiresAt - Date.now()) / millisecondsPerSecond));
  }
  return 0;
}

function publishInventoryLocked(
  result: Record<string, unknown>,
  toolArguments: Record<string, unknown>,
  sessionId: string,
  callId: string
): void {
  const lockToken = result.lock_token;
  if (typeof lockToken !== "string") {
    return;
  }
  publishEvent({
    eventId: `${callId}-lock`,
    eventType: eventTypeInventoryLocked,
    timestampMs: nowMs(),
    sessionId,
    provenance: liveProvenanceValue,
    payload: {
      skuId: result.sku_id,
      quantityLocked: result.quantity_locked,
      lockToken,
      fencingToken: result.fencing_token,
      ttlSeconds: resolveLockTtlSeconds(result, toolArguments)
    }
  });
}
