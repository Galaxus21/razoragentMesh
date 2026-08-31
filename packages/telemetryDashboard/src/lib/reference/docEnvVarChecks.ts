// Checks that every environment variable the setup guide tells you to set is one the code reads.
//
// Twelve of them were not. `ED25519_PRIVATE_KEY` was the costly one: it reads exactly like the way
// to supply a signing key, and the code has always read `MERCHANT_PRIVATE_KEY_HEX`. Setting it did
// nothing, silently, and the mesh carried on with its development default -- so the failure mode
// was not a crash but every install sharing one key.
//
// "Read" is judged loosely on purpose: a name counts if it appears anywhere in the source, because
// several are reached indirectly through a constant (`process.env[httpPortEnvVar]`) and a checker
// that only understood `process.env.NAME` would have reported live variables as dead. The loose
// test still catches every real case, since a variable nothing reads appears nowhere at all.

import fs from "node:fs";
import path from "node:path";

export interface DocumentedEnvVar {
  readonly name: string;
  readonly sourcePath: string;
  readonly line: number;
}

// SCREAMING_SNAKE_CASE assignments inside a bash fence: `MERCHANT_PRIVATE_KEY_HEX=ac26...`
const envAssignmentPattern = /^([A-Z][A-Z0-9_]{2,})=/gm;
const bashFencePattern = /^```(?:bash|sh|dotenv)[^\n]*\n([\s\S]*?)^```/gm;
// Any SCREAMING_SNAKE token in source, however it is reached.
const envNamePattern = /\b([A-Z][A-Z0-9_]{2,})\b/g;

// Variables that belong to the toolchain rather than to this repo. A guide telling you to run
// `PYTHONPATH=packages/buyerSdkPy python ...` is describing how to invoke an interpreter, not
// declaring configuration the mesh reads, so holding it to the same standard would be pedantry.
const toolchainEnvVars = new Set([
  "PYTHONPATH",
  "PATH",
  "NODE_ENV",
  "NODE_OPTIONS",
  "HOME",
  "CI",
]);

const sourceExtensions = new Set([".ts", ".tsx", ".py", ".yml", ".yaml"]);
const skippedDirectories = new Set(["node_modules", ".next", "dist", "__pycache__", ".git", "generated"]);

function resolveRepositoryRoot(): string {
  return path.resolve(process.cwd(), "..", "..");
}

export function collectDocumentedEnvVars(docBody: string, sourcePath: string): readonly DocumentedEnvVar[] {
  const found: DocumentedEnvVar[] = [];
  for (const fence of docBody.matchAll(bashFencePattern)) {
    const fenceStartLine = docBody.slice(0, fence.index).split("\n").length;
    for (const assignment of fence[1].matchAll(envAssignmentPattern)) {
      found.push({
        name: assignment[1],
        sourcePath,
        line: fenceStartLine + fence[1].slice(0, assignment.index).split("\n").length,
      });
    }
  }
  return found;
}

function collectSourceFiles(directory: string, collected: string[]): void {
  for (const entry of fs.readdirSync(directory, { withFileTypes: true })) {
    if (entry.isDirectory()) {
      if (!skippedDirectories.has(entry.name)) {
        collectSourceFiles(path.join(directory, entry.name), collected);
      }
    } else if (sourceExtensions.has(path.extname(entry.name))) {
      collected.push(path.join(directory, entry.name));
    }
  }
}

let cachedNames: ReadonlySet<string> | undefined;

// Every SCREAMING_SNAKE token appearing anywhere in the repo's source or compose file.
export function collectEnvNamesUsedInSource(): ReadonlySet<string> {
  if (cachedNames) {
    return cachedNames;
  }
  const root = resolveRepositoryRoot();
  const files: string[] = [];
  collectSourceFiles(path.join(root, "packages"), files);
  const composePath = path.join(root, "docker-compose.yml");
  if (fs.existsSync(composePath)) {
    files.push(composePath);
  }

  const names = new Set<string>();
  for (const file of files) {
    // The guides themselves are the thing under test, so they are not evidence of use.
    if (file.includes(`${path.sep}docs${path.sep}`)) {
      continue;
    }
    for (const match of fs.readFileSync(file, "utf-8").matchAll(envNamePattern)) {
      names.add(match[1]);
    }
  }
  cachedNames = names;
  return names;
}

export function findUnreadEnvVars(
  documented: readonly DocumentedEnvVar[]
): readonly DocumentedEnvVar[] {
  const used = collectEnvNamesUsedInSource();
  return documented.filter(
    (variable) => !used.has(variable.name) && !toolchainEnvVars.has(variable.name)
  );
}
