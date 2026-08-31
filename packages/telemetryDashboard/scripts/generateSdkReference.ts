// Writes generated/typeScriptSdkReference.json and generated/mcpToolReference.json.
//
// Companion to scripts/generateApiReference.py, which covers the Python half. Together the four
// artifacts are the symbol tables scripts/verifyDocSnippets.ts resolves the guides against.
//
// These are committed rather than produced during `next build`: the docs are statically
// generated inside a container that has no access to the sibling packages' sources, and a
// checked-in artifact is also a reviewable diff -- a pull request that changes the SDK surface
// shows the change to the surface, not just to the implementation.
//
// Regenerate with: npm run docs:reference

import fs from "node:fs";
import path from "node:path";
import { fileURLToPath } from "node:url";
import { extractPackageSurface } from "../src/lib/reference/typeScriptSurface.js";
import type {
  McpToolReference,
  McpToolSchema,
  PackageSurface,
} from "../src/types/referenceTypes.js";

const currentDirectory = path.dirname(fileURLToPath(import.meta.url));
const packageRoot = path.resolve(currentDirectory, "..");
const monorepoPackages = path.resolve(packageRoot, "..");
const outputDirectory = path.join(packageRoot, "generated");
const bytesPerKilobyte = 1024;

const typeScriptSdkFileName = "typeScriptSdkReference.json";
const mcpToolFileName = "mcpToolReference.json";
const typeScriptSdkPackageName = "@razorpay/agent-buyer-sdk";
const mcpSchemaPackageName = "razoragent-mesh-mcp-server";
const requestSuffix = "Request";
const responseSuffix = "Response";

const typeScriptSdkEntryPoint = path.join(monorepoPackages, "buyerSdkTs", "src", "index.ts");
const mcpSchemaEntryPoint = path.join(
  monorepoPackages,
  "mcpServer",
  "src",
  "schemas",
  "index.ts"
);

function writeArtifact(fileName: string, payload: unknown, summary: string): void {
  const contents = `${JSON.stringify(payload, null, 2)}
`;
  fs.mkdirSync(outputDirectory, { recursive: true });
  fs.writeFileSync(path.join(outputDirectory, fileName), contents, "utf-8");

  const sizeKilobytes = (Buffer.byteLength(contents, "utf-8") / bytesPerKilobyte).toFixed(1);
  process.stdout.write(`Wrote generated/${fileName}: ${summary} (${sizeKilobytes} kB)
`);
}

function buildSurface(entryPoint: string, packageName: string): PackageSurface {
  const surface = extractPackageSurface(entryPoint, packageName);
  if (surface.exports.length === 0) {
    throw new Error(`${entryPoint} exports nothing -- refusing to write an empty surface`);
  }
  return surface;
}

// The zod schema objects themselves are zod's API, not the mesh's: recording parse/safeParse/
// optional on each one says nothing a guide could get wrong. The z.infer aliases beside them are
// the part that matters, because they carry the field names a request body has to use.
function collectToolSchemas(surface: PackageSurface): readonly McpToolSchema[] {
  const fieldsByAlias = new Map<string, readonly string[]>(
    surface.exports
      .filter((symbol) => symbol.kind === "type")
      .map((symbol) => [symbol.name, symbol.members.map((member) => member.name)])
  );

  const schemas: McpToolSchema[] = [];
  for (const [alias, requestFields] of fieldsByAlias) {
    if (!alias.endsWith(requestSuffix)) {
      continue;
    }
    const schemaName = alias.slice(0, -requestSuffix.length);
    const responseFields = fieldsByAlias.get(`${schemaName}${responseSuffix}`);
    if (!responseFields) {
      throw new Error(`${alias} has no matching ${schemaName}${responseSuffix} type`);
    }
    schemas.push({ schemaName, requestFields, responseFields });
  }

  if (schemas.length === 0) {
    throw new Error(`${surface.entryPoint} declares no request/response schema pairs`);
  }
  return schemas.sort((left, right) => left.schemaName.localeCompare(right.schemaName));
}

function main(): void {
  const sdkSurface = buildSurface(typeScriptSdkEntryPoint, typeScriptSdkPackageName);
  writeArtifact(typeScriptSdkFileName, sdkSurface, `${sdkSurface.exports.length} exports`);

  const schemaSurface = buildSurface(mcpSchemaEntryPoint, mcpSchemaPackageName);
  const toolReference: McpToolReference = {
    entryPoint: schemaSurface.entryPoint,
    schemas: collectToolSchemas(schemaSurface),
  };
  writeArtifact(mcpToolFileName, toolReference, `${toolReference.schemas.length} schema pairs`);
}

main();
