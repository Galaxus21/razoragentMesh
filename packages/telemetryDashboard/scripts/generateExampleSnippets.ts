// Writes generated/exampleSnippets.json from the runnable programs in examples/.
//
// The examples live at the repository root, next to the packages they import; the dashboard's
// Docker build only copies this package. Rather than reach outside the build context at render
// time -- which works locally and fails in the image -- the regions are extracted here and
// committed, exactly as the SDK reference artifacts in the same directory are. CI regenerates and
// fails on any diff, so an edited example that was not re-synced cannot ship.

import fs from "node:fs";
import path from "node:path";
import { fileURLToPath } from "node:url";
import { extractExampleRegions, type ExampleSource } from "../src/lib/reference/exampleRegions.js";

const currentDirectory = path.dirname(fileURLToPath(import.meta.url));
const packageRoot = path.resolve(currentDirectory, "..");
const repositoryRoot = path.resolve(packageRoot, "..", "..");
const examplesDirectory = path.join(repositoryRoot, "examples");
const outputPath = path.join(packageRoot, "generated", "exampleSnippets.json");

const languageByExtension: Record<string, string> = {
  ".ts": "typescript",
  ".py": "python",
};

function collectExampleFiles(directory: string): readonly string[] {
  const found: string[] = [];
  for (const entry of fs.readdirSync(directory, { withFileTypes: true })) {
    const entryPath = path.join(directory, entry.name);
    if (entry.isDirectory()) {
      found.push(...collectExampleFiles(entryPath));
    } else if (path.extname(entry.name) in languageByExtension) {
      found.push(entryPath);
    }
  }
  return found.sort();
}

function readExampleSource(filePath: string): ExampleSource {
  // Forward slashes regardless of platform: the path is an MDX attribute a human types, and it
  // would otherwise read differently depending on which machine last ran the generator.
  const relativePath = path.relative(repositoryRoot, filePath).split(path.sep).join("/");
  return {
    path: relativePath,
    language: languageByExtension[path.extname(filePath)],
    regions: extractExampleRegions(fs.readFileSync(filePath, "utf-8")),
  };
}

function main(): void {
  const sources = collectExampleFiles(examplesDirectory).map(readExampleSource);
  const regionCount = sources.reduce((total, source) => total + source.regions.length, 0);
  if (regionCount === 0) {
    throw new Error(`Refusing to write an empty snippet table: no regions found in ${examplesDirectory}`);
  }

  fs.mkdirSync(path.dirname(outputPath), { recursive: true });
  fs.writeFileSync(outputPath, `${JSON.stringify(sources, null, 2)}\n`, "utf-8");
  process.stdout.write(
    `Wrote ${regionCount} regions from ${sources.length} examples to ` +
      `${path.relative(packageRoot, outputPath)}\n`
  );
}

main();
