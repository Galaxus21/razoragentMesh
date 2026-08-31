import { describe, it } from "node:test";
import assert from "node:assert/strict";

import {
  extractExampleRegions,
  findExampleRegion,
  type ExampleSource,
} from "../src/lib/reference/exampleRegions.js";
import { loadExampleSources } from "../src/lib/reference/referenceTables.js";

// Two things are asserted here. What the region cutter does to a given source -- the behaviour,
// which is cheap to get subtly wrong -- and that the committed table it produces still describes
// the examples on disk, which is what makes <Snippet> a view rather than a second copy.

const typeScriptSource = [
  "const before = 1;",
  "// #region cart",
  "  const inside = 2;",
  "  const alsoInside = 3;",
  "// #endregion cart",
  "const after = 4;",
].join("\n");

describe("Cutting named regions out of an example", () => {
  it("returns only what is between the markers", () => {
    assert.deepEqual(extractExampleRegions(typeScriptSource), [
      { name: "cart", code: "const inside = 2;\nconst alsoInside = 3;" },
    ]);
  });

  it("removes the common indent, so a region lifted out of a function body reads flush", () => {
    // The two lines above are indented two spaces inside the region and zero after dedenting.
    const [region] = extractExampleRegions(typeScriptSource);
    assert.ok(!region.code.split("\n").some((line) => line.startsWith(" ")));
  });

  it("keeps relative indentation inside the region", () => {
    // Dedenting must not flatten structure -- only the common prefix comes off.
    const [region] = extractExampleRegions(
      ["# region body", "    if x:", "        return 1", "# endregion"].join("\n")
    );
    assert.equal(region.code, "if x:\n    return 1");
  });

  it("reads Python's marker style as well as TypeScript's", () => {
    const [region] = extractExampleRegions(
      ["# region intent", "value = 1", "# endregion intent"].join("\n")
    );
    assert.deepEqual(region, { name: "intent", code: "value = 1" });
  });

  it("trims blank lines at the edges but not in the middle", () => {
    const [region] = extractExampleRegions(
      ["// #region gap", "", "first", "", "second", "", "// #endregion"].join("\n")
    );
    assert.equal(region.code, "first\n\nsecond");
  });

  it("ignores a file with no markers rather than treating the whole file as one region", () => {
    assert.deepEqual(extractExampleRegions("const alone = 1;\n"), []);
  });

  it("refuses a region that is never closed", () => {
    // Silently returning the rest of the file would transclude an arbitrary tail into a guide.
    assert.throws(
      () => extractExampleRegions("// #region open\nconst inside = 1;\n"),
      /Region open is never closed/
    );
  });

  it("refuses nested regions instead of guessing which one the end marker closes", () => {
    assert.throws(
      () => extractExampleRegions("// #region outer\n// #region inner\n// #endregion\n"),
      /Region outer is still open where region inner begins/
    );
  });
});

describe("Resolving a <Snippet> reference", () => {
  const sources: readonly ExampleSource[] = [
    { path: "examples/typescript/a.ts", language: "typescript", regions: [{ name: "one", code: "x" }] },
  ];

  it("returns the region with the language its file was written in", () => {
    assert.deepEqual(findExampleRegion(sources, "examples/typescript/a.ts", "one"), {
      name: "one",
      code: "x",
      language: "typescript",
    });
  });

  it("names the regions that do exist when one does not", () => {
    // A component that rendered nothing here would put an empty box in a published guide.
    assert.throws(
      () => findExampleRegion(sources, "examples/typescript/a.ts", "two"),
      /has no region "two". It has: one/
    );
  });

  it("names the available files when the path is unknown", () => {
    assert.throws(
      () => findExampleRegion(sources, "examples/ts/a.ts", "one"),
      /not a generated example. Available: examples\/typescript\/a.ts/
    );
  });
});

describe("The committed snippet table still describes the examples on disk", () => {
  it("covers both runtimes, so neither guide half is transcluding stale code", () => {
    const paths = loadExampleSources().map((source) => source.path);
    assert.ok(
      paths.some((path) => path.startsWith("examples/typescript/")),
      `no TypeScript example in the generated table: ${paths.join(", ")}`
    );
    assert.ok(
      paths.some((path) => path.startsWith("examples/python/")),
      `no Python example in the generated table: ${paths.join(", ")}`
    );
  });

  it("records a non-empty body for every region it lists", () => {
    for (const source of loadExampleSources()) {
      assert.ok(source.regions.length > 0, `${source.path} contributes no regions`);
      for (const region of source.regions) {
        assert.ok(region.code.trim().length > 0, `${source.path}#${region.name} is empty`);
      }
    }
  });
});
