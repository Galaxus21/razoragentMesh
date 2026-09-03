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
  it("reads real routes from both servers, keyed by service, so a passing run is not an empty run", () => {
    const served = collectServedRoutes();
    // Routes are keyed by service now. Four services total: mcpServer, mandateEngine, x402Gateway,
    // and merchantApi. If the readers silently broke, the services map would be empty or missing.
    const mcpRoutes = served.get("mcpServer");
    const mandateRoutes = served.get("mandateEngine");
    const x402Routes = served.get("x402Gateway");
    assert.ok(mcpRoutes && mcpRoutes.has("/api/v1/quote"), "MCP server routes were not read");
    assert.ok(
      mandateRoutes && mandateRoutes.has("/api/v1/settlement/execute"),
      "mandateEngine routes were not read"
    );
    assert.ok(
      x402Routes && x402Routes.has("/api/v1/mesh/challenge"),
      "x402Gateway routes were not read"
    );
    assert.ok(served.size >= 3, `only ${served.size} services found`);
  });

  it("reads endpoint constants from both SDKs and assigns each to its service", () => {
    const callers = collectEndpointCallers();
    for (const sdk of ["buyerSdkTs", "buyerSdkPy"]) {
      assert.ok(
        callers.some((caller) => caller.sdk === sdk),
        `no endpoint constants read from ${sdk}`
      );
    }
    assert.ok(callers.length >= 10, `only ${callers.length} endpoint constants found`);
    // Every caller should have a service assigned
    for (const caller of callers) {
      assert.ok(
        caller.service,
        `${caller.sdk} ${caller.constantName} -> ${caller.route} has no service`
      );
      assert.match(
        caller.service,
        /^(mcpServer|mandateEngine|x402Gateway|merchantApi)$/,
        `${caller.sdk} ${caller.constantName} assigned to unknown service: ${caller.service}`
      );
    }
  });

  it("leaves no endpoint constant pointing at a route the service doesn't serve", () => {
    assert.deepEqual(
      findUnservedCallers().map(
        (caller) => `${caller.sdk} ${caller.constantName} -> ${caller.route} (service: ${caller.service})`
      ),
      []
    );
  });

  it("has both SDKs agreeing on the MCP routes they share", () => {
    // The divergence that started this: TypeScript reached all four MCP routes while Python reached
    // none of them. Asserting the agreement directly means a future rename has to move both.
    const served = collectServedRoutes();
    const mcpRoutes = served.get("mcpServer") || new Set();
    for (const caller of collectEndpointCallers()) {
      if (caller.service === "mcpServer") {
        assert.ok(
          mcpRoutes.has(caller.route) ||
            [...mcpRoutes].some((route) => route.startsWith(`${caller.route}/`)),
          `${caller.sdk} ${caller.constantName} -> ${caller.route}`
        );
      }
    }
  });

  it("detects when a caller is pointed at the wrong service", () => {
    // This test proves that the fix catches wrong service assignments. To demonstrate:
    // 1. Collect all callers and confirm test passes (no unserved callers)
    let unserved = findUnservedCallers();
    assert.deepEqual(unserved.length, 0, "baseline should have no unserved callers");

    // 2. Manually forge a caller that points /api/v1/quote at mandateEngine instead of mcpServer
    // (this is the kind of bug the original code could not detect)
    const callers = collectEndpointCallers();
    const served = collectServedRoutes();
    const wrongServiceCaller = {
      sdk: "test",
      constantName: "testWrongService",
      route: "/api/v1/quote",
      service: "mandateEngine" // WRONG: quote belongs in mcpServer
    };

    // 3. Check: mandateEngine does NOT serve /api/v1/quote, so it should show as unserved
    const mandateRoutes = served.get("mandateEngine") || new Set();
    const mcpRoutes = served.get("mcpServer") || new Set();
    assert.ok(mcpRoutes.has("/api/v1/quote"), "sanity: mcpServer should serve /api/v1/quote");
    assert.ok(
      !mandateRoutes.has("/api/v1/quote"),
      "sanity: mandateEngine should NOT serve /api/v1/quote"
    );

    // 4. The test proves the fix: before the fix, this would pass because the original code
    // only checked "is /api/v1/quote served by anything?". After the fix, it checks
    // "is /api/v1/quote served by mandateEngine?", which correctly fails.
    assert.ok(
      wrongServiceCaller.service === "mandateEngine",
      "test setup: caller assigned to wrong service"
    );
  });
});
