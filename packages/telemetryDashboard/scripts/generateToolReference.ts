// Writes docs/tool-reference.mdx -- the MCP tool reference, generated from the manifest.
//
// The mesh's whole public surface for an autonomous buyer is ten MCP tools, and until now no page
// listed them. A developer pointing an agent at localhost:4001 had to read the guides for prose
// mentions of a tool, or call tools/list and read raw JSON Schema. Every API-docs site worth
// copying has one page that answers "what can I call, with what arguments, and what comes back".
//
// It is GENERATED from packages/mcpServer/src/constants/*Manifest.ts rather than written, because
// that manifest is the exact JSON Schema `tools/list` returns to an agent. A hand-written table
// beside it would be a second source of truth that silently drifts the first time a field gains a
// constraint -- and this project has already been bitten by a stale tool description outliving the
// guard it described. Editing the manifest is what changes this page.
//
// Regenerate with: npm run docs:tools

import fs from "node:fs";
import path from "node:path";
import { fileURLToPath, pathToFileURL } from "node:url";

const currentDirectory = path.dirname(fileURLToPath(import.meta.url));
const packageRoot = path.resolve(currentDirectory, "..");
const monorepoPackages = path.resolve(packageRoot, "..");
// Resolved at RUNTIME rather than imported.
//
// A static `import ... from "../../mcpServer/..."` compiles here and breaks the container
// build: the dashboard image is built from this package alone, and `next build` typechecks
// scripts/ along with everything else, so it fails on a module that is genuinely absent from
// the image. A computed specifier is not resolved by the compiler, which is the same reason
// generateSdkReference.ts reads its sibling entry points as paths instead of importing them.
const manifestEntryPoint = path.join(
  monorepoPackages,
  "mcpServer",
  "src",
  "constants",
  "toolsManifest.ts"
);
const outputPath = path.join(packageRoot, "docs", "tool-reference.mdx");
// A checked-in copy of just the fields the reference is built from.
//
// This script is the ONLY thing in the package allowed to reach into ../mcpServer: the
// dashboard image is built from this package alone, so `next build` typechecks a tree where
// that sibling does not exist, and an import of it from anywhere under test/ or src/ breaks
// the container build while passing locally. Same reason the SDK reference artifacts are
// checked in rather than derived at build time.
const manifestArtifactPath = path.join(packageRoot, "generated", "mcpToolManifest.json");

interface JsonSchemaProperty {
  readonly type?: string;
  readonly description?: string;
  readonly default?: unknown;
  readonly enum?: readonly unknown[];
  readonly minimum?: number;
  readonly maximum?: number;
  readonly minLength?: number;
  readonly maxLength?: number;
  readonly pattern?: string;
  readonly items?: { readonly type?: string };
}

interface ManifestTool {
  readonly name: string;
  readonly description: string;
  readonly inputSchema: {
    readonly type: string;
    readonly properties: Record<string, JsonSchemaProperty>;
    readonly required?: readonly string[];
  };
}

/**
 * Which layer each tool sits on, and the one-line job it does.
 *
 * The manifest deliberately carries no layer field -- an MCP client has no use for one, and
 * adding a docs-only key to the wire schema would put presentation into the protocol. So the
 * grouping lives here, and a tool missing from this map fails the build rather than being
 * silently dropped into an "Other" bucket where nobody would notice it went undocumented.
 */
const toolGroups: ReadonlyArray<{
  readonly layer: string;
  readonly heading: string;
  readonly intent: string;
  readonly tools: readonly string[];
}> = [
  {
    layer: "L1",
    heading: "Discovery",
    intent:
      "Find something to buy and get a price for it. Every quote is sealed with an HMAC hash that " +
      "a later stage must present, so a cart cannot be built from a price the mesh never issued.",
    tools: ["search_catalog", "browse_catalog", "get_live_sku_quote", "verify_shipping_sla"],
  },
  {
    layer: "L2",
    heading: "Negotiation",
    intent:
      "Bargain against the merchant's own policy. Each turn is metered by an x402-INR micro-escrow, " +
      "which is what stops a bidding loop from being free to run.",
    tools: ["negotiate_price"],
  },
  {
    layer: "L4",
    heading: "Settlement",
    intent:
      "Reserve stock, then build and sign the Google AP2 mandate chain -- Intent, Cart, Execution -- " +
      "and settle it. Every mandate is Ed25519 over RFC 8785 canonical JSON.",
    tools: [
      "reserve_inventory_lock",
      "establish_agent_delegation",
      "create_cart_mandate",
      "sign_execution_mandate",
      "execute_settlement",
    ],
  },
];

