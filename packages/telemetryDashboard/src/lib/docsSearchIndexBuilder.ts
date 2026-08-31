// Turns the docs directory into a flat, searchable index of sections.
//
// Search is done in the browser against a generated index rather than by a server round trip:
// these are six guides, not a corpus, and shipping the index means the box works offline and
// on a statically exported build. The cost is bundle size, which is why the prose is stripped
// to plain text and every section's haystack is truncated -- see maxSearchTextLength.
//
// Sections come from docsLoader.splitIntoSections, the same walk that produces the table of
// contents, so a result's anchor is guaranteed to be an anchor that exists on the page.

import { loadAllDocPages, docsRoutePrefix, splitIntoSections } from "@/lib/docsLoader";
import type { DocSearchEntry } from "@/types/docsTypes";

// 2500 covers the longest haystack the current guides produce (2125 characters: heading,
// document title, and the section's plain text) with headroom, so every word of prose is
// reachable -- a test asserts that nothing is truncated. It is a cap rather than no cap at all
// because the index ships to the browser: one future 20-page reference document should cost
// bounded bundle size, not unbounded. If sections start truncating, the answer is to split
// the document, not to raise this quietly -- a truncated section is prose that search cannot
// find, with nothing on the page to say so.
export const maxSearchTextLength = 2500;
export const maxSnippetLength = 160;

const fencedBlockPattern = /```[\s\S]*?```/g;
const jsxTagPattern = /<\/?[A-Za-z][^>]*>/g;
const mathBlockPattern = /\$\$[\s\S]*?\$\$/g;
const inlineMathPattern = /\$[^$\n]+\$/g;
const markdownLinkPattern = /\[([^\]]*)\]\([^)]*\)/g;
const markdownEmphasisPattern = /[*_~`#>|]/g;
const htmlEntityPattern = /&[a-z]+;/gi;
const collapsibleWhitespacePattern = /\s+/g;

// Code fences are dropped rather than indexed: a search for "docker" should land on the
// paragraph that explains the step, not on whichever of the fifty shell blocks mentions it
// first. The same goes for LaTeX, which is unreadable as a result snippet.
export function toPlainText(markdown: string): string {
  return markdown
    .replace(fencedBlockPattern, " ")
    .replace(mathBlockPattern, " ")
    .replace(inlineMathPattern, " ")
    .replace(jsxTagPattern, " ")
    .replace(markdownLinkPattern, "$1")
    .replace(htmlEntityPattern, " ")
    .replace(markdownEmphasisPattern, " ")
    .replace(collapsibleWhitespacePattern, " ")
    .trim();
}

function truncate(text: string, limit: number): string {
  if (text.length <= limit) {
    return text;
  }
  const cut = text.slice(0, limit);
  const lastSpace = cut.lastIndexOf(" ");
  return `${(lastSpace > 0 ? cut.slice(0, lastSpace) : cut).trimEnd()}...`;
}

export function buildDocsSearchIndex(): readonly DocSearchEntry[] {
  const entries: DocSearchEntry[] = [];

  for (const page of loadAllDocPages()) {
    const baseRoute = `${docsRoutePrefix}/${page.slug}`;

    for (const section of splitIntoSections(page.body)) {
      const plainText = toPlainText(section.body);
      const headingText = section.heading?.text ?? "";

      // A section with a heading is worth indexing even when its prose is all code: the
      // heading itself is the thing most readers search for. A preamble with no heading and
      // no prose is not.
      if (headingText.length === 0 && plainText.length === 0) {
        continue;
      }

      entries.push({
        route: section.heading ? `${baseRoute}#${section.heading.id}` : baseRoute,
        docTitle: page.frontmatter.title,
        headingText,
        snippet: truncate(plainText, maxSnippetLength),
        // Lowercased at build time so the matcher does not lowercase the whole index on every
        // keystroke.
        searchText: truncate(
          `${headingText} ${page.frontmatter.title} ${plainText}`.toLowerCase(),
          maxSearchTextLength
        ),
      });
    }
  }

  return entries;
}
