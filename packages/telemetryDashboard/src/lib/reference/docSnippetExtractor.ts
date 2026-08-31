// Pulls the checkable facts out of a guide's code fences.
//
// This is deliberately not a parser. A snippet in prose is usually a fragment -- no imports, an
// undeclared variable, an elided body -- so anything that insisted on a valid program would
// reject most of the docs. What it does instead is find the few constructs that can be resolved
// against a symbol table with certainty: what was imported from where, what was constructed, and
// what was reached through a variable whose type is therefore known.
//
// Everything else is ignored on purpose. A member access on a receiver the extractor cannot type
// produces no finding, because guessing there would mean crying wolf on every fence in the docs.

import type { CodeFence, SnippetLanguage } from "@/types/docSnippetTypes";
import type { DocPage } from "@/types/docsTypes";

export interface ImportFact {
  readonly packageName: string;
  readonly names: readonly string[];
}

export interface ConstructionFact {
  readonly variable: string;
  readonly className: string;
  readonly argumentNames: readonly string[];
}

export interface MemberAccessFact {
  readonly receiver: string;
  readonly member: string;
}

export interface ServiceUrlFact {
  readonly key: string;
  readonly url: string;
}

export interface SnippetFacts {
  readonly imports: readonly ImportFact[];
  readonly constructions: readonly ConstructionFact[];
  readonly memberAccesses: readonly MemberAccessFact[];
  readonly serviceUrls: readonly ServiceUrlFact[];
}

