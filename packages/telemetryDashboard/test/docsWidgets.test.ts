import { describe, it } from "node:test";
import assert from "node:assert/strict";
import fs from "node:fs";
import path from "node:path";

import { ApiEndpoint } from "../src/components/docs/apiEndpoint.js";
import { RunStep } from "../src/components/docs/runStep.js";
import { mdxComponents } from "../src/components/docs/mdxComponents.js";
import { buildDocSourceUrl, docsRepositoryUrl } from "../src/constants/docsSourceConfig.js";
import { defaultEventStyleMap } from "../src/constants/dashboardConstants.js";
import { meshServiceRegistry, meshServicesById } from "../src/constants/meshServiceRegistry.js";
import { describeScenarioSteps } from "../src/server/protocolDriver/runScenario.js";
import { loadAllDocPages, resolveDocsDirectory } from "../src/lib/docsLoader.js";

// Prose can now embed live components. The value of that is entirely conditional on the
// component arguments being real: <ApiEndpoint service="mcp-server"> renders a plausible-looking
// box for a service that does not exist under that id. These tests resolve every embedded
// reference against the registry it claims to come from.

const componentUsagePattern = /<([A-Z][A-Za-z0-9]*)\b([^>]*)\/?>/g;

function readAttribute(attributes: string, name: string): string | null {
  const match = new RegExp(`${name}="([^"]*)"`).exec(attributes);
  return match ? match[1] : null;
}

interface ComponentUsage {
  readonly slug: string;
  readonly componentName: string;
  readonly attributes: string;
}

