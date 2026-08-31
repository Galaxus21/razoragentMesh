import { describe, it } from "node:test";
import assert from "node:assert/strict";

import {
  collectEndpointCallers,
  collectServedRoutes,
  findUnservedCallers,
} from "../src/lib/reference/sdkEndpointParity.js";

// Both SDKs pass their own suites while calling routes that may not exist, because both suites mock
// the transport -- and a mock answers whatever it is asked. This compares callers to servers
// directly, and it is the only check in the repo that does.
//
// It was written with two known-broken Python routes on an allowlist: `/api/v1/quotes/live` and
// `/api/v1/inventory/lock`, neither of which any service served. Both are fixed, the allowlist is
// gone, and the assertion below is now unconditional -- which is the state it was always meant to
// reach. `test_razorAgentClient.py` had been asserting the wrong path as though it were the
// contract, so nothing else could have caught this.

describe("Every route the buyer SDKs call is served by something", () => {
  it("reads real routes from both servers, so a passing run is not an empty run", () => {
    const served = collectServedRoutes();
    // The MCP server's own constants plus three FastAPI surfaces. If the readers silently broke,
    // this set would collapse and every caller below would trivially "pass" against nothing.
    assert.ok(served.has("/api/v1/quote"), "MCP server routes were not read");
    assert.ok(served.has("/api/v1/settlement/execute"), "FastAPI routes were not read");
    assert.ok(served.size > 15, `only ${served.size} served routes found`);
  });

  it("reads endpoint constants from both SDKs", () => {
    const callers = collectEndpointCallers();
    for (const sdk of ["buyerSdkTs", "buyerSdkPy"]) {
      assert.ok(
        callers.some((caller) => caller.sdk === sdk),
        `no endpoint constants read from ${sdk}`
      );
    }
    assert.ok(callers.length >= 10, `only ${callers.length} endpoint constants found`);
  });

  it("leaves no endpoint constant pointing at a route nothing serves", () => {
    assert.deepEqual(
      findUnservedCallers().map((caller) => `${caller.sdk} ${caller.constantName} -> ${caller.route}`),
      []
    );
  });

  it("has both SDKs agreeing on the MCP routes they share", () => {
    // The divergence that started this: TypeScript reached all four MCP routes while Python reached
    // none of them. Asserting the agreement directly means a future rename has to move both.
    const served = collectServedRoutes();
    for (const caller of collectEndpointCallers()) {
      assert.ok(
        served.has(caller.route) ||
          [...served].some((route) => route.startsWith(`${caller.route}/`)),
        `${caller.sdk} ${caller.constantName} -> ${caller.route}`
      );
    }
  });
});