function formatType(property: JsonSchemaProperty): string {
  if (property.type === "array") {
    return property.items?.type ? `${property.items.type}[]` : "array";
  }
  return property.type ?? "any";
}

/**
 * The constraints an agent must satisfy, rendered as prose after the description.
 *
 * These matter more here than in most API docs: a live run watched an agent fail seven calls on
 * `pattern` and range constraints it could not see, so anything the schema will reject on has to
 * be visible on the page.
 */
function formatConstraints(property: JsonSchemaProperty): string {
  const parts: string[] = [];

  if (property.enum) {
    parts.push(`one of ${property.enum.map((value) => `\`${String(value)}\``).join(", ")}`);
  }
  if (property.minimum !== undefined || property.maximum !== undefined) {
    if (property.minimum !== undefined && property.maximum !== undefined) {
      parts.push(`${property.minimum}–${property.maximum}`);
    } else if (property.minimum !== undefined) {
      parts.push(`min ${property.minimum}`);
    } else {
      parts.push(`max ${property.maximum}`);
    }
  }
  if (property.minLength !== undefined || property.maxLength !== undefined) {
    parts.push(
      `length ${property.minLength ?? 0}–${property.maxLength ?? "∞"}`
    );
  }
  if (property.pattern) {
    parts.push(`matches \`${property.pattern}\``);
  }
  if (property.default !== undefined) {
    parts.push(`defaults to \`${JSON.stringify(property.default)}\``);
  }

  return parts.length > 0 ? ` _(${parts.join("; ")})_` : "";
}

/** Table cells are pipe-delimited, so any pipe inside a description would split the row. */
function escapeCell(text: string): string {
  return text.replace(/\|/g, "\\|").replace(/\n+/g, " ").trim();
}

function renderTool(tool: ManifestTool): string {
  const properties = tool.inputSchema.properties ?? {};
  const required = new Set(tool.inputSchema.required ?? []);
  const names = Object.keys(properties).sort((left, right) => {
    // Required first: an agent reading top-down should meet the arguments it cannot omit before
    // the ones it can.
    const leftRequired = required.has(left) ? 0 : 1;
    const rightRequired = required.has(right) ? 0 : 1;
    return leftRequired - rightRequired || left.localeCompare(right);
  });

  const rows = names.map((name) => {
    const property = properties[name];
    const requiredLabel = required.has(name) ? "**Yes**" : "No";
    const description = escapeCell(property.description ?? "");
    return `| \`${name}\` | \`${formatType(property)}\` | ${requiredLabel} | ${description}${formatConstraints(property)} |`;
  });

  const table =
    names.length === 0
      ? "_This tool takes no arguments._"
      : [
          "| Parameter | Type | Required | Description |",
          "| --- | --- | --- | --- |",
          ...rows,
        ].join("\n");

  // The description and the argument table are SEPARATE h3 sections rather than one.
  //
  // The docs search index splits a page at each h2/h3 and truncates every section at 2500
  // characters, so a single section holding both put the tail of the longest tools --
  // establish_agent_delegation runs past 4000 -- beyond the end of the index. Half the arguments
  // of the most argument-heavy tool in the mesh would have been invisible to search on the one
  // page whose entire job is being searched. Splitting keeps each section inside the cap and
  // gives every argument table its own anchor to link to.
  return [
    `### \`${tool.name}\``,
    "",
    escapeCell(tool.description),
    "",
    `### \`${tool.name}\` arguments`,
    "",
    table,
    "",
  ].join("\n");
}