function collectComponentUsages(): readonly ComponentUsage[] {
  const docsDirectory = resolveDocsDirectory();
  const usages: ComponentUsage[] = [];

  for (const page of loadAllDocPages()) {
    const raw = fs.readFileSync(path.join(docsDirectory, `${page.slug}.mdx`), "utf-8");
    // Code is skipped, matching what MDX itself does: a fenced sample may legitimately show
    // JSX, and an inline span like `BaseTelemetryEvent<TType, TPayload>` is a type signature
    // being quoted, not a component being rendered.
    const withoutCode = raw.replace(/```[\s\S]*?```/g, "").replace(/`[^`\n]*`/g, "");
    for (const match of withoutCode.matchAll(componentUsagePattern)) {
      usages.push({ slug: page.slug, componentName: match[1], attributes: match[2] });
    }
  }
  return usages;
}

describe("Components embedded in prose resolve to real things", () => {
  it("registers every component the guides actually use", () => {
    const registered = new Set(Object.keys(mdxComponents));
    const usages = collectComponentUsages();
    assert.ok(usages.length > 0, "No embedded components found -- the guides use none");

    for (const usage of usages) {
      assert.ok(
        registered.has(usage.componentName),
        `${usage.slug}.mdx uses <${usage.componentName}>, which mdxComponents does not register`
      );
    }
  });

  it("names a registered mesh service in every <ApiEndpoint>", () => {
    const endpoints = collectComponentUsages().filter((u) => u.componentName === "ApiEndpoint");
    assert.ok(endpoints.length > 0);

    for (const usage of endpoints) {
      const service = readAttribute(usage.attributes, "service");
      assert.ok(service, `${usage.slug}.mdx has an <ApiEndpoint> with no service`);
      assert.ok(
        meshServicesById[service],
        `${usage.slug}.mdx names service '${service}', which is not in meshServiceRegistry`
      );
      assert.ok(readAttribute(usage.attributes, "path"), `${usage.slug}.mdx: missing path`);
    }
  });

  it("names a real scenario and a real step in every <RunStep>", () => {
    const runSteps = collectComponentUsages().filter((u) => u.componentName === "RunStep");
    assert.ok(runSteps.length > 0);

    for (const usage of runSteps) {
      const scenario = readAttribute(usage.attributes, "scenario") ?? "";
      const step = readAttribute(usage.attributes, "step") ?? "";
      const definitions = describeScenarioSteps(scenario);
      assert.ok(definitions.length > 0, `${usage.slug}.mdx names unknown scenario '${scenario}'`);
      assert.ok(
        definitions.some((definition) => definition.stepId === step),
        `${usage.slug}.mdx names step '${step}', which '${scenario}' does not run`
      );
    }
  });
});

describe("Embedded components fail loudly rather than rendering a blank", () => {
  it("throws on an unknown service id", () => {
    // Doc pages are statically generated, so this throw fails `next build` -- the typo cannot
    // reach a reader as an empty box.
    assert.throws(
      () => ApiEndpoint({ service: "mcp-server", path: "/health" }),
      /names no service in meshServiceRegistry/
    );
  });

  it("renders for every registered service", () => {
    for (const service of meshServiceRegistry) {
      assert.ok(ApiEndpoint({ service: service.serviceId, path: service.healthPath }));
    }
  });

  it("throws on an unknown scenario or a step that scenario does not run", () => {
    assert.throws(
      () => RunStep({ scenario: "noSuchScenario", step: "settle" }),
      /names no scenario in the driver catalog/
    );
    // 'settle' is a real step, but the tampered-mandate run is refused before settlement.
    assert.throws(
      () => RunStep({ scenario: "tamperedMandate", step: "settle" }),
      /is not a step of 'tamperedMandate'/
    );
  });
});

describe("EventCatalog is derived from the event union", () => {
  it("covers every telemetry event type", () => {
    // defaultEventStyleMap is typed Record<TelemetryEventType, EventMetaStyle>, so a new
    // member of the union will not compile until the map gains an entry -- which is what makes
    // the rendered catalog exhaustive rather than a list someone remembered to update.
    const eventTypes = Object.keys(defaultEventStyleMap);
    assert.ok(eventTypes.length > 0);
    assert.equal(new Set(eventTypes).size, eventTypes.length);
  });

  it("no longer hard-codes the event count in prose", () => {
    // The guide opened with "The 12 Canonical Event Schema Specifications", a number nothing
    // could keep true. If it comes back, this fails.
    const telemetryGuide = loadAllDocPages().find((page) => page.slug === "telemetry");
    assert.ok(telemetryGuide);
    assert.ok(
      !/##\s*3\.\s*The \d+ Canonical/.test(telemetryGuide.body),
      "The hand-counted event total is back in the telemetry guide heading"
    );
    assert.ok(telemetryGuide.body.includes("<EventCatalog />"));
  });
});

describe("Edit-this-page links point at the real source file", () => {
  it("builds a GitHub blob URL from the document's own source path", () => {
    const url = buildDocSourceUrl("packages/telemetryDashboard/docs/setup.mdx");
    assert.ok(url.startsWith(`${docsRepositoryUrl}/blob/`));
    assert.ok(url.endsWith("/packages/telemetryDashboard/docs/setup.mdx"));
  });

  it("produces a distinct, well-formed link for every shipped guide", () => {
    const urls = loadAllDocPages().map((page) => buildDocSourceUrl(page.sourcePath));
    assert.equal(new Set(urls).size, urls.length);
    for (const url of urls) {
      assert.ok(/^https:\/\/github\.com\/[^/]+\/[^/]+\/blob\/.+\.mdx$/.test(url), url);
    }
  });
});

describe("Documented health probes match the service registry", () => {
  it("does not tell a reader to curl a health path the service does not serve", () => {
    // setup.mdx documented `curl localhost:4003/health`, which returns 404: the x402 gateway
    // namespaces its probe under /api/v1/mesh/. Nothing connected the guide to the registry
    // that already recorded the real path.
    const docsDirectory = resolveDocsDirectory();
    for (const page of loadAllDocPages()) {
      const raw = fs.readFileSync(path.join(docsDirectory, `${page.slug}.mdx`), "utf-8");
      for (const service of meshServiceRegistry) {
        for (const wrongPath of ["/health", "/api/v1/mesh/health"]) {
          if (wrongPath === service.healthPath) {
            continue;
          }
          assert.ok(
            !raw.includes(`localhost:${service.composePort}${wrongPath}`),
            `${page.slug}.mdx documents localhost:${service.composePort}${wrongPath}, but ` +
              `${service.displayName} serves its probe at ${service.healthPath}`
          );
        }
      }
    }
  });
});
