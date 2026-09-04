import { describe, it } from "node:test";
import assert from "node:assert/strict";
import fs from "node:fs";
import path from "node:path";

import {
  docsRoutePrefix,
  extractHeadings,
  loadAllDocPages,
  loadDocNavEntries,
  loadDocPage,
  resolveDocsDirectory,
} from "../src/lib/docsLoader.js";
import { docsManifest } from "../src/generated/docsManifest.js";
import {
  documentationSectionOrder,
  navigationCategories,
  navigationItems,
} from "../src/constants/sidebarNavigationConfig.js";

// The pipeline's whole claim is that a guide is registered by existing. These assertions are
// what make that true: if the manifest, the sidebar and the directory can drift apart, the old
// failure mode returns -- a route that renders "Page Not Found" with HTTP 200.

describe("Docs directory is the single source of truth", () => {
  it("discovers every .mdx file in the docs directory and nothing else", () => {
    const docsDirectory = resolveDocsDirectory();
    const filesOnDisk = fs
      .readdirSync(docsDirectory)
      .filter((name) => name.endsWith(".mdx"))
      .map((name) => name.slice(0, -".mdx".length))
      .sort();

    const discovered = loadAllDocPages()
      .map((page) => page.slug)
      .sort();
    assert.deepEqual(discovered, filesOnDisk);
  });

  it("leaves no stale .md files behind from the migration", () => {
    const leftovers = fs
      .readdirSync(resolveDocsDirectory())
      .filter((name) => name.endsWith(".md"));
    assert.deepEqual(leftovers, [], "Unconverted .md files would be silently unreachable");
  });

  it("requires the frontmatter every consumer reads", () => {
    for (const page of loadAllDocPages()) {
      assert.ok(page.frontmatter.title.length > 0, `${page.slug}: title`);
      assert.ok(page.frontmatter.description.length > 0, `${page.slug}: description`);
      assert.ok(page.frontmatter.navLabel.length > 0, `${page.slug}: navLabel`);
      assert.ok(page.frontmatter.navDescription.length > 0, `${page.slug}: navDescription`);
      assert.ok(page.frontmatter.icon.length > 0, `${page.slug}: icon`);
      assert.notEqual(
        page.frontmatter.order,
        Number.MAX_SAFE_INTEGER,
        `${page.slug} has no order, so it would sort last by accident`
      );
    }
  });

  it("assigns each guide a unique order so the sidebar is deterministic", () => {
    const orders = loadAllDocPages().map((page) => page.frontmatter.order);
    assert.equal(new Set(orders).size, orders.length, "Duplicate order values");
  });

  it("returns null rather than a fake page for an unknown slug", () => {
    // The previous loader returned a "Page Not Found" body with a 200 status, which read as a
    // real page to every caller. A null lets the route send a real 404.
    assert.equal(loadDocPage(["does-not-exist"]), null);
    assert.equal(loadDocPage([]), null);
  });
});

describe("Generated docs manifest stays in sync", () => {
  it("matches what the loader discovers right now", () => {
    // The manifest is committed so the client bundle can import it without filesystem access.
    // That makes it the one artifact that can go stale, so it is compared field by field
    // against a fresh scan. Regenerate with: npm run docs:manifest
    assert.deepEqual(
      JSON.parse(JSON.stringify(docsManifest)),
      JSON.parse(JSON.stringify(loadDocNavEntries())),
      "src/generated/docsManifest.ts is stale -- run: npm run docs:manifest"
    );
  });

  it("routes every manifest entry under the docs prefix", () => {
    for (const entry of docsManifest) {
      assert.equal(entry.route, `${docsRoutePrefix}/${entry.slug}`);
    }
  });
});

