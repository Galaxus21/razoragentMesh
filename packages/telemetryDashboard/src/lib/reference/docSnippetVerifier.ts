// Runs every doc page's code against the generated reference and reports what does not resolve.
//
// The order of the checks below is the order of how wrong each mistake is for a reader. An
// install line that names no package stops them at minute one; a member that does not exist
// stops them after they have written code around it.

import type { SnippetFinding } from "@/types/docSnippetTypes";
import type { DocPage } from "@/types/docsTypes";
import fs from "node:fs";
import path from "node:path";
import { loadAllDocPages, resolveDocsDirectory } from "@/lib/docsLoader";
import { extractCodeFences, extractSnippetFacts } from "@/lib/reference/docSnippetExtractor";
import {
  checkFenceAgainstTable,
  collectReceiverTypes,
  type CheckContext,
} from "@/lib/reference/docSnippetChecks";
import { checkDocumentedEndpoints, checkServiceUrls } from "@/lib/reference/docEndpointChecks";
import { collectDocumentedEnvVars, findUnreadEnvVars } from "@/lib/reference/docEnvVarChecks";
import { findExampleRegion } from "@/lib/reference/exampleRegions";
import {
  buildPythonSymbolTable,
  buildTypeScriptSymbolTable,
  loadExampleSources,
  loadHttpApiReference,
  type SymbolTable,
} from "@/lib/reference/referenceTables";

const mdxExtension = ".mdx";
const lineBreakPattern = /\r?\n/;

// Fences and URLs are located within the body, which gray-matter hands over with the frontmatter
// already removed. A finding whose line number is nine short of the real one sends the reader to
// the wrong place, so the frontmatter is measured back in here.
function resolveBodyLineOffset(slug: string, body: string): number {
  const raw = fs.readFileSync(path.join(resolveDocsDirectory(), `${slug}${mdxExtension}`), "utf-8");
  const bodyStart = raw.indexOf(body);
  const precedingText = raw.slice(0, bodyStart);
  return precedingText.length === 0 ? 0 : precedingText.split(lineBreakPattern).length - 1;
}

function atSourceLine(offset: number, findings: readonly SnippetFinding[]): SnippetFinding[] {
  return findings.map((finding) => ({ ...finding, line: finding.line + offset }));
}

const npmInstaller = "npm install";
const pipInstaller = "pip install";

// <Snippet file=".." region=".." /> in either attribute order, self-closing or with children.
const snippetTagPattern = /<Snippet\s+([^>]*?)\/?>/g;
const snippetFileAttribute = /\bfile\s*=\s*"([^"]+)"/;
const snippetRegionAttribute = /\bregion\s*=\s*"([^"]+)"/;

// A transcluded region resolves at render time, so a stale one already fails `next build`. It is
// checked here as well because a build failure names a React component and a checker failure
// names the guide, the line and the regions that do exist -- and because the same command should
// answer "is anything in the docs wrong" whether the prose pastes code or transcludes it.
function checkTranscludedRegions(sourcePath: string, body: string): readonly SnippetFinding[] {
  const sources = loadExampleSources();
  const findings: SnippetFinding[] = [];

  for (const match of body.matchAll(snippetTagPattern)) {
    const file = snippetFileAttribute.exec(match[1])?.[1];
    const region = snippetRegionAttribute.exec(match[1])?.[1];
    const line = body.slice(0, match.index).split(lineBreakPattern).length;
    if (!file || !region) {
      findings.push({ sourcePath, line, message: "<Snippet> needs both a file and a region" });
      continue;
    }
    try {
      findExampleRegion(sources, file, region);
    } catch (error) {
      findings.push({ sourcePath, line, message: (error as Error).message });
    }
  }
  return findings;
}

interface LanguageTables {
  readonly typeScript: SymbolTable;
  readonly python: SymbolTable;
  readonly knownPackageNames: ReadonlySet<string>;
  readonly installerPackageNames: Readonly<Record<string, string>>;
}

function checkFencesOnPage(page: DocPage, tables: LanguageTables): readonly SnippetFinding[] {
  // One map per language per page: a Python variable named `buyerAgent` says nothing about what
  // the TypeScript fence three sections earlier bound that name to.
  const typeScriptReceivers = new Map<string, string>();
  const pythonReceivers = new Map<string, string>();
  const tableByLanguage = {
    typescript: tables.typeScript,
    javascript: tables.typeScript,
    python: tables.python,
  };
  const receiversByLanguage = {
    typescript: typeScriptReceivers,
    javascript: typeScriptReceivers,
    python: pythonReceivers,
  };

  const findings: SnippetFinding[] = [];
  for (const fence of extractCodeFences(page)) {
    const facts = extractSnippetFacts(fence);
    const table = tableByLanguage[fence.language];
    const receiverTypes = receiversByLanguage[fence.language];
    collectReceiverTypes(facts, table, receiverTypes);

    const context: CheckContext = {
      table,
      receiverTypes,
      knownPackageNames: tables.knownPackageNames,
      installerPackageNames: tables.installerPackageNames,
    };
    findings.push(...checkFenceAgainstTable(fence, facts, context), ...checkServiceUrls(fence, facts));
  }
  return findings;
}

export function verifyDocSnippets(): readonly SnippetFinding[] {
  const typeScript = buildTypeScriptSymbolTable();
  const python = buildPythonSymbolTable();
  const httpApi = loadHttpApiReference();
  const tables: LanguageTables = {
    typeScript,
    python,
    knownPackageNames: new Set([typeScript.packageName, python.packageName]),
    installerPackageNames: {
      [npmInstaller]: typeScript.packageName,
      [pipInstaller]: python.packageName,
    },
  };

  const findings: SnippetFinding[] = [];
  for (const page of loadAllDocPages()) {
    const offset = resolveBodyLineOffset(page.slug, page.body);
    findings.push(
      ...atSourceLine(offset, checkDocumentedEndpoints(page.sourcePath, page.body, httpApi)),
      ...atSourceLine(offset, checkTranscludedRegions(page.sourcePath, page.body)),
      ...atSourceLine(
        offset,
        findUnreadEnvVars(collectDocumentedEnvVars(page.body, page.sourcePath)).map((variable) => ({
          sourcePath: variable.sourcePath,
          line: variable.line,
          message: variable.name + ' is documented as configuration, but nothing in the repo reads it',
        }))
      ),
      ...atSourceLine(offset, checkFencesOnPage(page, tables))
    );
  }
  return findings;
}

export function formatFinding(finding: SnippetFinding): string {
  return `${finding.sourcePath}:${finding.line}  ${finding.message}`;
}
