import { describe, it } from "node:test";
import assert from "node:assert/strict";
import fs from "node:fs";
import path from "node:path";

// docs/tool-reference.mdx is generated from the MCP manifest, and a generated file that is not
// checked is a file that silently goes stale. These are the properties that make the page worth
// trusting: it describes every tool the server exposes, no tool it does not, and it never
// publishes an argument with no explanation of what to put in it.
//
// Both sides are read from disk rather than imported from ../mcpServer. The dashboard's container
// image contains this package alone, so `next build` typechecks a tree where that sibling does
// not exist -- an import of it here compiles locally and breaks the image build, which is exactly
// what it did. scripts/generateToolReference.ts is the one place allowed to reach across, and it
// writes generated/mcpToolManifest.json for everything downstream, this test included.

const packageRoot = process.cwd();
const referenceSource = fs.readFileSync(
  path.join(packageRoot, "docs", "tool-reference.mdx"),
  "utf-8"
);

interface ManifestParameter {
  readonly name: string;
  readonly type: string;
  readonly description: string;
}

interface ManifestTool {
  readonly name: string;
  readonly required: readonly string[];
  readonly parameters: readonly ManifestParameter[];
}

const tools: readonly ManifestTool[] = JSON.parse(
  fs.readFileSync(path.join(packageRoot, "generated", "mcpToolManifest.json"), "utf-8")
);

describe("The generated tool reference matches the tools the server serves", () => {
  it("has a manifest artifact to check against at all", () => {
    // Guards the failure mode the rest of this file cannot see: an empty or missing artifact
    // would make every loop below iterate zero times and pass.
    assert.ok(tools.length >= 10, `Expected the full tool surface, got ${tools.length}`);
  });

  it("documents every tool in the manifest, and only those", () => {
    const documented = [...referenceSource.matchAll(/^### `([a-z_]+)`$/gm)].map(
      (match) => match[1]
    );
    const manifestNames = tools.map((tool) => tool.name).sort();

    assert.deepEqual([...new Set(documented)].sort(), manifestNames);
  });

  it("prints every argument of every tool", () => {
    for (const tool of tools) {
      for (const parameter of tool.parameters) {
        assert.ok(
          referenceSource.includes(`| \`${parameter.name}\` |`),
          `${tool.name}.${parameter.name} is in the manifest but missing from the reference. ` +
            "Run: npm run docs:tools"
        );
      }
    }
  });

  it("marks required arguments as required", () => {
    // An agent that reads "optional" on a required field will omit it and get a schema error it
    // cannot explain -- which is exactly the failure a live run produced eleven times.
    for (const tool of tools) {
      for (const parameterName of tool.required) {
        const row = referenceSource
          .split("\n")
          .find((line) => line.startsWith(`| \`${parameterName}\` |`));
        assert.ok(row, `No row for required argument ${tool.name}.${parameterName}`);
        assert.match(
          row,
          /\| \*\*Yes\*\* \|/,
          `${tool.name}.${parameterName} is required but the reference does not say so`
        );
      }
    }
  });
});

describe("The manifest itself explains every argument", () => {
  it("gives every argument of every tool a description", () => {
    // The reference can only be as good as its source. Before this was enforced, 31 of the
    // mesh's arguments shipped with no description at all -- including sku_id, quantity and
    // delegation_id, the three a real buyer agent most often got wrong.
    const undocumented = tools.flatMap((tool) =>
      tool.parameters
        .filter((parameter) => parameter.description.trim().length === 0)
        .map((parameter) => `${tool.name}.${parameter.name}`)
    );

    assert.deepEqual(
      undocumented,
      [],
      `Arguments with no description reach agents as a bare type: ${undocumented.join(", ")}`
    );
  });
});
