import { describe, it } from "node:test";
import assert from "node:assert/strict";

import { buildLiveAgentSessions } from "../src/lib/liveAgentSteps.js";
import type { TelemetryEvent } from "../src/types/telemetryEventTypes.js";

function toolCall(
  sessionId: string,
  callId: string,
  toolName: string,
  timestampMs: number
): TelemetryEvent {
  return {
    eventId: `${callId}-call`,
    eventType: "MCP_TOOL_CALL",
    timestampMs,
    sessionId,
    provenance: "LIVE",
    payload: {
      toolName,
      callId,
      callerAgentId: "did:agent:abc",
      parameters: { sku_id: "SKU-015" },
    },
  } as TelemetryEvent;
}

function toolResult(
  sessionId: string,
  callId: string,
  toolName: string,
  timestampMs: number,
  success: boolean
): TelemetryEvent {
  return {
    eventId: `${callId}-result`,
    eventType: "MCP_TOOL_RESULT",
    timestampMs,
    sessionId,
    provenance: "LIVE",
    payload: {
      toolName,
      callId,
      success,
      durationMs: 34,
      result: success ? { ok: true } : { error: "Settlement refused: replayed nonce" },
    },
  } as TelemetryEvent;
}

describe("buildLiveAgentSessions", () => {
  it("groups events by sessionId so two concurrent agents never share a pipeline", () => {
    const events = [
      toolCall("session-b", "c2", "search_catalog", 200),
      toolCall("session-a", "c1", "search_catalog", 100),
    ];

    const sessions = buildLiveAgentSessions(events);

    assert.equal(sessions.length, 2);
    assert.deepEqual(
      sessions.map((session) => session.sessionId),
      // Most recent session first.
      ["session-b", "session-a"]
    );
    assert.equal(sessions[0].steps.length, 1);
    assert.equal(sessions[1].steps.length, 1);
  });

  it("folds a tool result into its call rather than rendering two stages", () => {
    const events = [
      toolResult("s1", "c1", "get_live_sku_quote", 150, true),
      toolCall("s1", "c1", "get_live_sku_quote", 100),
    ];

    const [session] = buildLiveAgentSessions(events);

    assert.equal(session.steps.length, 1);
    assert.equal(session.steps[0].status, "SUCCEEDED");
    assert.equal(session.steps[0].durationMs, 34);
    assert.deepEqual(session.steps[0].resultSummary, { ok: true });
  });

  it("orders stages oldest-first even though the stream arrives newest-first", () => {
    const events = [
      toolCall("s1", "c3", "reserve_inventory_lock", 300),
      toolCall("s1", "c2", "get_live_sku_quote", 200),
      toolCall("s1", "c1", "search_catalog", 100),
    ];

    const [session] = buildLiveAgentSessions(events);

    assert.deepEqual(
      session.steps.map((step) => step.sdkCall.methodName),
      ["search_catalog", "get_live_sku_quote", "reserve_inventory_lock"]
    );
    assert.deepEqual(
      session.steps.map((step) => step.ordinal),
      [1, 2, 3]
    );
  });

  it("renders a refused call as REFUSED, never as FAILED", () => {
    // A refusal is the protocol working -- a replayed nonce or an over-budget cart is the mesh
    // doing its job. FAILED is reserved for genuinely broken things, and colouring a refusal
    // that way would tell a judge the demo crashed when it in fact defended itself.
    const events = [
      toolResult("s1", "c1", "execute_settlement", 150, false),
      toolCall("s1", "c1", "execute_settlement", 100),
    ];

    const [session] = buildLiveAgentSessions(events);

    assert.equal(session.steps[0].status, "REFUSED");
    assert.equal(session.refusalCount, 1);
    assert.equal(session.steps[0].refusal?.message, "Settlement refused: replayed nonce");
  });

  it("renders a 500 as FAILED, not as a refusal the mesh chose to make", () => {
    // Seen live: settlement returned HTTP 500 "Connection closed by server" and the page
    // labelled it REFUSED -- PROTOCOL WORKED. That tells a reader the mesh successfully
    // defended itself when in fact a service fell over.
    const failure = {
      eventId: "c1-result",
      eventType: "MCP_TOOL_RESULT",
      timestampMs: 150,
      sessionId: "s1",
      payload: {
        toolName: "execute_settlement",
        callId: "c1",
        success: false,
        durationMs: 18,
        result: {
          error: "Settlement refused: [HTTP 500] Internal settlement error",
          exceptionCode: 500,
        },
      },
    } as TelemetryEvent;

    const [session] = buildLiveAgentSessions([
      failure,
      toolCall("s1", "c1", "execute_settlement", 100),
    ]);

    assert.equal(session.steps[0].status, "FAILED");
    assert.equal(session.steps[0].refusal?.errorName, "MeshError");
    assert.equal(session.refusalCount, 0, "a breakage must not be counted as a defended attack");
  });

  it("keeps a 409 replay and a 403 unauthorized agent as genuine refusals", () => {
    for (const statusCode of [409, 403, 400, 502]) {
      const refused = {
        eventId: `r-${statusCode}`,
        eventType: "MCP_TOOL_RESULT",
        timestampMs: 150,
        sessionId: `s-${statusCode}`,
        payload: {
          toolName: "execute_settlement",
          callId: `c-${statusCode}`,
          success: false,
          durationMs: 12,
          result: { error: "refused", exceptionCode: statusCode },
        },
      } as TelemetryEvent;

      const [session] = buildLiveAgentSessions([
        refused,
        toolCall(`s-${statusCode}`, `c-${statusCode}`, "execute_settlement", 100),
      ]);

      assert.equal(session.steps[0].status, "REFUSED", `status ${statusCode} must stay REFUSED`);
      assert.equal(session.steps[0].refusal?.statusCode, statusCode);
    }
  });

  it("leaves a call still in flight as RUNNING", () => {
    const [session] = buildLiveAgentSessions([toolCall("s1", "c1", "execute_settlement", 100)]);

    assert.equal(session.steps[0].status, "RUNNING");
    assert.equal(session.steps[0].durationMs, 0);
  });

  it("drops heartbeats and events with no session", () => {
    const heartbeat = {
      eventId: "hb",
      eventType: "HEARTBEAT",
      timestampMs: 100,
      sessionId: "s1",
      payload: {},
    } as TelemetryEvent;
    const orphan = { ...toolCall("", "c9", "search_catalog", 100) };

    const sessions = buildLiveAgentSessions([heartbeat, orphan]);

    assert.deepEqual(sessions, []);
  });

  it("never fabricates wire exchanges or crypto artifacts", () => {
    // Telemetry does not carry them. Synthesising a plausible request/response pair would put
    // invented bytes in a panel whose whole purpose is showing what really went over the wire.
    const events = [
      toolResult("s1", "c1", "create_cart_mandate", 150, true),
      toolCall("s1", "c1", "create_cart_mandate", 100),
    ];

    const [session] = buildLiveAgentSessions(events);

    assert.deepEqual(session.steps[0].exchanges, []);
    assert.deepEqual(session.steps[0].artifacts, []);
  });

  it("maps each tool to the package that does the work, for the packages-touched strip", () => {
    const events = [
      toolCall("s1", "c1", "search_catalog", 100),
      toolCall("s1", "c2", "create_cart_mandate", 200),
      toolCall("s1", "c3", "execute_settlement", 300),
    ];

    const [session] = buildLiveAgentSessions(events);

    assert.deepEqual(
      session.steps.map((step) => step.implementedBy),
      [
        "packages/mcpServer/src/tools",
        "packages/buyerSdkTs/src/agentMandateBuilder.ts",
        "packages/mandateEngine",
      ]
    );
  });

  it("re-attaches PAYMENT_CAPTURED, which the engine keys by paymentId, to the agent's session", () => {
    // The mandate engine stamps sessionId with the PAYMENT id, so the capture arrived as its own
    // one-stage session -- splitting the single event a reader most wants to see off the run
    // that produced it. Both events carry the paymentId, so they can be joined on it.
    const paymentId = "pay_mcp_abc123";
    const settlementResult = {
      eventId: "c1-result",
      eventType: "MCP_TOOL_RESULT",
      timestampMs: 200,
      sessionId: "mcp-session",
      payload: {
        toolName: "execute_settlement",
        callId: "c1",
        success: true,
        durationMs: 19,
        result: { status: "captured", paymentId },
      },
    } as TelemetryEvent;
    const captured = {
      eventId: "cap",
      eventType: "PAYMENT_CAPTURED",
      timestampMs: 210,
      sessionId: paymentId,
      payload: { paymentId },
    } as TelemetryEvent;

    const sessions = buildLiveAgentSessions([
      captured,
      settlementResult,
      toolCall("mcp-session", "c1", "execute_settlement", 100),
    ]);

    assert.equal(sessions.length, 1, "the capture must not become its own session");
    assert.equal(sessions[0].sessionId, "mcp-session");
    assert.deepEqual(
      sessions[0].steps.map((step) => step.title),
      ["Settle", "Payment captured"]
    );
  });

  it("falls back to the tool name for a tool it has no description for", () => {
    const [session] = buildLiveAgentSessions([toolCall("s1", "c1", "some_future_tool", 100)]);

    assert.equal(session.steps[0].title, "some_future_tool");
    assert.equal(session.steps[0].sdkCall.methodName, "some_future_tool");
  });
});
