// Cuts named regions out of the runnable examples so prose can quote code it cannot invalidate.
//
// A fence pasted into a guide is a copy, and copies drift -- that is the whole reason the checker
// in this directory exists. A region is not a copy: `examples/` is compiled and executed by
// `python scripts/verifyExamples.py`,
// and the guide renders whatever that file currently says. The failure mode inverts, too. A
// pasted fence that names a deleted method renders happily and misleads the reader; a region that
// no longer exists throws here, at build time, naming the file and the region.
//
// Both marker styles are the ones each language's tooling already folds on, so the examples stay
// navigable in an editor rather than being littered with markup invented for the docs site.

export interface ExampleRegion {
  readonly name: string;
  readonly code: string;
}

export interface ExampleSource {
  readonly path: string;
  readonly language: string;
  readonly regions: readonly ExampleRegion[];
}

// `// #region cart` in TypeScript, `# region cart` in Python. The name is required: an unnamed
// region cannot be addressed from an MDX attribute, so there is no reason to accept one.
const regionStartPattern = /^\s*(?:\/\/|#)\s*#?region\s+(\w+)\s*$/;
const regionEndPattern = /^\s*(?:\/\/|#)\s*#?endregion(?:\s+\w+)?\s*$/;
const lineBreakPattern = /\r?\n/;
const blankLinePattern = /^\s*$/;

// A region lifted out of a function body arrives indented. Rendering it that way would put every
// line of a quoted block four or eight columns in for no reason, so the common indent comes off.
function removeCommonIndent(lines: readonly string[]): readonly string[] {
  const indents = lines
    .filter((line) => !blankLinePattern.test(line))
    .map((line) => line.length - line.trimStart().length);
  const commonIndent = indents.length > 0 ? Math.min(...indents) : 0;
  return lines.map((line) => line.slice(commonIndent));
}

function trimBlankEdges(lines: readonly string[]): readonly string[] {
  let start = 0;
  let end = lines.length;
  while (start < end && blankLinePattern.test(lines[start])) {
    start += 1;
  }
  while (end > start && blankLinePattern.test(lines[end - 1])) {
    end -= 1;
  }
  return lines.slice(start, end);
}

export function extractExampleRegions(source: string): readonly ExampleRegion[] {
  const regions: ExampleRegion[] = [];
  let openName: string | undefined;
  let collected: string[] = [];

  for (const line of source.split(lineBreakPattern)) {
    const start = regionStartPattern.exec(line);
    if (start) {
      if (openName) {
        throw new Error(`Region ${openName} is still open where region ${start[1]} begins`);
      }
      openName = start[1];
      collected = [];
      continue;
    }
    if (openName && regionEndPattern.test(line)) {
      regions.push({ name: openName, code: trimBlankEdges(removeCommonIndent(collected)).join("\n") });
      openName = undefined;
      continue;
    }
    if (openName) {
      collected.push(line);
    }
  }

  if (openName) {
    throw new Error(`Region ${openName} is never closed`);
  }
  return regions;
}

export function findExampleRegion(
  sources: readonly ExampleSource[],
  filePath: string,
  regionName: string
): ExampleRegion & { readonly language: string } {
  const source = sources.find((candidate) => candidate.path === filePath);
  if (!source) {
    throw new Error(
      `<Snippet> names ${filePath}, which is not a generated example. Available: ` +
        sources.map((candidate) => candidate.path).join(", ")
    );
  }
  const region = source.regions.find((candidate) => candidate.name === regionName);
  if (!region) {
    throw new Error(
      `${filePath} has no region "${regionName}". It has: ` +
        source.regions.map((candidate) => candidate.name).join(", ")
    );
  }
  return { ...region, language: source.language };
}
