// Covers the telemetry the MCP tool layer publishes so an external agent's work shows up on
// the dashboard. The contract these tests defend is that publishing is invisible to the caller:
// a tool must return the same result, at the same speed, whether or not the bus is reachable.

import assert from "node:assert/strict";
import test, { afterEach, beforeEach } from "node:test";
import { dispatchToolCall } from "../src/mcpServerMain.js";

const testSkuId = "SKU-CHAIR-001";
const testBuyerDid = "did:agent:a1b2c3d4e5f60718293a4b5c6d7e8f90a1b2c3d4e5f60718293a4b5c6d7e8f90";
const testPincode = "560034";
const testSessionId = "session-under-test";

interface CapturedEvent {
  readonly eventId: string;
  readonly eventType: string;
  readonly timestampMs: number;
  readonly sessionId: string;
  readonly payload: Record<string, unknown>;
  readonly provenance: string;
}

const originalFetch = globalThis.fetch;
let captured: CapturedEvent[] = [];

/** Collects every published event instead of reaching the network. */
function installCapturingFetch(): void {
  captured = [];
  globalThis.fetch = (async (_url: string, init?: { body?: string }) => {
    if (init?.body) {
      captured.push(JSON.parse(init.body) as CapturedEvent);
    }
    return { ok: true, status: 202 } as Response;
  }) as typeof globalThis.fetch;
}

/** Publishing must be fire-and-forget, so give the microtask queue a turn to drain. */
async function settlePublishes(): Promise<void> {
  await new Promise((resolve) => setTimeout(resolve, 20));
}

beforeEach(() => installCapturingFetch());
afterEach(() => {
  globalThis.fetch = originalFetch;
});

function eventsOfType(eventType: string): CapturedEvent[] {
  return captured.filter((event) => event.eventType === eventType);
}

test("a tool call publishes a call and a result sharing one callId", async () => {
  await dispatchToolCall(
    "get_live_sku_quote",
    {
      sku_id: testSkuId,
      quantity: 2,
      buyer_agent_id: testBuyerDid,
      delivery_pincode: testPincode
    },
    { sessionId: testSessionId }
  );
  await settlePublishes();

  const calls = eventsOfType("MCP_TOOL_CALL");
  const results = eventsOfType("MCP_TOOL_RESULT");
  assert.equal(calls.length, 1);
  assert.equal(results.length, 1);

  // The dashboard pairs a result to its call by callId; without that the panels cannot show
  // which invocation a result belongs to when an agent runs tools concurrently.
  assert.equal(calls[0].payload.callId, results[0].payload.callId);
  assert.notEqual(calls[0].eventId, results[0].eventId, "each event needs its own id");

  // Attribution: the dashboard shows which agent acted.
  assert.equal(calls[0].payload.callerAgentId, testBuyerDid);
  assert.equal(results[0].payload.success, true);
  assert.equal(typeof results[0].payload.durationMs, "number");
});

test("published events carry the session id and LIVE provenance", async () => {
  await dispatchToolCall(
    "verify_shipping_sla",
    {
      origin_pincode: "560001",
      delivery_pincode: testPincode,
      package_weight_grams: 500,
      required_delivery_tier: "standard"
    },
    { sessionId: testSessionId }
  );
  await settlePublishes();

  assert.ok(captured.length > 0, "the SLA tool must report its work");
  for (const event of captured) {
    // Grouping: every event from one agent's session shares this id.
    assert.equal(event.sessionId, testSessionId);
    // The dashboard's LIVE badge requires liveCount > 0 and zero unproven events. These
    // describe tools the mesh genuinely executed, unlike the seeder's SYNTHETIC fixtures.
    assert.equal(event.provenance, "LIVE");
    assert.ok(Number.isInteger(event.timestampMs) && event.timestampMs > 0);
  }
});

test("a refusal is published as success:false rather than dropped", async () => {
  await assert.rejects(() =>
    dispatchToolCall(
      "get_live_sku_quote",
      {
        sku_id: "SKU-NOT-A-REAL-ITEM",
        quantity: 1,
        buyer_agent_id: testBuyerDid,
        delivery_pincode: testPincode
      },
      { sessionId: testSessionId }
    )
  );
  await settlePublishes();

  const results = eventsOfType("MCP_TOOL_RESULT");
  assert.equal(results.length, 1, "a refusal still owes the dashboard a result event");
  assert.equal(results[0].payload.success, false);
  // A refusal is the protocol working. Dropping these would hide the most convincing thing an
  // external agent can demonstrate.
  const result = results[0].payload.result as Record<string, unknown>;
  assert.match(String(result.error), /not found in catalog/);
});

test("a lock reports the TTL that was requested, not a null", async () => {
  const requestedTtlSeconds = 45;
  await dispatchToolCall(
    "reserve_inventory_lock",
    {
      sku_id: testSkuId,
      quantity: 1,
      lock_ttl_seconds: requestedTtlSeconds,
      buyer_agent_id: testBuyerDid,
      quote_hash: "test-hash"
    },
    { sessionId: testSessionId }
  );
  await settlePublishes();

  const locked = eventsOfType("INVENTORY_LOCKED");
  assert.equal(locked.length, 1);
  // InventoryLockedPayload types ttlSeconds as a required number. The tool's response carries
  // expires_at_unix_ms and no ttl, so this is taken from the request; publishing the missing
  // field verbatim put a null into a numeric field.
  assert.equal(locked[0].payload.ttlSeconds, requestedTtlSeconds);
  assert.equal(locked[0].payload.skuId, testSkuId);
  assert.equal(typeof locked[0].payload.lockToken, "string");
});

test("a dead telemetry bus does not fail the tool call", async () => {
  // The whole contract: the bus is a convenience for the panels, never a dependency of a
  // purchase. A judge's demo must not die because the mandate engine is slow to boot.
  globalThis.fetch = (async () => {
    throw new Error("telemetry bus is unreachable");
  }) as typeof globalThis.fetch;

  const quote = await dispatchToolCall(
    "get_live_sku_quote",
    {
      sku_id: testSkuId,
      quantity: 1,
      buyer_agent_id: testBuyerDid,
      delivery_pincode: testPincode
    },
    { sessionId: testSessionId }
  ) as Record<string, unknown>;

  assert.equal(quote.sku_id, testSkuId, "the quote must be returned regardless");
  await settlePublishes();
});
