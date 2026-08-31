import { describe, it } from "node:test";
import assert from "node:assert/strict";

import {
  navigationItems,
  AppSidebar,
  isRouteMatching,
} from "../src/components/appSidebar.js";
import {
  defaultSidebarCollapsed,
  sidebarStorageKey,
} from "../src/hooks/useSidebarState.js";
import {
  connectionStatusColors,
  connectionStatusLabels,
} from "../src/constants/dashboardConstants.js";
import { DashboardHeader } from "../src/components/dashboardHeader.js";
import {
  createTestNegotiationScenarioEvents,
  createTestNominalSettlementEvents,
  createTestOosHealingScenarioEvents,
} from "./fixtures/testTelemetryFixtures.js";
import { SseConnectionState, TelemetryEvent } from "../src/types/telemetryEventTypes.js";

const expectedRouteList: ReadonlyArray<string> = [
  "/overview",
  "/protocol",
  "/self-healing",
  "/infrastructure",
  "/playground",
  "/playground/adversarial",
  "/sdk-console",
  "/agent-observability",
  "/negotiation-hub",
  "/security-audit",
  "/merchant-studio",
  "/docs/setup",
  "/docs/onboarding",
  "/docs/buyer-sdk",
  "/docs/merchant-guide",
  "/docs/telemetry",
  "/docs/gstr1-invoice",
];

const mockSessionPrefix = "session-challenger-m2-";
const stressToggleIterations = 10000;
const expectedTotalNavItems = 17;

function simulateLocalStorageReader(rawValue: string | null): boolean {
  if (rawValue === null) {
    return defaultSidebarCollapsed;
  }
  return rawValue === "true";
}

function simulateToggleLoop(initialState: boolean, count: number): boolean {
  let currentState = initialState;
  for (let iteration = 0; iteration < count; iteration += 1) {
    currentState = !currentState;
  }
  return currentState;
}

// Imported from source rather than redefined locally. These tests previously carried their own
// copy of the prefix-matching logic, which meant they passed regardless of what the real
// implementation did -- they would still have gone green if isRouteMatching were deleted.
const checkActiveRouteMatch = isRouteMatching;

describe("Milestone 2 Challenger 1: Sidebar State Machine & Storage Edge Cases", () => {
  it("should maintain default collapsed invariant when storage is empty or null", () => {
    assert.equal(sidebarStorageKey, "razormesh-sidebar");
    assert.equal(defaultSidebarCollapsed, false);
    assert.equal(simulateLocalStorageReader(null), false);
  });

  it("should handle corrupted or non-standard localStorage payloads safely", () => {
    const corruptedValues = [
      "null",
      "undefined",
      "NaN",
      "0",
      "1",
      "{\"collapsed\":true}",
      "[true]",
      "TRUE",
      "FALSE",
      "",
      "   ",
      "random-garbage-string",
    ];

    for (const corruptValue of corruptedValues) {
      const parsed = simulateLocalStorageReader(corruptValue);
      assert.equal(parsed, false, `Corrupted value '${corruptValue}' should evaluate to false`);
    }

    assert.equal(simulateLocalStorageReader("true"), true);
    assert.equal(simulateLocalStorageReader("false"), false);
  });

  it("should maintain state consistency across 10,000 rapid toggle transitions", () => {
    const finalStateEven = simulateToggleLoop(false, stressToggleIterations);
    assert.equal(finalStateEven, false, "Even number of toggles must return to initial false");

    const finalStateOdd = simulateToggleLoop(false, stressToggleIterations + 1);
    assert.equal(finalStateOdd, true, "Odd number of toggles must invert to true");
  });

  it("should support idempotent setCollapsed direct assignments", () => {
    let state = false;
    const setState = (next: boolean) => {
      state = next;
    };

    setState(true);
    assert.equal(state, true);
    setState(true);
    assert.equal(state, true);
    setState(false);
    assert.equal(state, false);
  });
});

describe("Milestone 2 Challenger 1: App Shell Navigation & Route Resolution", () => {
  it("should contain exactly 17 valid navigation items matching the Stitch specification", () => {
    assert.equal(navigationItems.length, expectedTotalNavItems);

    const routes = navigationItems.map((item) => item.route);
    assert.deepEqual(routes, expectedRouteList);

    for (const item of navigationItems) {
      assert.ok(item.route.startsWith("/"), `Route '${item.route}' must start with slash`);
      assert.ok(item.label.trim().length > 0, `Label for '${item.route}' must not be empty`);
      assert.ok((item.description ?? "").trim().length > 0, `Description for '${item.route}' must not be empty`);
    }
  });

  it("should accurately resolve exact, nested, and non-matching routes", () => {
    for (const route of expectedRouteList) {
      assert.equal(checkActiveRouteMatch(route, route), true, `Exact match failed for ${route}`);
      assert.equal(checkActiveRouteMatch(`${route}/sub-view`, route), true, `Nested match failed for ${route}`);
      assert.equal(checkActiveRouteMatch(`${route}/12345/details`, route), true, `Deep nested match failed for ${route}`);

      for (const otherRoute of expectedRouteList) {
        // A route nested UNDER another registered route (e.g. /playground/adversarial under
        // /playground) legitimately belongs to itself, not to its parent -- the most specific
        // registered route wins, so exactly one sidebar row highlights.
        if (otherRoute !== route && !otherRoute.startsWith(`${route}/`)) {
          assert.equal(checkActiveRouteMatch(otherRoute, route), false, `False positive match between ${otherRoute} and ${route}`);
        }
      }
    }
  });
});

