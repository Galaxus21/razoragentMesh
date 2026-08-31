// Loads the committed reference artifacts and answers questions about them.
//
// Read from disk rather than imported as modules: these tables exist for a Node-side checker and
// a Node-side test, and importing 130 kB of JSON into src/ risks a client component pulling it
// into the browser bundle by accident.

import fs from "node:fs";
import path from "node:path";
import type { ExampleSource } from "@/lib/reference/exampleRegions";
import type {
  ExportedSymbol,
  HttpApiReference,
  McpToolReference,
  PackageSurface,
} from "@/types/referenceTypes";

export const generatedDirectoryName = "generated";
export const typeScriptSdkFileName = "typeScriptSdkReference.json";
export const pythonSdkFileName = "pythonSdkReference.json";
export const httpApiFileName = "httpApiReference.json";
export const mcpToolFileName = "mcpToolReference.json";
export const exampleSnippetsFileName = "exampleSnippets.json";

// Python's surface records members inherited from outside the SDK once, keyed by base class,
// instead of repeating them on all fifty models.
interface PythonPackageSurface extends PackageSurface {
  readonly inheritedMembers: Readonly<Record<string, readonly { name: string }[]>>;
}

export function resolveGeneratedDirectory(): string {
  return path.resolve(process.cwd(), generatedDirectoryName);
}

function readArtifact<TArtifact>(fileName: string): TArtifact {
  const artifactPath = path.join(resolveGeneratedDirectory(), fileName);
  if (!fs.existsSync(artifactPath)) {
    throw new Error(
      `${fileName} is missing. Regenerate the artifacts with: npm run docs:generate, and ` +
        `python scripts/generateApiReference.py for the FastAPI surfaces`
    );
  }
  return JSON.parse(fs.readFileSync(artifactPath, "utf-8")) as TArtifact;
}

export function loadTypeScriptSdkSurface(): PackageSurface {
  return readArtifact<PackageSurface>(typeScriptSdkFileName);
}

export function loadPythonSdkSurface(): PythonPackageSurface {
  return readArtifact<PythonPackageSurface>(pythonSdkFileName);
}

export function loadHttpApiReference(): HttpApiReference {
  return readArtifact<HttpApiReference>(httpApiFileName);
}

export function loadMcpToolReference(): McpToolReference {
  return readArtifact<McpToolReference>(mcpToolFileName);
}

export function loadExampleSources(): readonly ExampleSource[] {
  return readArtifact<readonly ExampleSource[]>(exampleSnippetsFileName);
}

// One question asked of both languages: does this class expose this name? The Python side has to
// fold in the inherited table first, which is the only place the two surfaces differ.
export interface SymbolTable {
  readonly packageName: string;
  readonly exports: ReadonlyMap<string, ExportedSymbol>;
  readonly memberNames: ReadonlyMap<string, ReadonlySet<string>>;
}

function buildTable(
  surface: PackageSurface,
  resolveMembers: (symbol: ExportedSymbol) => readonly string[]
): SymbolTable {
  return {
    packageName: surface.packageName,
    exports: new Map(surface.exports.map((symbol) => [symbol.name, symbol])),
    memberNames: new Map(
      surface.exports.map((symbol) => [symbol.name, new Set(resolveMembers(symbol))])
    ),
  };
}

export function buildTypeScriptSymbolTable(): SymbolTable {
  return buildTable(loadTypeScriptSdkSurface(), (symbol) =>
    symbol.members.map((member) => member.name)
  );
}

export function buildPythonSymbolTable(): SymbolTable {
  const surface = loadPythonSdkSurface();
  return buildTable(surface, (symbol) => [
    ...symbol.members.map((member) => member.name),
    ...((symbol as ExportedSymbol & { readonly inheritsFrom?: readonly string[] }).inheritsFrom ??
      []).flatMap((base) =>
      (surface.inheritedMembers[base] ?? []).map((member) => member.name)
    ),
  ]);
}
