// Guards the failure that shipped once already: `defaultX402GatewayUrl` pointed at 4002
// (the merchant API) while the gateway listens on 4003, so every negotiation call from the
// TypeScript SDK reached the wrong service. Ports live in three places -- docker-compose.yml,
// sdkConstants.ts, and the Python MeshSlaConfig -- so assert all three agree.

import assert from "node:assert/strict";
import test from "node:test";
import fs from "node:fs";
import path from "node:path";
import { fileURLToPath } from "node:url";
import {
  defaultMandateEngineUrl,
  defaultMcpServerUrl,
  defaultX402GatewayUrl
} from "../src/sdkConstants.js";

const testDir = path.dirname(fileURLToPath(import.meta.url));
const repoRoot = path.resolve(testDir, "..", "..", "..");
const composePath = path.join(repoRoot, "docker-compose.yml");
const pythonConfigPath = path.join(
  repoRoot, "packages", "buyerSdkPy", "razoragent_buyer_sdk", "transportModels.py"
);

const expectedServicePorts: ReadonlyArray<readonly [string, number]> = [
  ["mandate-engine", 8000],
  ["mcp-server", 4001],
  ["merchant-api", 4002],
  ["x402-gateway", 4003]
];

function readFileLines(filePath: string): readonly string[] {
  return fs.readFileSync(filePath, "utf-8").split("\n").map((line) => line.trimEnd());
}

// Reads the host side of the first `- "host:container"` mapping under a compose service.
function readComposePublishedPort(composeLines: readonly string[], serviceName: string): number {
  const serviceHeader = `  ${serviceName}:`;
  const startIndex = composeLines.indexOf(serviceHeader);
  assert.notEqual(startIndex, -1, `service '${serviceName}' not found in docker-compose.yml`);

  for (let index = startIndex + 1; index < composeLines.length; index += 1) {
    const line = composeLines[index] ?? "";
    const isNextServiceHeader = line.startsWith("  ") && !line.startsWith("   ") && line.endsWith(":");
    if (isNextServiceHeader) {
      break;
    }
    const trimmed = line.trim();
    if (trimmed.startsWith('- "') && trimmed.includes(":")) {
      const mapping = trimmed.slice(3, trimmed.lastIndexOf('"'));
      return Number(mapping.split(":")[0]);
    }
  }
  throw new Error(`no published port found for service '${serviceName}'`);
}

function portOf(url: string): number {
  return Number(new URL(url).port);
}

test("docker-compose publishes the ports the SDKs default to", () => {
  const composeLines = readFileLines(composePath);
  for (const [serviceName, expectedPort] of expectedServicePorts) {
    assert.equal(
      readComposePublishedPort(composeLines, serviceName),
      expectedPort,
      `compose port drifted for '${serviceName}'`
    );
  }
});

test("TypeScript SDK default URLs match the compose port map", () => {
  assert.equal(portOf(defaultMandateEngineUrl), 8000);
  assert.equal(portOf(defaultMcpServerUrl), 4001);
  assert.equal(
    portOf(defaultX402GatewayUrl),
    4003,
    "gateway must be 4003, not the merchant API's 4002"
  );
});

test("Python SDK default URLs match the TypeScript SDK", () => {
  const pythonLines = readFileLines(pythonConfigPath).map((line) => line.trim());
  const expectedPythonPorts: ReadonlyArray<readonly [string, number]> = [
    ["gatewayBaseUrl", 8000],
    ["mcpBaseUrl", 4001],
    ["merchantApiBaseUrl", 4002],
    ["x402GatewayBaseUrl", 4003]
  ];

  for (const [fieldName, expectedPort] of expectedPythonPorts) {
    const declaration = pythonLines.find(
      (line) => line.startsWith(`${fieldName}:`) && line.includes("Field(default=")
    );
    assert.ok(declaration, `MeshSlaConfig field '${fieldName}' not found`);
    const quotedDefault = declaration.split('"')[1];
    assert.ok(quotedDefault, `MeshSlaConfig field '${fieldName}' has no quoted default`);
    assert.equal(portOf(quotedDefault), expectedPort, `Python '${fieldName}' port drifted`);
  }
});