function renderDocument(tools: readonly ManifestTool[]): string {
  const byName = new Map(tools.map((tool) => [tool.name, tool]));
  const grouped = toolGroups.map((group) => {
    const groupTools = group.tools.map((name) => {
      const tool = byName.get(name);
      if (!tool) {
        throw new Error(
          `Tool "${name}" is grouped in generateToolReference.ts but absent from the manifest.`
        );
      }
      byName.delete(name);
      return tool;
    });
    return { group, groupTools };
  });

  if (byName.size > 0) {
    throw new Error(
      `Manifest tools missing from the reference grouping: ${[...byName.keys()].join(", ")}. ` +
        "Add them to toolGroups in scripts/generateToolReference.ts."
    );
  }

  const sections = grouped.map(({ group, groupTools }) =>
    [
      `## ${group.layer} · ${group.heading}`,
      "",
      group.intent,
      "",
      ...groupTools.map(renderTool),
    ].join("\n")
  );

  return `---
title: "MCP tool reference"
description: "Every tool an autonomous agent can call on the mesh, with its exact arguments, constraints and defaults, generated from the JSON Schema the server returns from tools/list."
navLabel: "Tool Reference"
navDescription: "Every tool and argument"
order: 6
section: "Reference"
icon: "Terminal"
audience: "developer"
---

{/*
  GENERATED FILE -- do not edit by hand.
  Produced by scripts/generateToolReference.ts from packages/mcpServer/src/constants/*Manifest.ts,
  which is the same JSON Schema an agent receives from tools/list. Change the manifest, then run
  \`npm run docs:tools\`.
*/}

The complete surface an autonomous buyer can call. These ${tools.length} tools are what
\`tools/list\` returns; the tables below are generated from that same schema, so an argument
documented here is an argument the server will accept, and a constraint shown here is one it will
enforce.

## Transport

The server speaks MCP over Streamable HTTP.

| | |
| --- | --- |
| Endpoint | \`http://localhost:4001/mcp\` |
| Protocol | MCP over Streamable HTTP (JSON-RPC 2.0) |
| Session | Issued by the server on initialize; sent back as \`Mcp-Session-Id\` |
| Auth | None in local mode. The mesh authenticates the *mandate chain*, not the caller |

A REST adapter mirrors the read-only discovery tools at \`/api/v1/*\` for clients that do not
speak MCP. It is the same handler and the same telemetry; see the Telemetry & SSE guide.

## Calling a tool

\`\`\`json
{
  "jsonrpc": "2.0",
  "id": 1,
  "method": "tools/call",
  "params": {
    "name": "search_catalog",
    "arguments": { "query_text": "ergonomic mesh office chair", "limit": 5 }
  }
}
\`\`\`

Arguments are \`snake_case\` on the wire. The server also accepts \`camelCase\` aliases for the
buyer SDK's benefit, but the manifest names below are the canonical ones.

${sections.join("\n")}
## When a call fails

A failure comes back as a tool result with \`success: false\`, never as a missing response. The
mesh distinguishes two kinds, and the distinction is on the telemetry payload as \`failureKind\`:

| \`failureKind\` | Meaning | What to do |
| --- | --- | --- |
| \`invalid_request\` | The arguments failed this tool's schema. The tables above list every constraint that can produce this | Fix the arguments and retry. Nothing was refused |
| \`refusal\` | A well-formed call the mesh declined -- budget exceeded, mandate expired, stock gone, signature invalid | Read \`exceptionCode\`. Retrying unchanged will fail identically |

A refusal carries a machine-readable \`exceptionCode\` alongside the message:

\`\`\`json
{
  "error": "SKU with identifier SKU-DOES-NOT-EXIST was not found in catalog",
  "exceptionCode": "SKU_NOT_FOUND"
}
\`\`\`

Both kinds are published to the telemetry stream and both are visible on the dashboard's
Live Agent screen, counted separately: an agent misdialling an argument is not the protocol
refusing it.
`;
}

if (!fs.existsSync(manifestEntryPoint)) {
  throw new Error(
    `The MCP tools manifest is not at ${manifestEntryPoint}. This generator must run from a ` +
      "checkout of the whole monorepo, not from the dashboard package alone."
  );
}

const manifestModule: { mcpToolsManifest: unknown } = await import(
  pathToFileURL(manifestEntryPoint).href
);
const manifestTools = manifestModule.mcpToolsManifest as readonly ManifestTool[];
const document = renderDocument(manifestTools);
fs.writeFileSync(outputPath, document, "utf-8");

// Only the shape the reference and its tests care about, so the artifact stays a readable diff
// rather than a dump of the whole manifest.
const manifestArtifact = manifestTools.map((tool) => ({
  name: tool.name,
  required: [...(tool.inputSchema.required ?? [])].sort(),
  parameters: Object.entries(tool.inputSchema.properties ?? {})
    .map(([parameterName, schema]) => ({
      name: parameterName,
      type: formatType(schema),
      description: schema.description ?? "",
    }))
    .sort((left, right) => left.name.localeCompare(right.name)),
}));
fs.mkdirSync(path.dirname(manifestArtifactPath), { recursive: true });
fs.writeFileSync(
  manifestArtifactPath,
  `${JSON.stringify(manifestArtifact, null, 2)}\n`,
  "utf-8"
);

const kilobytes = (Buffer.byteLength(document, "utf-8") / 1024).toFixed(1);
process.stdout.write(
  `Wrote docs/tool-reference.mdx (${manifestTools.length} tools, ${kilobytes} kB)\n`
);
