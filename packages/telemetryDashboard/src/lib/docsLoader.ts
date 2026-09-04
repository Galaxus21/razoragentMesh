// Loads documentation by scanning the docs directory, not by consulting a registry.
//
// The previous loader kept two hand-maintained maps keyed by slug -- one for the filename, one
// for a fallback title -- so a new guide silently rendered "Documentation Page Not Found" until
// both were edited too. Everything now comes from the file itself: the slug is its name, the
// title and navigation labels are its frontmatter. Adding a guide means adding one file.

import fs from "node:fs";
import path from "node:path";
import matter from "gray-matter";
import GithubSlugger from "github-slugger";
import type {
  DocFrontmatter,
  DocHeading,
  DocNavEntry,
  DocPage,
  DocSection,
} from "@/types/docsTypes";

export const docsFileExtension = ".mdx";
export const docsRoutePrefix = "/docs";

const minimumHeadingDepth = 2;
const maximumHeadingDepth = 3;
const fencedBlockMarker = "```";

// Package-local only: documentation rendered by this service must live inside the service
// directory. Parent-traversal lookups (`../docs`) break Docker build-context isolation.
export function resolveDocsDirectory(): string {
  const currentWorkingDir = process.cwd();
  const candidatePaths = [
    path.resolve(currentWorkingDir, "docs"),
    path.resolve(currentWorkingDir, "src/docs"),
  ];
  for (const candidate of candidatePaths) {
    if (fs.existsSync(candidate)) {
      return candidate;
    }
  }
  return path.resolve(currentWorkingDir, "docs");
}

function listMdxFilesRecursively(directory: string, relativePrefix = ""): readonly string[] {
  if (!fs.existsSync(directory)) {
    return [];
  }
  const collected: string[] = [];
  for (const entry of fs.readdirSync(directory, { withFileTypes: true })) {
    const relativePath = relativePrefix ? `${relativePrefix}/${entry.name}` : entry.name;
    if (entry.isDirectory()) {
      collected.push(...listMdxFilesRecursively(path.join(directory, entry.name), relativePath));
    } else if (entry.name.endsWith(docsFileExtension)) {
      collected.push(relativePath);
    }
  }
  return collected;
}

function readFrontmatterField(
  data: Record<string, unknown>,
  key: string,
  fallback: string
): string {
  const value = data[key];
  return typeof value === "string" && value.trim().length > 0 ? value : fallback;
}

function toFrontmatter(data: Record<string, unknown>, slug: string): DocFrontmatter {
  const orderValue = data.order;
  return {
    title: readFrontmatterField(data, "title", slug),
    description: readFrontmatterField(data, "description", ""),
    navLabel: readFrontmatterField(data, "navLabel", slug),
    navDescription: readFrontmatterField(data, "navDescription", ""),
    // Unordered documents sort last rather than silently jumping to the top of the sidebar.
    order: typeof orderValue === "number" ? orderValue : Number.MAX_SAFE_INTEGER,
    icon: readFrontmatterField(data, "icon", "FileText"),
    audience: readFrontmatterField(data, "audience", "developer"),
    // An unsectioned page lands under Guides rather than vanishing from the sidebar.
    section: readFrontmatterField(data, "section", "Guides"),
  };
}

// Walks the document once, splitting it at every h2/h3 into the section that heading
// introduces. Headings and search sections are both derived from this single walk: if they
// were collected by two separate passes, the anchor ids the table of contents links to and the
// ids the search results link to could disagree, and nothing would notice.
//
// The ids must match what rehype-slug produces at render time, so the same github-slugger
// implementation generates them -- including its de-duplication counter, which is why one
// slugger instance is reused across the whole document.
export function splitIntoSections(body: string): readonly DocSection[] {
  const slugger = new GithubSlugger();
  const sections: DocSection[] = [];
  let currentHeading: DocHeading | null = null;
  let currentLines: string[] = [];
  let isInsideFence = false;

  const flush = (): void => {
    if (currentHeading !== null || currentLines.some((line) => line.trim().length > 0)) {
      sections.push({ heading: currentHeading, body: currentLines.join("\n") });
    }
  };

  for (const line of body.split("\n")) {
    if (line.trimStart().startsWith(fencedBlockMarker)) {
      isInsideFence = !isInsideFence;
      currentLines.push(line);
      continue;
    }

    const match = isInsideFence ? null : /^(#{2,3})\s+(.+?)\s*$/.exec(line);
    if (!match) {
      currentLines.push(line);
      continue;
    }

    const depth = match[1].length;
    if (depth < minimumHeadingDepth || depth > maximumHeadingDepth) {
      currentLines.push(line);
      continue;
    }

    flush();
    const text = match[2].replace(/`/g, "").trim();
    currentHeading = { id: slugger.slug(text), text, depth };
    currentLines = [];
  }
  flush();

  return sections;
}

export function extractHeadings(body: string): readonly DocHeading[] {
  return splitIntoSections(body)
    .map((section) => section.heading)
    .filter((heading): heading is DocHeading => heading !== null);
}

function readDocPage(docsDirectory: string, relativePath: string): DocPage {
  const absolutePath = path.join(docsDirectory, relativePath);
  const rawFile = fs.readFileSync(absolutePath, "utf-8");
  const parsed = matter(rawFile);
  const slug = relativePath.slice(0, -docsFileExtension.length);

  return {
    slug,
    slugSegments: slug.split("/"),
    sourcePath: `packages/telemetryDashboard/docs/${relativePath}`,
    frontmatter: toFrontmatter(parsed.data as Record<string, unknown>, slug),
    body: parsed.content,
    headings: extractHeadings(parsed.content),
  };
}

export function loadAllDocPages(): readonly DocPage[] {
  const docsDirectory = resolveDocsDirectory();
  return listMdxFilesRecursively(docsDirectory)
    .map((relativePath) => readDocPage(docsDirectory, relativePath))
    .sort((left, right) => {
      if (left.frontmatter.order !== right.frontmatter.order) {
        return left.frontmatter.order - right.frontmatter.order;
      }
      return left.slug.localeCompare(right.slug);
    });
}

export function loadDocPage(slugSegments: readonly string[]): DocPage | null {
  const requestedSlug = slugSegments.join("/");
  return loadAllDocPages().find((page) => page.slug === requestedSlug) ?? null;
}

export function toNavEntry(page: DocPage): DocNavEntry {
  return {
    slug: page.slug,
    route: `${docsRoutePrefix}/${page.slug}`,
    navLabel: page.frontmatter.navLabel,
    navDescription: page.frontmatter.navDescription,
    title: page.frontmatter.title,
    description: page.frontmatter.description,
    order: page.frontmatter.order,
    icon: page.frontmatter.icon,
    section: page.frontmatter.section,
  };
}

export function loadDocNavEntries(): readonly DocNavEntry[] {
  return loadAllDocPages().map(toNavEntry);
}
