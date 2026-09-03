// Covers the telemetry the MCP tool layer publishes so an external agent's work shows up on
// the dashboard. The contract these tests defend is that publishing is invisible to the caller:
// a tool must return the same result, at the same speed, whether or not the bus is reachable.

import assert from "node:assert/strict";
import test, { afterEach, beforeEach } from "node:test";
import { dispatchToolCall } from "../src/mcpServerMain.js";
import { publishToolResult } from "../src/telemetry/telemetryPublisher.js";

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

test("the three mandate tools each publish MANDATE_SIGNED, which lights the Mandate Explorer", async () => {
  // The panel's three cards stayed PENDING for every live agent run: its only producers were the
  // dashboard's own driver and the synthetic seeder, so an external MCP buyer left it dark while
  // Metrics Bar and Webhook Feed filled from the engine's own PAYMENT_CAPTURED.
  const delegation = (await dispatchToolCall(
    "establish_agent_delegation",
    { key_custody: "mesh_demo_custodial", max_budget_paise: 10_000_000, single_transaction_limit_paise: 10_000_000 },
    { sessionId: testSessionId }
  )) as Record<string, unknown>;
  await settlePublishes();

  const intent = eventsOfType("MANDATE_SIGNED");
  assert.equal(intent.length, 1);
  assert.equal(intent[0].payload.mandateType, "INTENT");
  assert.equal(intent[0].payload.verificationStatus, "VALID");
  assert.equal(typeof intent[0].payload.mandateHash, "string");
  assert.ok(intent[0].payload.signerKeyDid, "the panel falls back to a role label without this");
  assert.equal(intent[0].provenance, "LIVE");

  const quote = (await dispatchToolCall(
    "get_live_sku_quote",
    { sku_id: testSkuId, quantity: 2, buyer_agent_id: String(delegation.delegated_agent_did), delivery_pincode: testPincode },
    { sessionId: testSessionId }
  )) as Record<string, unknown>;
  const lock = (await dispatchToolCall(
    "reserve_inventory_lock",
    {
      sku_id: testSkuId, quantity: 2, lock_ttl_seconds: 60,
      buyer_agent_id: String(delegation.delegated_agent_did), quote_hash: String(quote.quote_hash)
    },
    { sessionId: testSessionId }
  )) as Record<string, unknown>;

  await dispatchToolCall(
    "create_cart_mandate",
    {
      delegation_id: String(delegation.delegation_id), sku_id: testSkuId, quantity: 2,
      delivery_pincode: testPincode, delivery_state_code: "29",
      quote_hash: String(quote.quote_hash), quote_expiry_timestamp: quote.quote_expiry_timestamp,
      lock_token: String(lock.lock_token), fencing_token: lock.fencing_token,
      lock_expires_at_unix_ms: lock.expires_at_unix_ms, lock_signature: String(lock.signature)
    },
    { sessionId: testSessionId }
  );
  await dispatchToolCall(
    "sign_execution_mandate",
    { delegation_id: String(delegation.delegation_id) },
    { sessionId: testSessionId }
  );
  await settlePublishes();

  const kinds = eventsOfType("MANDATE_SIGNED").map((event) => event.payload.mandateType);
  assert.deepEqual(kinds, ["INTENT", "CART", "EXECUTION"]);

  // Every card the panel renders must carry a hash, or it shows an em dash where the chain
  // linkage should be. Only create_cart_mandate returns one, so the other two are computed.
  for (const event of eventsOfType("MANDATE_SIGNED")) {
    assert.equal(typeof event.payload.mandateHash, "string", String(event.payload.mandateType));
    assert.match(String(event.payload.mandateHash), /^[0-9a-f]{64}$/);
  }
});

test("a tool that signs no mandate publishes no MANDATE_SIGNED", async () => {
  await dispatchToolCall(
    "get_live_sku_quote",
    { sku_id: testSkuId, quantity: 1, buyer_agent_id: testBuyerDid, delivery_pincode: testPincode },
    { sessionId: testSessionId }
  );
  await settlePublishes();
  assert.equal(eventsOfType("MANDATE_SIGNED").length, 0);
});

// negotiate_price runs a whole negotiation inside one tool call, so unlike every other derived
// publisher here it fans one result out into several events. Driven through publishToolResult
// rather than dispatchToolCall: the capturing fetch above stands in for the telemetry bus, and
// dispatching the real tool would send its gateway traffic there too.
const negotiationResult = {
  sku_id: testSkuId,
  quantity: 2,
  status: "CONVERGED",
  list_unit_price_paise: 100_000,
  agreed_unit_price_paise: 91_805,
  contract_ast_hash: "ast_hash_deadbeef",
  turns: [
    { turn_number: 1, buyer_bid_paise: 85_000, seller_ask_paise: 100_000, spread_paise: 15_000,
      converged: false, micro_fee_paise: 50, cumulative_micro_fees_paise: 50 },
    { turn_number: 2, buyer_bid_paise: 91_570, seller_ask_paise: 91_805, spread_paise: 235,
      converged: false, micro_fee_paise: 50, cumulative_micro_fees_paise: 100 },
    { turn_number: 3, buyer_bid_paise: 92_599, seller_ask_paise: 91_805, spread_paise: 0,
      converged: true, micro_fee_paise: 50, cumulative_micro_fees_paise: 150 }
  ]
};

test("a negotiation publishes one BID_TURN_COMPLETED per turn, which is what the chart plots", async () => {
  publishToolResult("negotiate_price", {}, negotiationResult, testSessionId, "call-neg", 900);
  await settlePublishes();

  const turns = eventsOfType("BID_TURN_COMPLETED");
  assert.equal(turns.length, 3);
  assert.deepEqual(turns.map((event) => event.payload.turnNumber), [1, 2, 3]);
  // Distinct eventIds, or the dashboard's dedupe collapses three turns into one point.
  assert.equal(new Set(turns.map((event) => event.eventId)).size, 3);
  assert.deepEqual(
    turns.map((event) => event.payload.status),
    ["IN_PROGRESS", "IN_PROGRESS", "CONVERGED"]
  );
});

test("convergence publishes NEGOTIATION_CONVERGED with the gross the buyer committed to", async () => {
  publishToolResult("negotiate_price", {}, negotiationResult, testSessionId, "call-neg2", 900);
  await settlePublishes();

  const converged = eventsOfType("NEGOTIATION_CONVERGED");
  assert.equal(converged.length, 1);
  assert.equal(converged[0].payload.finalAgreedUnitPricePaise, 91_805);
  assert.equal(converged[0].payload.totalTurns, 3);
  // Unit price times quantity. The panel shows this as the deal value, so an off-by-quantity
  // here understates a bulk negotiation by the whole multiplier.
  assert.equal(converged[0].payload.totalGrossPaise, 183_610);
  assert.equal(converged[0].payload.contractAstHash, "ast_hash_deadbeef");
});

test("an exhausted negotiation marks its last turn EXHAUSTED and converges nothing", async () => {
  publishToolResult(
    "negotiate_price",
    {},
    { ...negotiationResult, status: "EXHAUSTED", agreed_unit_price_paise: null,
      contract_ast_hash: null,
      turns: negotiationResult.turns.map((turn) => ({ ...turn, converged: false })) },
    testSessionId,
    "call-neg3",
    900
  );
  await settlePublishes();

  assert.equal(eventsOfType("NEGOTIATION_CONVERGED").length, 0);
  const statuses = eventsOfType("BID_TURN_COMPLETED").map((event) => event.payload.status);
  assert.deepEqual(statuses, ["IN_PROGRESS", "IN_PROGRESS", "EXHAUSTED"]);
});
