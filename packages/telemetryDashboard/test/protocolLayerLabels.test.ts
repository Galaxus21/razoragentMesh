import { describe, it } from "node:test";
import assert from "node:assert/strict";
import fs from "node:fs";
import path from "node:path";

import { protocolLayerNodes } from "../src/constants/protocolLayerMap.js";

// The repository carried four layer numberings at once: README prose said four, its diagram drew
// six, PROJECT.md numbered by package, protocolLayerMap defined five, and the protocol driver
// called the mandate chain "Layer 2" where the map called it Layer 4. They are reconciled on the
// six-layer scheme now, and this is what stops them drifting apart again.
//
// Only `Layer <n>` labels written into source are checked. Prose in the guides is covered by the
// documentation checker instead, and generated files are excluded because they are derived.

const repositoryRoot = path.resolve(process.cwd(), "..", "..");
const layerLabelPattern = /Layer (\d+)/g;
const sourceExtensions = new Set([".ts", ".tsx", ".py"]);
const skippedDirectories = new Set([
  "node_modules",
  ".next",
  "dist",
  "__pycache__",
  "generated",
  "test",
  "tests",
  "docs",
]);

interface LayerLabel {
  readonly file: string;
  readonly line: number;
  readonly ordinal: number;
}

function collectLayerLabels(directory: string, found: LayerLabel[]): void {
  for (const entry of fs.readdirSync(directory, { withFileTypes: true })) {
    const entryPath = path.join(directory, entry.name);
    if (entry.isDirectory()) {
      if (!skippedDirectories.has(entry.name)) {
        collectLayerLabels(entryPath, found);
      }
      continue;
    }
    if (!sourceExtensions.has(path.extname(entry.name))) {
      continue;
    }
    const source = fs.readFileSync(entryPath, "utf-8");
    for (const match of source.matchAll(layerLabelPattern)) {
      found.push({
        file: path.relative(repositoryRoot, entryPath).split(path.sep).join("/"),
        line: source.slice(0, match.index).split("\n").length,
        ordinal: Number(match[1]),
      });
    }
  }
}

// Where a package sits in the stack, asserted against the map rather than against a literal, so
// renumbering the map is the only edit a renumbering needs.
const expectedLayerByPathPrefix: Readonly<Record<string, string>> = {
  "packages/catalogSanitizer": "ingress",
  "packages/x402Gateway/src/middleware/proofOfWorkMiddleware.py": "ingress",
  "packages/mcpServer": "discovery",
  "packages/merchantApi": "discovery",
  // Two files in the Merchant API belong to other layers, the same way the PoW middleware above
  // belongs to ingress rather than to the gateway package it lives in. Layer 3's search half
  // runs here because this is where the Qdrant client is, and Layer 0 is called from here
  // because this is where merchant text enters the mesh.
  "packages/merchantApi/src/routes/oosHealingRoute.py": "resilience",
  "packages/merchantApi/src/routes/healingTelemetry.py": "resilience",
  "packages/merchantApi/src/catalog/ingressSanitizer.py": "ingress",
  "packages/x402Gateway": "negotiation",
  "packages/vectorHealer": "resilience",
  "packages/mandateEngine": "settlement",
};

function expectedOrdinalFor(file: string): number | undefined {
  // Longest prefix wins, so the PoW middleware beats the x402Gateway package it lives in.
  const prefix = Object.keys(expectedLayerByPathPrefix)
    .filter((candidate) => file.startsWith(candidate))
    .sort((left, right) => right.length - left.length)[0];
  if (!prefix) {
    return undefined;
  }
  const layerId = expectedLayerByPathPrefix[prefix];
  const node = protocolLayerNodes.find((layer) => layer.layerId === layerId);
  assert.ok(node, `expectedLayerByPathPrefix names ${layerId}, which the map does not define`);
  return node.ordinal;
}

describe("Layer labels in source agree with the canonical map", () => {
  const labels: LayerLabel[] = [];
  collectLayerLabels(path.join(repositoryRoot, "packages"), labels);

  it("finds labels to check, so a passing run is not an empty run", () => {
    assert.ok(labels.length > 20, `only ${labels.length} layer labels found across packages/`);
  });

  it("numbers the canonical stack 0..5", () => {
    assert.deepEqual(
      protocolLayerNodes.map((layer) => layer.ordinal),
      [0, 1, 2, 3, 4, 5]
    );
  });

  it("never names a layer the map does not define", () => {
    const defined = new Set(protocolLayerNodes.map((layer) => layer.ordinal));
    const unknown = labels.filter((label) => !defined.has(label.ordinal));
    assert.deepEqual(
      unknown.map((label) => `${label.file}:${label.line} says Layer ${label.ordinal}`),
      []
    );
  });

  it("puts every package's own label on the layer that implements it", () => {
    const wrong = labels
      .map((label) => ({ label, expected: expectedOrdinalFor(label.file) }))
      .filter((entry) => entry.expected !== undefined && entry.label.ordinal !== entry.expected);
    assert.deepEqual(
      wrong.map(
        (entry) =>
          `${entry.label.file}:${entry.label.line} says Layer ${entry.label.ordinal}, ` +
          `expected Layer ${entry.expected}`
      ),
      []
    );
  });
});
