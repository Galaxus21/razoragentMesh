// Shapes for the MDX documentation pipeline.
//
// Every field a doc page needs comes from that file's own frontmatter, so adding a guide means
// adding one .mdx file -- there is no second place to register it. The previous loader kept two
// hand-maintained maps (filename and title) keyed by slug, which silently produced a "Page Not
// Found" body for any file whose slug had not also been added to both.

export interface DocFrontmatter {
  readonly title: string;
  readonly description: string;
  readonly navLabel: string;
  readonly navDescription: string;
  readonly order: number;
  readonly icon: string;
  readonly audience: string;
}

export interface DocHeading {
  readonly id: string;
  readonly text: string;
  readonly depth: number;
}

export interface DocPage {
  readonly slug: string;
  readonly slugSegments: readonly string[];
  readonly sourcePath: string;
  readonly frontmatter: DocFrontmatter;
  readonly body: string;
  readonly headings: readonly DocHeading[];
}

// The subset the sidebar and the prev/next control need. Kept separate from DocPage so the
// generated manifest does not have to carry every document's full body into the client bundle.
export interface DocNavEntry {
  readonly slug: string;
  readonly route: string;
  readonly navLabel: string;
  readonly navDescription: string;
  readonly title: string;
  readonly description: string;
  readonly order: number;
  readonly icon: string;
}

// One heading and the prose beneath it. The table of contents needs only the heading; the
// search index needs the prose too, and both must agree on the anchor id -- so docsLoader
// derives them from the same walk rather than scanning the document twice.
export interface DocSection {
  readonly heading: DocHeading | null;
  readonly body: string;
}

// A single searchable unit: one section of one guide. The generated index is imported by a
// client component, so every field here is shipped to the browser -- searchText is truncated
// when the index is built rather than carrying whole documents into the bundle.
export interface DocSearchEntry {
  readonly route: string;
  readonly docTitle: string;
  readonly headingText: string;
  readonly snippet: string;
  readonly searchText: string;
}