const fencePattern = /^```(typescript|javascript|python)[^\n]*\n([\s\S]*?)^```/gm;
const typeScriptNamedImportPattern = /import\s*\{([^}]*)\}\s*from\s*["']([^"']+)["']/g;
const typeScriptDefaultImportPattern = /import\s+(\w+)\s+from\s*["']([^"']+)["']/g;
const pythonImportPattern = /from\s+([\w.]+)\s+import\s+\(?([^\n)]*)\)?/g;
const typeScriptConstructionPattern = /(?:const|let|var)\s+(\w+)\s*=\s*(?:await\s+)?new\s+(\w+)\s*\(/g;
const pythonConstructionPattern = /^\s*(\w+)\s*=\s*(?:await\s+)?([A-Z]\w*)\s*\(/gm;
const memberAccessPattern = /\b([A-Za-z_]\w*)\s*\.\s*([A-Za-z_]\w*)/g;
// Object-literal keys in TypeScript, keyword arguments in Python. Written as literals rather
// than composed at runtime: a template literal eats the backslashes.
const objectKeyPattern = /^\s*([A-Za-z_]\w*)\s*:/;
const keywordArgumentPattern = /^\s*([A-Za-z_]\w*)\s*=/;
const localhostUrlPattern = /https?:\/\/localhost:\d+/;
const commentPattern = /(^|\s)(\/\/|#)[^\n]*/g;

export function extractCodeFences(page: DocPage): readonly CodeFence[] {
  const fences: CodeFence[] = [];
  for (const match of page.body.matchAll(fencePattern)) {
    fences.push({
      slug: page.slug,
      sourcePath: page.sourcePath,
      // page.body has the frontmatter block removed, so the offset is added back by the caller's
      // source file only for display; the line here is relative to the body and good enough to
      // find the fence in an editor's search.
      line: page.body.slice(0, match.index).split("\n").length,
      language: match[1] as SnippetLanguage,
      body: match[2],
    });
  }
  return fences;
}

// Scans forward from an opening bracket and returns the text it encloses, so a nested object or
// call does not end the argument list early the way a non-greedy regex would.
function readBalanced(source: string, openIndex: number): string {
  const openBracket = source[openIndex];
  const closeBracket = openBracket === "(" ? ")" : "}";
  let depth = 0;
  for (let index = openIndex; index < source.length; index += 1) {
    if (source[index] === openBracket) {
      depth += 1;
    } else if (source[index] === closeBracket) {
      depth -= 1;
      if (depth === 0) {
        return source.slice(openIndex + 1, index);
      }
    }
  }
  return source.slice(openIndex + 1);
}

// TypeScript's arguments arrive wrapped in an options object, Python's do not. Scanning from the
// brace rather than the parenthesis puts both languages' named arguments at the same nesting
// depth, so one scanner reads both -- and a nested call's own arguments are never mistaken for
// the outer one's.
function readArgumentStart(source: string, openIndex: number): number {
  for (let index = openIndex + 1; index < source.length; index += 1) {
    if (source[index] === "{") {
      return index;
    }
    if (!/\s/.test(source[index])) {
      return openIndex;
    }
  }
  return openIndex;
}

// Names the caller passed: object-literal keys for TypeScript, keyword arguments for Python.
// Only at the top level -- a key nested inside a value belongs to that value's own shape.
function readArgumentNames(argumentText: string, namePattern: RegExp): readonly string[] {
  const names: string[] = [];
  let depth = 0;
  let lineStart = 0;

  for (let index = 0; index <= argumentText.length; index += 1) {
    const character = argumentText[index];
    if (character === "{" || character === "(" || character === "[") {
      // Deliberately not the start of a new segment. `config=MeshSlaConfig(mcpBaseUrl=...)` is
      // one argument named config, and resetting here would name it mcpBaseUrl instead -- the
      // inner call's own keyword read as the outer call's. The leading brace of a TypeScript
      // options object is already gone, because readArgumentStart began the scan inside it.
      depth += 1;
    } else if (character === "}" || character === ")" || character === "]") {
      depth -= 1;
    } else if ((character === "," || character === "\n" || index === argumentText.length) && depth === 0) {
      const match = namePattern.exec(argumentText.slice(lineStart, index));
      if (match) {
        names.push(match[1]);
      }
      lineStart = index + 1;
    }
  }
  return [...new Set(names)];
}

function readServiceUrls(argumentText: string): readonly ServiceUrlFact[] {
  const urls: ServiceUrlFact[] = [];
  const entryPattern = /([A-Za-z_]\w*)\s*[:=]\s*["'](https?:\/\/[^"']+)["']/g;
  for (const match of argumentText.matchAll(entryPattern)) {
    if (localhostUrlPattern.test(match[2])) {
      urls.push({ key: match[1], url: match[2] });
    }
  }
  return urls;
}

function collectConstructions(
  body: string,
  pattern: RegExp
): { constructions: ConstructionFact[]; serviceUrls: ServiceUrlFact[] } {
  const constructions: ConstructionFact[] = [];
  const serviceUrls: ServiceUrlFact[] = [];
  const namePattern =
    pattern === pythonConstructionPattern ? keywordArgumentPattern : objectKeyPattern;

  for (const match of body.matchAll(pattern)) {
    const openIndex = match.index + match[0].length - 1;
    const argumentText = readBalanced(body, readArgumentStart(body, openIndex));
    constructions.push({
      variable: match[1],
      className: match[2],
      argumentNames: readArgumentNames(argumentText, namePattern),
    });
    serviceUrls.push(...readServiceUrls(argumentText));
  }
  return { constructions, serviceUrls };
}

function collectImports(body: string, language: SnippetLanguage): readonly ImportFact[] {
  const splitNames = (text: string): readonly string[] =>
    text
      .split(",")
      .map((name) => name.trim().split(/\s+as\s+/)[0].trim())
      .filter((name) => name.length > 0 && name !== "*");

  if (language === "python") {
    return [...body.matchAll(pythonImportPattern)].map((match) => ({
      packageName: match[1],
      names: splitNames(match[2]),
    }));
  }

  return [
    ...[...body.matchAll(typeScriptNamedImportPattern)].map((match) => ({
      packageName: match[2],
      names: splitNames(match[1]),
    })),
    ...[...body.matchAll(typeScriptDefaultImportPattern)].map((match) => ({
      packageName: match[2],
      names: [match[1]],
    })),
  ];
}

export function extractSnippetFacts(fence: CodeFence): SnippetFacts {
  // Comments are stripped first: a prose aside inside a snippet ("// call client.doThing()") is
  // illustration, and holding it to the same standard as code would be pedantry.
  const body = fence.body.replace(commentPattern, "$1");
  const constructionPattern =
    fence.language === "python" ? pythonConstructionPattern : typeScriptConstructionPattern;
  const { constructions, serviceUrls } = collectConstructions(body, constructionPattern);

  return {
    imports: collectImports(body, fence.language),
    constructions,
    memberAccesses: [...body.matchAll(memberAccessPattern)].map((match) => ({
      receiver: match[1],
      member: match[2],
    })),
    serviceUrls,
  };
}
