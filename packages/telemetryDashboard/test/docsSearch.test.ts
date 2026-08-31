import { describe, it } from "node:test";
import assert from "node:assert/strict";

import { docsSearchIndex } from "../src/generated/docsSearchIndex.js";
import {
  buildDocsSearchIndex,
  maxSearchTextLength,
  maxSnippetLength,
  toPlainText,
} from "../src/lib/docsSearchIndexBuilder.js";
import {
  defaultResultLimit,
  minimumQueryLength,
  searchDocs,
  tokenizeQuery,
} from "../src/lib/docsSearchMatcher.js";
import { loadAllDocPages, loadDocPage } from "../src/lib/docsLoader.js";
import type { DocSearchEntry } from "../src/types/docsTypes.js";

// The index ships to the browser and is checked into git, so it is the one docs artifact that
// can silently describe a version of the guides that no longer exists. These assertions are
// what stop that: it is compared against a fresh scan, and every route it advertises is
// resolved back to a heading that actually exists on the page it names.

describe("Generated docs search index stays in sync", () => {
  it("matches what the builder produces right now", () => {
    assert.deepEqual(
      JSON.parse(JSON.stringify(docsSearchIndex)),
      JSON.parse(JSON.stringify(buildDocsSearchIndex())),
      "src/generated/docsSearchIndex.ts is stale -- run: npm run docs:generate"
    );
  });

  it("points every result at a document and an anchor that exist", () => {
    // A result that scrolls nowhere is worse than no result: the reader believes they were
    // taken to the answer. Each route is split back into slug and fragment and resolved.
    for (const entry of docsSearchIndex) {
      const [routePath, fragment] = entry.route.split("#");
      const slug = routePath.replace(/^\/docs\//, "");
      const page = loadDocPage(slug.split("/"));
      assert.ok(page, `${entry.route} names no document`);

      if (fragment) {
        const anchorIds = page.headings.map((heading) => heading.id);
        assert.ok(
          anchorIds.includes(fragment),
          `${entry.route} points at an anchor the page does not render`
        );
      }
    }
  });

  it("indexes every guide, so no document is unsearchable", () => {
    const indexedSlugs = new Set(
      docsSearchIndex.map((entry) => entry.route.split("#")[0].replace(/^\/docs\//, ""))
    );
    for (const page of loadAllDocPages()) {
      assert.ok(indexedSlugs.has(page.slug), `${page.slug} contributed no searchable sections`);
    }
  });

  it("truncates every field so the bundle cannot grow with the prose", () => {
    for (const entry of docsSearchIndex) {
      assert.ok(
        entry.searchText.length <= maxSearchTextLength + 3,
        `${entry.route} searchText is ${entry.searchText.length} chars`
      );
      assert.ok(entry.snippet.length <= maxSnippetLength + 3, `${entry.route} snippet too long`);
      assert.equal(entry.searchText, entry.searchText.toLowerCase());
    }
  });

  it("reaches the end of every section, so no prose is silently unsearchable", () => {
    // The cap started at 600, which truncated 19 of the 103 sections and left a quarter of the
    // prose unfindable -- with nothing on the page to say so. This is the assertion that keeps
    // the cap honest: a section that outgrows it fails here, and the fix is to split the
    // document, not to raise the number until the failure goes away.
    for (const entry of docsSearchIndex) {
      assert.ok(
        !entry.searchText.endsWith("..."),
        `${entry.route} is truncated at ${maxSearchTextLength} chars -- the tail of that ` +
          `section cannot be found by search`
      );
    }
  });
});

describe("Plain-text extraction", () => {
  it("drops fenced code so results are prose, not shell transcripts", () => {
    const plain = toPlainText("Run the service.\n\n```bash\ndocker compose up --build\n```\n\nDone.");
    assert.ok(plain.includes("Run the service."));
    assert.ok(plain.includes("Done."));
    assert.ok(!plain.includes("docker compose"), "A code fence leaked into the searchable text");
  });

  it("drops LaTeX, which is unreadable as a result snippet", () => {
    const plain = toPlainText("Tax splits evenly: $$\\text{cgstPaise} = \\lfloor x \\rfloor$$ each.");
    assert.ok(!plain.includes("lfloor"));
    assert.ok(plain.includes("Tax splits evenly:"));
  });

  it("keeps link text but discards the target", () => {
    const plain = toPlainText("See the [buyer SDK guide](/docs/buyer-sdk) for details.");
    assert.ok(plain.includes("buyer SDK guide"));
    assert.ok(!plain.includes("/docs/buyer-sdk"));
  });

  it("strips embedded components rather than indexing their markup", () => {
    const plain = toPlainText('Before <ApiEndpoint service="mcpServer" path="/health" /> after');
    assert.ok(!plain.includes("ApiEndpoint"));
    assert.equal(plain, "Before after");
  });
});

describe("Search ranking", () => {
  const entry = (overrides: Partial<DocSearchEntry>): DocSearchEntry => ({
    route: "/docs/example#section",
    docTitle: "Example Guide",
    headingText: "A Section",
    snippet: "",
    searchText: "a section example guide",
    ...overrides,
  });

  it("ignores a query too short to be meaningful", () => {
    assert.deepEqual(searchDocs(docsSearchIndex, "a"), []);
    assert.deepEqual(searchDocs(docsSearchIndex, "   "), []);
    assert.equal(minimumQueryLength, 2);
  });

  it("requires every term to match, not just one", () => {
    const index = [entry({ searchText: "settlement saga runs to completion" })];
    assert.equal(searchDocs(index, "settlement saga").length, 1);
    // 'qdrant' appears nowhere in that section, so the section is not a result at all.
    assert.equal(searchDocs(index, "settlement qdrant").length, 0);
  });

  it("ranks a heading hit above a body hit", () => {
    const index = [
      entry({ route: "/docs/a#body", headingText: "Unrelated", searchText: "unrelated mandate" }),
      entry({ route: "/docs/b#head", headingText: "Mandate Chain", searchText: "mandate chain" }),
    ];
    const results = searchDocs(index, "mandate");
    assert.equal(results[0].entry.route, "/docs/b#head");
  });

  it("ranks a heading containing the whole phrase first", () => {
    const index = [
      entry({
        route: "/docs/a#scattered",
        headingText: "Inventory",
        searchText: "inventory lock appears far apart here in prose",
      }),
      entry({
        route: "/docs/b#phrase",
        headingText: "Inventory Lock",
        searchText: "inventory lock",
      }),
    ];
    assert.equal(searchDocs(index, "inventory lock")[0].entry.route, "/docs/b#phrase");
  });

  it("caps how many results reach the dropdown", () => {
    // 'the' matches nearly every section; the limit is what keeps the panel usable.
    assert.ok(searchDocs(docsSearchIndex, "the").length <= defaultResultLimit);
  });

  it("finds real content in the shipped guides", () => {
    // Chosen because each is a term a reader would actually type, and each lives in a
    // different guide -- so this fails if the index silently narrows to one document.
    for (const query of ["gstin", "mandate", "docker", "telemetry"]) {
      assert.ok(searchDocs(docsSearchIndex, query).length > 0, `No result for '${query}'`);
    }
  });

  it("splits a query on whitespace without producing empty terms", () => {
    assert.deepEqual(tokenizeQuery("  Mandate   Chain "), ["mandate", "chain"]);
  });
});
