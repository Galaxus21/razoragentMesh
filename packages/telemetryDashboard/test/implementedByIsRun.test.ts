// `implementedBy` on the protocol map is a claim about the RUNNING system, not about the
// repository's file listing.
//
// The existing check in protocolLayerMap.test.ts asserts each entry starts with "packages/".
// That passed for `implementedBy: ["packages/vectorHealer"]` throughout the period when nothing
// outside the healer's own tests ever constructed `OosInterceptor`, and when no Dockerfile
// copied the package into an image -- so /protocol named a Layer 3 that was not present in the
// mesh at all, and a string-shape assertion had no way to notice.
//
// So two things are checked here that a shape assertion cannot reach: the cited path exists on
// disk, and something OUTSIDE that package's own directory and outside the test suites imports
// from it. The second is the one with teeth: a package nothing imports is a library, whatever
// the diagram says.

import assert from "node:assert/strict";
import test from "node:test";
import fs from "node:fs";
import path from "node:path";
import { protocolLayerNodes } from "@/constants/protocolLayerMap";

function resolveRepositoryRoot(): string {
  // Tests run from the dashboard package root, two levels below the repository root -- the
  // same assumption sdkEndpointParity.ts and generateExampleSnippets.ts make.
  return path.resolve(process.cwd(), "..", "..");
}

const sourceExtensions = new Set([".py", ".ts", ".tsx"]);
const skippedDirectories = new Set([
  "node_modules", "dist", "build", ".next", "__pycache__", ".git", "generated"
]);
// A package imported only by tests is exercised, not deployed. The distinction is the entire
// point of the check, so test trees are excluded from what counts as a caller.
const testPathMarkers = ["/test/", "/tests/", ".test.", "_test.", "/testFixtures/"];

function collectSourceFiles(directory: string, found: string[] = []): string[] {
  for (const entry of fs.readdirSync(directory, { withFileTypes: true })) {
    if (entry.name.startsWith(".") && entry.name !== ".env.example") {
      continue;
    }
    const fullPath = path.join(directory, entry.name);
    if (entry.isDirectory()) {
      if (!skippedDirectories.has(entry.name)) {
        collectSourceFiles(fullPath, found);
      }
    } else if (sourceExtensions.has(path.extname(entry.name))) {
      found.push(fullPath);
    }
  }
  return found;
}

// "packages/vectorHealer/src/x.py" -> "vectorHealer"; also handles a bare package directory.
function packageNameOf(citedPath: string): string {
  return citedPath.split("/")[1] ?? citedPath;
}

// An IMPORT, not a mention. protocolLayerMap.ts contains the literal "packages/vectorHealer"
// in the very `implementedBy` entry under test, so a substring search lets the claim satisfy
// itself -- the map would prove its own truth and this check would pass on an unused package,
// which is the exact failure it exists to catch. Only a line that actually pulls the package in
// counts, so the reference has to sit on an import statement.
function importsPackage(source: string, packageName: string): boolean {
  const dotted = `packages.${packageName}`;
  const slashed = `packages/${packageName}`;
  for (const line of source.split("\n")) {
    if (!line.includes(dotted) && !line.includes(slashed)) {
      continue;
    }
    const trimmed = line.trim();
    const isPythonImport = /^(from|import)\s/.test(trimmed);
    const isTypeScriptImport =
      /^(import|export)\s/.test(trimmed) || /(require|import)\s*\(/.test(trimmed);
    if (isPythonImport || isTypeScriptImport) {
      return true;
    }
  }
  return false;
}

function isProductionFile(relativePath: string): boolean {
  const normalized = `/${relativePath.split(path.sep).join("/")}`;
  return !testPathMarkers.some((marker) => normalized.includes(marker));
}

// A package can also be running because it IS a service. x402Gateway and telemetryDashboard are
// entrypoints -- uvicorn and Next.js start them, and nothing imports an entrypoint -- so an
// import-only rule would report them as unused, which is false and would train a reader to
// ignore this check. Being built by compose is the evidence that they run.
//
// Both halves matter: `packages/vectorHealer` satisfied NEITHER. Nothing imported it and no
// Dockerfile copied it into any image, which is why /protocol could name a Layer 3 that was
// absent from the running mesh.
function isDeployedService(packageName: string): boolean {
  const dockerfilePath = path.join(repositoryRoot, "packages", packageName, "Dockerfile");
  if (!fs.existsSync(dockerfilePath)) {
    return false;
  }
  const compose = fs.readFileSync(path.join(repositoryRoot, "docker-compose.yml"), "utf-8");
  return (
    compose.includes(`packages/${packageName}/Dockerfile`) ||
    compose.includes(`context: ./packages/${packageName}`)
  );
}

const repositoryRoot = resolveRepositoryRoot();
const allSourceFiles = collectSourceFiles(path.join(repositoryRoot, "packages"))
  .concat(collectSourceFiles(path.join(repositoryRoot, "scripts")));

test("every implementedBy path exists on disk", () => {
  for (const layer of protocolLayerNodes) {
    for (const citedPath of layer.implementedBy) {
      const absolutePath = path.join(repositoryRoot, citedPath);
      assert.ok(
        fs.existsSync(absolutePath),
        `${layer.layerId} cites ${citedPath}, which does not exist`
      );
    }
  }
});

test("every implementedBy package is either imported by production code or deployed", () => {
  const unreferenced: string[] = [];

  for (const layer of protocolLayerNodes) {
    for (const citedPath of layer.implementedBy) {
      const packageName = packageNameOf(citedPath);
      if (isDeployedService(packageName)) {
        continue;
      }
      const ownDirectory = path.join(repositoryRoot, "packages", packageName) + path.sep;

      const hasProductionCaller = allSourceFiles.some((filePath) => {
        if (filePath.startsWith(ownDirectory)) {
          return false;
        }
        const relativePath = path.relative(repositoryRoot, filePath);
        if (!isProductionFile(relativePath)) {
          return false;
        }
        const source = fs.readFileSync(filePath, "utf-8");
        return importsPackage(source, packageName);
      });

      if (!hasProductionCaller) {
        unreferenced.push(`${layer.layerId} cites ${citedPath}`);
      }
    }
  }

  assert.deepEqual(
    unreferenced,
    [],
    "these layers name a package that nothing deploys and no production file outside it " +
      "imports, so the protocol map claims a component the running mesh does not use:\n  " +
      unreferenced.join("\n  ")
  );
});