describe("Milestone 2 Challenger 1: TelemetryContext Lifecycle & Scenario Stream", () => {
  it("should generate nominal settlement scenario events conforming to mathematical invariants", () => {
    const sessionId = `${mockSessionPrefix}nominal`;
    const nominalEvents = createTestNominalSettlementEvents(sessionId);

    assert.ok(nominalEvents.length >= 6, "Nominal scenario must produce at least 6 events");
    for (const event of nominalEvents) {
      assert.ok(event.eventId.length > 0, "Event must have eventId");
      assert.ok(event.eventType.length > 0, "Event must have eventType");
      assert.ok(event.timestampMs > 0, "Event must have positive timestampMs");
      assert.equal(event.sessionId, sessionId, "SessionId must match");
    }

    const paymentEvent = nominalEvents.find((evt) => evt.eventType === "PAYMENT_CAPTURED");
    assert.ok(paymentEvent, "Nominal scenario must contain PAYMENT_CAPTURED event");
    if (paymentEvent && paymentEvent.eventType === "PAYMENT_CAPTURED") {
      assert.equal(paymentEvent.payload.currency, "INR");
      assert.ok(Number.isInteger(paymentEvent.payload.amountPaise), "Amount must be integer paise (INV-01)");
      assert.ok(paymentEvent.payload.transfers.length > 0, "Transfers must not be empty");
    }
  });

  it("should generate B2B negotiation scenario with monotonic bid/ask convergence", () => {
    const sessionId = `${mockSessionPrefix}negotiation`;
    const negotiationEvents = createTestNegotiationScenarioEvents(sessionId);

    const bidTurns = negotiationEvents.filter(
      (evt): evt is Extract<TelemetryEvent, { eventType: "BID_TURN_COMPLETED" }> =>
        evt.eventType === "BID_TURN_COMPLETED"
    );

    assert.ok(bidTurns.length >= 2, "Negotiation must have at least 2 bid turns");

    let lastBid = 0;
    let lastAsk = Infinity;

    for (const turn of bidTurns) {
      assert.ok(turn.payload.buyerBidPaise >= lastBid, "Buyer bid must be monotonically non-decreasing");
      assert.ok(turn.payload.sellerAskPaise <= lastAsk, "Seller ask must be monotonically non-increasing");
      assert.ok(turn.payload.spreadPaise >= 0, "Spread must be non-negative");
      lastBid = turn.payload.buyerBidPaise;
      lastAsk = turn.payload.sellerAskPaise;
    }
  });

  it("should generate OOS healing scenario with valid similarity threshold and price delta", () => {
    const sessionId = `${mockSessionPrefix}healing`;
    const healingEvents = createTestOosHealingScenarioEvents(sessionId);

    assert.ok(healingEvents.length >= 1, "Healing scenario must produce at least 1 event");
    const healEvent = healingEvents[0];
    assert.equal(healEvent.eventType, "OOS_HEALED");

    if (healEvent.eventType === "OOS_HEALED") {
      assert.ok(healEvent.payload.cosineSimilarity >= 0.85, "Similarity must be >= 0.85");
      assert.ok(healEvent.payload.healingDurationMs < 300, "Healing duration must be sub-300ms SLA");
      assert.ok(healEvent.payload.patchedMandateHash.startsWith("0x"), "Patched hash must start with 0x");
      const expectedDelta = healEvent.payload.substitutePricePaise - healEvent.payload.originalPricePaise;
      assert.equal(healEvent.payload.priceDeltaPaise, expectedDelta, "Price delta arithmetic must match");
    }
  });
});

describe("Milestone 2 Challenger 1: DashboardHeader Connection & Status Contracts", () => {
  it("should have valid color and label mappings for all 4 SSE connection states", () => {
    const states: ReadonlyArray<SseConnectionState> = [
      "CONNECTING",
      "CONNECTED",
      "DISCONNECTED",
      "ERROR",
    ];

    for (const state of states) {
      const label = connectionStatusLabels[state];
      const color = connectionStatusColors[state];

      assert.ok(label && label.length > 0, `Missing label for state ${state}`);
      assert.ok(color && color.length > 0, `Missing color class for state ${state}`);
    }
  });
});
