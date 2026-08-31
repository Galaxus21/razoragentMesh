// Resolves what the guides claim against what the generated reference records.
//
// This is the check the whole reference pipeline exists for. BUYER_AGENT_SDK_GUIDE documented
// buyerAgent.catalog.search(), buyerAgent.cart.create() and a {agentDid, privateKeyHex,
// gatewayUrl, maxDailyBudgetPaise} constructor -- none of which were ever implemented -- and
// nothing in the repository could tell. Every rule below exists because a specific published
// sentence was wrong in that way.
//
// The bias is towards silence: a construct the extractor cannot resolve produces no finding. A
// checker that fires on fragments would be turned off within a week, and then it would be
// checking nothing at all.

import type { CodeFence, SnippetFinding } from "@/types/docSnippetTypes";
import type { SnippetFacts } from "@/lib/reference/docSnippetExtractor";
import { type SymbolTable } from "@/lib/reference/referenceTables";

// A specifier naming the project but matching no real package is the `@razoragent/buyer-sdk-ts`
// class of error: an install line nobody could follow. Third-party and relative imports are none
// of this checker's business, which is why the test is for these markers rather than for
// "anything unrecognised".
const projectPackageMarkers = ["razoragent", "razorpay", "buyer-sdk", "buyer_sdk"];

const installCommandPattern = /\b(npm install|pip install)\s+([@\w./-]+)/g;

function namesTheProject(packageName: string): boolean {
  const lowered = packageName.toLowerCase();
  return projectPackageMarkers.some((marker) => lowered.includes(marker));
}

function finding(fence: CodeFence, message: string): SnippetFinding {
  return { sourcePath: fence.sourcePath, line: fence.line, message };
}

// Each installer is checked against the name its own registry would resolve, so `pip install
// @razorpay/agent-buyer-sdk` is a finding even though that string is a real package elsewhere.
function checkInstallCommands(
  fence: CodeFence,
  installerPackageNames: Readonly<Record<string, string>>
): readonly SnippetFinding[] {
  const findings: SnippetFinding[] = [];
  for (const match of fence.body.matchAll(installCommandPattern)) {
    const [, installer, requested] = match;
    const realName = installerPackageNames[installer];
    if (realName && namesTheProject(requested) && requested !== realName) {
      findings.push(
        finding(fence, `\`${installer} ${requested}\` -- the package is named ${realName}`)
      );
    }
  }
  return findings;
}

function checkImports(
  fence: CodeFence,
  facts: SnippetFacts,
  table: SymbolTable,
  knownPackageNames: ReadonlySet<string>
): readonly SnippetFinding[] {
  const findings: SnippetFinding[] = [];
  for (const importFact of facts.imports) {
    if (!namesTheProject(importFact.packageName)) {
      continue;
    }
    if (!knownPackageNames.has(importFact.packageName)) {
      findings.push(
        finding(fence, `imports from '${importFact.packageName}', which is not a real package`)
      );
      continue;
    }
    if (importFact.packageName !== table.packageName) {
      continue;
    }
    for (const name of importFact.names) {
      if (!table.exports.has(name)) {
        findings.push(
          finding(fence, `imports '${name}' from ${table.packageName}, which exports no such name`)
        );
      }
    }
  }
  return findings;
}

function checkConstructions(
  fence: CodeFence,
  facts: SnippetFacts,
  table: SymbolTable
): readonly SnippetFinding[] {
  const findings: SnippetFinding[] = [];
  for (const construction of facts.constructions) {
    const symbol = table.exports.get(construction.className);
    // An unknown class name is not reported here: the snippet may be constructing something from
    // the reader's own application. Imports are where a wrong SDK name gets caught.
    if (!symbol || symbol.constructorParameters.length === 0) {
      continue;
    }
    const accepted = new Set(symbol.constructorParameters);
    const unknown = construction.argumentNames.filter((name) => !accepted.has(name));
    // Reported as one finding rather than one per key: a constructor called with four names from
    // an older shape is one mistake, and four lines of the same sentence read as four.
    if (unknown.length > 0) {
      findings.push(
        finding(
          fence,
          `${construction.className} is constructed with ${unknown.join(", ")} -- it accepts ` +
            `${[...accepted].sort().join(", ")}`
        )
      );
    }
  }
  return findings;
}

// Only receivers whose type is known get their member accesses checked: a variable bound by
// `new RazorAgentClient(...)`, or a class name used directly for a static call.
//
// The map is threaded across a whole page rather than rebuilt per fence, because that is how the
// guides are written: section 2 constructs the client and section 6 calls a method on it. Scoped
// to one fence, the checker would have been blind to exactly the errors it exists to catch.
export function collectReceiverTypes(
  facts: SnippetFacts,
  table: SymbolTable,
  receiverTypes: Map<string, string>
): void {
  for (const construction of facts.constructions) {
    if (table.exports.has(construction.className)) {
      receiverTypes.set(construction.variable, construction.className);
    }
  }
  for (const access of facts.memberAccesses) {
    if (table.exports.has(access.receiver)) {
      receiverTypes.set(access.receiver, access.receiver);
    }
  }
}

function checkMemberAccesses(
  fence: CodeFence,
  facts: SnippetFacts,
  table: SymbolTable,
  receiverTypes: ReadonlyMap<string, string>
): readonly SnippetFinding[] {
  const findings: SnippetFinding[] = [];

  for (const access of facts.memberAccesses) {
    const className = receiverTypes.get(access.receiver);
    if (!className) {
      continue;
    }
    const members = table.memberNames.get(className);
    if (members && !members.has(access.member)) {
      findings.push(
        finding(
          fence,
          `${access.receiver}.${access.member} -- ${className} has no such member. It has: ` +
            `${[...members].sort().join(", ")}`
        )
      );
    }
  }
  return findings;
}

export interface CheckContext {
  readonly table: SymbolTable;
  readonly receiverTypes: ReadonlyMap<string, string>;
  readonly knownPackageNames: ReadonlySet<string>;
  readonly installerPackageNames: Readonly<Record<string, string>>;
}

export function checkFenceAgainstTable(
  fence: CodeFence,
  facts: SnippetFacts,
  { table, receiverTypes, knownPackageNames, installerPackageNames }: CheckContext
): readonly SnippetFinding[] {
  return [
    ...checkInstallCommands(fence, installerPackageNames),
    ...checkImports(fence, facts, table, knownPackageNames),
    ...checkConstructions(fence, facts, table),
    ...checkMemberAccesses(fence, facts, table, receiverTypes),
  ];
}
