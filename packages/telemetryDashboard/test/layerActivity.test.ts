import { describe, it } from "node:test";
import assert from "node:assert/strict";

import { buildLayerActivity, layerActiveWindowMs } from "../src/lib/layerActivity.js";
import type { TelemetryEvent } from "../src/types/telemetryEventTypes.js";

const baseTimeMs = 1_760_000_000_000;

function toolCall(
  toolName: string,
  atMs: number,
  eventId: string
): TelemetryEvent {
  return {
    eventId,
    eventType: "MCP_TOOL_CALL",
    timestampMs: atMs,
    sessionId: "sess-1",
    payload: { toolName, callId: `call-${eventId}`, callerAgentId: "agent-1", parameters: {} }
  } as TelemetryEvent;
}

const zodIssuesJson = '[{ "code": "invalid_type", "path": ["sku_id"] }]';
const zodRegexIssuesJson = '[{ "validation": "regex", "path": ["buyer_agent_id"] }]';

function toolResult(
  toolName: string,
  atMs: number,
  eventId: string,
  payloadExtra: Record<string, unknown>
): TelemetryEvent {
  return {
    eventId,
    eventType: "MCP_TOOL_RESULT",
    timestampMs: atMs,
    sessionId: "sess-1",
    payload: { toolName, callId: `call-${eventId}`, durationMs: 5, ...payloadExtra }
  } as TelemetryEvent;
}

describe("Layer activity graph — a misdialled call is not a refusal", () => {
  it("should count a schema violation as an invalid call, never as a refusal", () => {
    // A live agy run produced eleven of these across five tools -- every one a missing or
    // malformed argument the agent immediately retried correctly -- and the graph reported them
    // as "11 refused, protocol worked". The mesh had refused nothing.
    const activities = buildLayerActivity(
      [
        toolResult("negotiate_price", baseTimeMs, "e1", {
          success: false,
          failureKind: "invalid_request",
          result: { error: zodIssuesJson }
        })
      ],
      baseTimeMs + layerActiveWindowMs + 1
    );

    const negotiation = activities.find((activity) => activity.node.title === "Negotiation");
    assert.equal(negotiation?.invalidRequestCount, 1);
    assert.equal(negotiation?.refusalCount, 0);
    // It must not leave the node resting on "refused" either, which is the visible half of the
    // same overstatement.
    assert.equal(negotiation?.status, "done");
    assert.equal(negotiation?.log[0]?.isRefusal, false);
    assert.equal(negotiation?.log[0]?.outcome, "invalid");
  });

  it("should still count a well-formed call the mesh declined as a refusal", () => {
    const activities = buildLayerActivity(
      [
        toolResult("execute_settlement", baseTimeMs, "e1", {
          success: false,
          failureKind: "refusal",
          result: { error: "cart total exceeds delegated budget", exceptionCode: "BUDGET" }
        })
      ],
      baseTimeMs + layerActiveWindowMs + 1
    );

    const settlement = activities.find((activity) => activity.node.title === "Settlement");
    assert.equal(settlement?.refusalCount, 1);
    assert.equal(settlement?.invalidRequestCount, 0);
    assert.equal(settlement?.status, "refused");
    assert.equal(settlement?.log[0]?.outcome, "refused");
  });

  it("should classify a pre-failureKind event from its error text", () => {
    // Events published before the server stamped failureKind carry only the Zod issues JSON.
    const activities = buildLayerActivity(
      [
        toolResult("get_live_sku_quote", baseTimeMs, "e1", {
          success: false,
          result: { error: zodRegexIssuesJson }
        })
      ],
      baseTimeMs
    );

    const discovery = activities.find((activity) => activity.node.title === "Discovery");
    assert.equal(discovery?.invalidRequestCount, 1);
    assert.equal(discovery?.refusalCount, 0);
  });

  it("should tell a tool call apart from its result in the log", () => {
    // Both are published for every invocation, at the same second, under the same label. Without
    // an outcome the log printed each step twice with nothing to explain the repeat.
    const activities = buildLayerActivity(
      [
        toolCall("search_catalog", baseTimeMs, "e1"),
        toolResult("search_catalog", baseTimeMs + 1, "e2", { success: true, result: {} })
      ],
      baseTimeMs + 2
    );

    const discovery = activities.find((activity) => activity.node.title === "Discovery");
    assert.deepEqual(
      discovery?.log.map((entry) => entry.outcome),
      ["ok", "call"]
    );
  });
});

