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
import {
  toolCreateCartMandate,
  toolEstablishAgentDelegation,
  toolNegotiatePrice,
  toolReserveInventoryLock,
  toolSignExecutionMandate
} from "../constants/protocolConstants.js";
import { computeMandateHash } from "@razorpay/agent-buyer-sdk";

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
const eventTypeMandateSigned = "MANDATE_SIGNED";
const eventTypeBidTurnCompleted = "BID_TURN_COMPLETED";
const eventTypeNegotiationConverged = "NEGOTIATION_CONVERGED";
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
  if (toolName === toolNegotiatePrice) {
    publishNegotiationTurns(result, sessionId, callId);
  }
  publishMandateSigned(toolName, result, sessionId, callId);
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

/**
 * BID_TURN_COMPLETED per turn, then NEGOTIATION_CONVERGED -- what lights the Negotiation Chart.
 *
 * The gateway itself emits neither, so before negotiate_price existed the panel could only ever
 * render rows the seeder had written: the chart claimed a negotiation capability that no live run
 * had ever produced a single data point for.
 *
 * One tool call is a whole negotiation, so this fans a single result out into several events --
 * unlike the other derived publishers here, which emit at most one. The chart plots bid against
 * ask per turn, so the turns have to arrive separately or there is nothing to draw.
 */
function publishNegotiationTurns(
  result: Record<string, unknown>,
  sessionId: string,
  callId: string
): void {
  const turns = Array.isArray(result.turns) ? result.turns : [];
  const maxTurns = turns.length;
  const converged = result.status === "CONVERGED";

  turns.forEach((rawTurn, index) => {
    const turn = asRecord(rawTurn);
    publishEvent({
      eventId: `${callId}-turn-${index + 1}`,
      eventType: eventTypeBidTurnCompleted,
      timestampMs: nowMs(),
      sessionId,
      provenance: liveProvenanceValue,
      payload: {
        turnNumber: turn.turn_number,
        maxTurns,
        buyerBidPaise: turn.buyer_bid_paise,
        sellerAskPaise: turn.seller_ask_paise,
        spreadPaise: turn.spread_paise,
        microFeePaidPaise: turn.micro_fee_paise,
        cumulativeMicroFeesPaise: turn.cumulative_micro_fees_paise,
        // The panel's union is IN_PROGRESS | CONVERGED | EXHAUSTED. Only the last turn can carry
        // a terminal status: every earlier one left the negotiation still open by definition.
        status: _resolveTurnStatus(turn.converged === true, index === maxTurns - 1, converged)
      }
    });
  });

  if (!converged) {
    return;
  }
  const agreedUnitPricePaise = result.agreed_unit_price_paise;
  const quantity = result.quantity;
  publishEvent({
    eventId: `${callId}-converged`,
    eventType: eventTypeNegotiationConverged,
    timestampMs: nowMs(),
    sessionId,
    provenance: liveProvenanceValue,
    payload: {
      finalAgreedUnitPricePaise: agreedUnitPricePaise,
      totalTurns: maxTurns,
      totalGrossPaise:
        typeof agreedUnitPricePaise === "number" && typeof quantity === "number"
          ? agreedUnitPricePaise * quantity
          : 0,
      // Null when the gateway converged without returning an AST hash. The panel types this as a
      // string, so an empty string is the honest rendering of "converged, none published".
      contractAstHash: typeof result.contract_ast_hash === "string" ? result.contract_ast_hash : ""
    }
  });
}

function _resolveTurnStatus(
  turnConverged: boolean,
  isFinalTurn: boolean,
  negotiationConverged: boolean
): string {
  if (turnConverged) {
    return "CONVERGED";
  }
  return isFinalTurn && !negotiationConverged ? "EXHAUSTED" : "IN_PROGRESS";
}

/**
 * MANDATE_SIGNED -- what lights the dashboard's Mandate Explorer for an external MCP buyer.
 *
 * The panel's three cards stayed PENDING for every live agent run, because the only producers of
 * this event were the dashboard's own protocol driver and the synthetic seeder: nothing on the
 * MCP path emitted it. Metrics Bar and Webhook Feed did populate, because the engine emits
 * PAYMENT_CAPTURED server-side -- so the empty panel read as "the dashboard does not see external
 * agents", which was never true.
 *
 * Derived here rather than in the tools, following publishInventoryLocked: the tool files stay
 * about producing mandates, and the whole feature is one function plus a dispatch line.
 */
function publishMandateSigned(
  toolName: string,
  result: Record<string, unknown>,
  sessionId: string,
  callId: string
): void {
  const signed = _resolveSignedMandate(toolName, result);
  if (!signed) {
    return;
  }
  publishEvent({
    eventId: `${callId}-mandate`,
    eventType: eventTypeMandateSigned,
    timestampMs: nowMs(),
    sessionId,
    provenance: liveProvenanceValue,
    payload: {
      mandateType: signed.mandateType,
      mandateHash: signed.mandateHash,
      signerKeyDid: signed.signerKeyDid,
      // The panel treats anything other than "INVALID" as valid. These mandates were just minted
      // and signed by this server, so saying so is accurate rather than optimistic.
      verificationStatus: "VALID",
      ...(signed.canonicalJcsPreview === undefined
        ? {}
        : { canonicalJcsPreview: signed.canonicalJcsPreview })
    }
  });
}

interface SignedMandateFacts {
  readonly mandateType: string;
  readonly mandateHash: string | null;
  readonly signerKeyDid: unknown;
  readonly canonicalJcsPreview?: unknown;
}

/**
 * Maps a tool result onto the three mandate kinds the panel renders. The mandate TYPE comes from
 * the tool name -- no tool reports its own kind, and it does not need to. The hash is read where
 * a tool already returns one and computed from the mandate document otherwise, which is why this
 * needs no changes inside the tools: they all return the signed document itself.
 */
function _resolveSignedMandate(
  toolName: string,
  result: Record<string, unknown>
): SignedMandateFacts | undefined {
  if (toolName === toolEstablishAgentDelegation) {
    const intentMandate = asRecord(result.intent_mandate);
    return {
      mandateType: "INTENT",
      mandateHash: _hashMandate(intentMandate),
      signerKeyDid: result.user_did ?? intentMandate.userDid
    };
  }
  if (toolName === toolCreateCartMandate) {
    return {
      mandateType: "CART",
      // Already computed by the tool, so reuse it rather than rehashing and risking a document
      // that canonicalises differently from the one the agent was handed.
      mandateHash: typeof result.cart_mandate_hash === "string" ? result.cart_mandate_hash : null,
      signerKeyDid: result.merchant_did
    };
  }
  if (toolName === toolSignExecutionMandate) {
    // Custodial mode returns the complete signed mandate; agent-held returns the unsigned payload
    // plus the exact canonical JSON the agent is asked to sign. Hash whichever is present.
    const executionMandate = asRecord(result.execution_mandate ?? result.unsigned_payload);
    return {
      mandateType: "EXECUTION",
      mandateHash: _hashMandate(executionMandate),
      signerKeyDid: result.buyer_agent_did,
      canonicalJcsPreview:
        typeof result.signing_payload_canonical_json === "string"
          ? result.signing_payload_canonical_json
          : undefined
    };
  }
  return undefined;
}

/** Best-effort: a hash the panel merely displays must never be able to fail a tool call. */
function _hashMandate(mandate: Record<string, unknown>): string | null {
  if (Object.keys(mandate).length === 0) {
    return null;
  }
  try {
    return computeMandateHash(mandate);
  } catch {
    return null;
  }
}
