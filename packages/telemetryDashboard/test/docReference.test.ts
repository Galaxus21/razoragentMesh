import { describe, it } from "node:test";
import assert from "node:assert/strict";

import { defaultEventStyleMap } from "../src/constants/dashboardConstants.js";
import { meshServiceRegistry } from "../src/constants/meshServiceRegistry.js";
import { extractCodeFences } from "../src/lib/reference/docSnippetExtractor.js";
import {
  loadHttpApiReference,
  loadMcpToolReference,
} from "../src/lib/reference/referenceTables.js";
import { verifyDocSnippets } from "../src/lib/reference/docSnippetVerifier.js";
import { loadAllDocPages } from "../src/lib/docsLoader.js";

// The standing gate: every guide the site publishes resolves against the generated reference,
// and the generated reference describes the services the mesh actually runs. What the checker
// does on a given snippet is asserted in docSnippetChecker.test.ts.


describe("Every published guide resolves against the generated reference", () => {
  it("finds no unknown symbol, package, route or port in any guide", () => {
    assert.deepEqual(
      verifyDocSnippets().map(
        (finding) => `${finding.sourcePath}:${finding.line} ${finding.message}`
      ),
      []
    );
  });

  it("actually reads the fences, so a passing run is not an empty run", () => {
    // A checker that silently stopped extracting would also report zero findings.
    const fenceCount = loadAllDocPages().reduce(
      (total, page) => total + extractCodeFences(page).length,
      0
    );
    assert.ok(fenceCount > 20, `only ${fenceCount} checkable fences found across the guides`);
  });
});

describe("The generated reference describes the services the mesh actually runs", () => {
  it("records an OpenAPI surface for every service it names", () => {
    for (const service of loadHttpApiReference().services) {
      assert.ok(
        meshServiceRegistry.some((entry) => entry.serviceId === service.serviceId),
        `${service.serviceId} is in the reference but not in meshServiceRegistry`
      );
      assert.ok(service.operations.length > 0, `${service.serviceId} exposes no routes`);
    }
  });

  it("agrees with the dashboard about which telemetry events exist", () => {
    // The event types are published by a Python seeder and rendered by TypeScript. Nothing but
    // this comparison connects the two, so a type added on one side is otherwise invisible.
    const seeded = loadHttpApiReference().telemetryEventTypes;
    assert.ok(seeded.length > 0);
    for (const eventType of seeded) {
      assert.ok(
        eventType in defaultEventStyleMap,
        `${eventType} is published by the seeder but the dashboard has no style for it`
      );
    }
  });

  it("pairs a request and a response schema for every MCP tool", () => {
    const reference = loadMcpToolReference();
    assert.ok(reference.schemas.length > 0);
    for (const schema of reference.schemas) {
      assert.ok(schema.requestFields.length > 0, `${schema.schemaName} has no request fields`);
      assert.ok(schema.responseFields.length > 0, `${schema.schemaName} has no response fields`);
    }
  });
});
