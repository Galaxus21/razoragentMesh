import { describe, it } from "node:test";
import assert from "node:assert/strict";
import { readFileSync } from "node:fs";
import path from "node:path";
import { fileURLToPath } from "node:url";

import { protocolLayerNodes } from "../src/constants/protocolLayerMap.js";
import {
  meshServiceRegistry,
  meshServicesById,
} from "../src/constants/meshServiceRegistry.js";
import { navigationItems } from "../src/constants/sidebarNavigationConfig.js";
import { findScenarioSummary } from "../src/constants/scenarioCatalog.js";

const currentDirectory = path.dirname(fileURLToPath(import.meta.url));
const repositoryRoot = path.resolve(currentDirectory, "..", "..", "..");
const composeFilePath = path.join(repositoryRoot, "docker-compose.yml");
const merchantAppPath = path.join(
  repositoryRoot,
  "packages",
  "merchantApi",
  "src",
  "merchantApp.py"
);

// Reads the host ports from docker-compose without regex: any line inside a `ports:` block has
// the shape `- "HOST:CONTAINER"`, so splitting on the quote and the colon is enough and cannot
// be broken by an escape sequence elsewhere in the file.
function readComposeHostPorts(composeText: string): ReadonlySet<number> {
  const hostPorts = new Set<number>();
  for (const rawLine of composeText.split("\n")) {
    const line = rawLine.trim();
    if (!line.startsWith('- "') || !line.endsWith('"')) {
      continue;
    }
    const mapping = line.slice(3, -1);
    const [hostPart] = mapping.split(":");
    const parsed = Number(hostPart);
    if (Number.isInteger(parsed)) {
      hostPorts.add(parsed);
    }
  }
  return hostPorts;
}

describe("Mesh service registry", () => {
  it("registers each service once with a usable probe path", () => {
    const seenIds = new Set<string>();
    for (const service of meshServiceRegistry) {
      assert.ok(!seenIds.has(service.serviceId), `Duplicate service ${service.serviceId}`);
      seenIds.add(service.serviceId);
      assert.ok(service.healthPath.startsWith("/"), `${service.serviceId} probe path is relative`);
      assert.ok(service.displayName.length > 0);
      assert.ok(service.packagePath.startsWith("packages/"));
    }
  });

  it("matches the host ports docker-compose actually publishes", () => {
    // A registry port that drifts from compose sends every probe to a port nothing listens on,
    // and the map would then report a healthy mesh as entirely down.
    const hostPorts = readComposeHostPorts(readFileSync(composeFilePath, "utf8"));
    assert.ok(hostPorts.size > 0, "Parsed no ports from docker-compose.yml");
    for (const service of meshServiceRegistry) {
      assert.ok(
        hostPorts.has(service.composePort),
        `${service.serviceId} claims port ${service.composePort}, which compose does not publish`
      );
    }
  });

  it("keeps the merchant API health route the registry probes", () => {
    // This service had no probe at all until the protocol map needed one; a later refactor
    // that drops it would turn a green node red with no other signal.
    const merchantSource = readFileSync(merchantAppPath, "utf8");
    assert.ok(merchantSource.includes('endpointHealth: str = "/health"'));
    assert.ok(merchantSource.includes("_registerHealthRoute(app)"));
    assert.equal(meshServicesById.merchantApi.healthPath, "/health");
  });
});

describe("Protocol layer map", () => {
  it("numbers the layers 0..N with no gaps or duplicates", () => {
    const ordinals = protocolLayerNodes.map((layer) => layer.ordinal);
    // L0 is the ingress shield: the stack starts at zero, as the README diagram has always drawn it.
    const expected = protocolLayerNodes.map((_, index) => index);
    assert.deepEqual(ordinals, expected);
  });

  it("gives every layer responsibilities, events and an implementing package", () => {
    for (const layer of protocolLayerNodes) {
      assert.ok(layer.responsibilities.length > 0, `${layer.layerId} lists no responsibilities`);
      assert.ok(layer.eventsEmitted.length > 0, `${layer.layerId} emits no telemetry`);
      assert.ok(layer.implementedBy.length > 0, `${layer.layerId} names no package`);
      for (const packagePath of layer.implementedBy) {
        assert.ok(
          packagePath.startsWith("packages/"),
          `${layer.layerId} cites ${packagePath}, which is not a package path`
        );
      }
    }
  });

  it("only references services the registry can actually probe", () => {
    for (const layer of protocolLayerNodes) {
      for (const serviceId of layer.serviceIds) {
        assert.ok(
          meshServicesById[serviceId],
          `${layer.layerId} references unknown service ${serviceId}`
        );
      }
    }
  });

  it("only links to scenarios and routes that exist", () => {
    const registeredRoutes = new Set(navigationItems.map((item) => item.route));
    for (const layer of protocolLayerNodes) {
      assert.ok(
        findScenarioSummary(layer.scenarioId),
        `${layer.layerId} links to unknown scenario ${layer.scenarioId}`
      );
      assert.ok(
        registeredRoutes.has(layer.docRoute),
        `${layer.layerId} links to unregistered route ${layer.docRoute}`
      );
      assert.ok(layer.scenarioHint.length > 0, `${layer.layerId} has no scenario hint`);
    }
  });

  it("covers every registered mesh service somewhere in the stack", () => {
    // A service nobody claims is a service nobody can find from the map.
    const claimedServices = new Set(
      protocolLayerNodes.flatMap((layer) => layer.serviceIds as readonly string[])
    );
    for (const service of meshServiceRegistry) {
      assert.ok(
        claimedServices.has(service.serviceId),
        `${service.serviceId} is not shown on any layer`
      );
    }
  });
});