describe("Sidebar documentation section derives from the manifest", () => {
  it("lists exactly the documents that exist, in frontmatter order", () => {
    const documentationCategory = navigationCategories.find(
      (category) => category.id === "documentation"
    );
    assert.ok(documentationCategory);

    // The first child is the /docs landing page, which is a route rather than a document.
    // Everything after it must be exactly the manifest, in exactly its order -- that is what
    // keeps the sidebar derived from the docs directory instead of hand-maintained.
    const [landing, ...guides] = documentationCategory.children;
    assert.equal(landing.route, "/docs");

    assert.deepEqual(
      guides.map((child) => child.route),
      docsManifest.map((entry) => entry.route)
    );
    assert.deepEqual(
      guides.map((child) => child.label),
      docsManifest.map((entry) => entry.navLabel)
    );
  });

  it("backs every /docs route in the sidebar with a real document", () => {
    const docsRoutes = navigationItems
      .map((item) => item.route)
      .filter((route) => route.startsWith(`${docsRoutePrefix}/`));
    assert.ok(docsRoutes.length > 0);

    for (const route of docsRoutes) {
      const slug = route.slice(`${docsRoutePrefix}/`.length);
      assert.ok(loadDocPage(slug.split("/")), `${route} has no backing document`);
    }
  });
});

describe("Every guide declares a section the sidebar can group by", () => {
  it("assigns each document to one of the declared sections", () => {
    // `section` is load-bearing: it is the sidebar heading and the docs-index grouping. A
    // malformed value renders as a heading rather than failing, so it is invisible in every test
    // that only counts routes -- which is exactly how `\\"Get started` once reached seven files
    // with the whole suite green.
    for (const page of loadAllDocPages()) {
      assert.ok(
        documentationSectionOrder.includes(page.frontmatter.section),
        `${page.slug} declares section ${JSON.stringify(page.frontmatter.section)}, which is not ` +
          `one of ${documentationSectionOrder.filter(Boolean).join(", ")}`
      );
    }
  });
});

describe("Heading extraction feeds the table of contents", () => {
  it("collects h2 and h3 headings with github-compatible anchor ids", () => {
    const headings = extractHeadings("## First Section\n\ntext\n\n### Nested & Detail\n");
    assert.deepEqual(headings, [
      { id: "first-section", text: "First Section", depth: 2 },
      { id: "nested--detail", text: "Nested & Detail", depth: 3 },
    ]);
  });

  it("ignores headings inside fenced code blocks", () => {
    // A shell comment like `# not a heading` inside a bash fence must not reach the contents.
    const headings = extractHeadings("## Real\n\n```bash\n## Not A Heading\n```\n\n## Also Real\n");
    assert.deepEqual(
      headings.map((heading) => heading.text),
      ["Real", "Also Real"]
    );
  });

  it("de-duplicates repeated heading text the way rehype-slug does", () => {
    const headings = extractHeadings("## Setup\n\n## Setup\n");
    assert.deepEqual(
      headings.map((heading) => heading.id),
      ["setup", "setup-1"]
    );
  });

  it("produces a usable contents list for every shipped guide", () => {
    for (const page of loadAllDocPages()) {
      assert.ok(page.headings.length > 0, `${page.slug} produced no headings`);
      const ids = page.headings.map((heading) => heading.id);
      assert.equal(new Set(ids).size, ids.length, `${page.slug} has duplicate anchor ids`);
    }
  });
});

describe("MDX sources are compilable", () => {
  it("has no bare HTML tags that MDX would read as JSX", () => {
    // MDX parses `<br>` as JSX and fails on it; void elements must be self-closed. Braces are
    // covered by remark-math, which claims `$...$` before MDX sees the expression.
    const docsDirectory = resolveDocsDirectory();
    for (const page of loadAllDocPages()) {
      const raw = fs.readFileSync(path.join(docsDirectory, `${page.slug}.mdx`), "utf-8");
      assert.ok(!raw.includes("<br>"), `${page.slug} contains an unclosed <br>`);
      assert.ok(!raw.includes("<hr>"), `${page.slug} contains an unclosed <hr>`);
    }
  });
});