describe("Layer activity graph — event to layer mapping", () => {
  it("should file a tool call under the tool's layer, not under MCP_TOOL_CALL's layer", () => {
    // Every MCP tool call is an MCP_TOOL_CALL, and the layer map declares that event type on
    // Discovery. Resolving by event type first would file settlement and negotiation calls under
    // Discovery, leaving those two nodes dark through an entire purchase.
    const activities = buildLayerActivity(
      [
        toolCall("search_catalog", baseTimeMs, "e1"),
        toolCall("negotiate_price", baseTimeMs + 10, "e2"),
        toolCall("execute_settlement", baseTimeMs + 20, "e3")
      ],
      baseTimeMs + 30
    );

    const countFor = (title: string): number =>
      activities.find((activity) => activity.node.title === title)?.eventCount ?? -1;

    assert.equal(countFor("Discovery"), 1);
    assert.equal(countFor("Negotiation"), 1);
    assert.equal(countFor("Settlement"), 1);
  });

  it("should report every layer, including the ones with no traffic", () => {
    const activities = buildLayerActivity([toolCall("search_catalog", baseTimeMs, "e1")], baseTimeMs);

    assert.equal(activities.length, 6);
    const resilience = activities.find((activity) => activity.node.title === "Resilience");
    // An empty layer is a finding, not a gap: it means the healer never fired. It must still be
    // rendered, and it must never be backfilled with a plausible-looking step.
    assert.equal(resilience?.status, "idle");
    assert.equal(resilience?.eventCount, 0);
    assert.equal(resilience?.refusalCount, 0);
    assert.deepEqual(resilience?.log, []);
  });

  it("should decay a layer from working to done once its activity window lapses", () => {
    const events = [toolCall("search_catalog", baseTimeMs, "e1")];

    const during = buildLayerActivity(events, baseTimeMs + layerActiveWindowMs - 1);
    const after = buildLayerActivity(events, baseTimeMs + layerActiveWindowMs + 1);

    assert.equal(during.find((a) => a.node.title === "Discovery")?.status, "active");
    assert.equal(after.find((a) => a.node.title === "Discovery")?.status, "done");
  });

  it("should mark a layer refused when the mesh turned a call down", () => {
    const blocked: TelemetryEvent = {
      eventId: "e-blocked",
      eventType: "BUDGET_BLOCKED",
      timestampMs: baseTimeMs,
      sessionId: "sess-1",
      payload: {}
    } as unknown as TelemetryEvent;

    // While the layer is still working, "working" is the honest label -- a node stuck on
    // "refused" for the rest of the run reads as broken rather than as the protocol doing its
    // job. The refusal is never lost: it is counted separately and flagged in the log.
    const during = buildLayerActivity([blocked], baseTimeMs);
    const settlingDuring = during.find((activity) => activity.node.title === "Settlement");
    assert.equal(settlingDuring?.status, "active");
    assert.equal(settlingDuring?.refusalCount, 1);
    assert.equal(settlingDuring?.log[0]?.isRefusal, true);

    // Once it settles, the refusal becomes the layer's resting state rather than a plain done.
    const after = buildLayerActivity([blocked], baseTimeMs + layerActiveWindowMs + 1);
    assert.equal(after.find((activity) => activity.node.title === "Settlement")?.status, "refused");
  });

  it("should credit the telemetry layer with the stream it carries, not with refusals", () => {
    const blocked: TelemetryEvent = {
      eventId: "e-blocked",
      eventType: "BUDGET_BLOCKED",
      timestampMs: baseTimeMs,
      sessionId: "sess-1",
      payload: {}
    } as unknown as TelemetryEvent;

    const activities = buildLayerActivity(
      [toolCall("search_catalog", baseTimeMs, "e1"), blocked],
      baseTimeMs
    );
    const telemetry = activities.find((activity) => activity.node.title === "Telemetry");

    // Nothing in the mesh emits HEARTBEAT, the only event its map entry declares, so read
    // literally this node sits dark through a run it is demonstrably carrying.
    assert.equal(telemetry?.eventCount, 2);
    assert.equal(telemetry?.status, "active");

    // But the refusal belongs to Settlement, which refused, not to the bus that carried it.
    assert.equal(telemetry?.refusalCount, 0);
    assert.equal(
      activities.find((activity) => activity.node.title === "Settlement")?.refusalCount,
      1
    );
  });

  it("should order each layer's log newest first", () => {
    const activities = buildLayerActivity(
      [
        toolCall("search_catalog", baseTimeMs, "old"),
        toolCall("get_live_sku_quote", baseTimeMs + 500, "new")
      ],
      baseTimeMs + 600
    );

    const discovery = activities.find((activity) => activity.node.title === "Discovery");
    assert.equal(discovery?.log[0]?.eventId, "new");
    assert.equal(discovery?.log[1]?.eventId, "old");
  });
});
