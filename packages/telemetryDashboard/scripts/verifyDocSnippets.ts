// Exits non-zero when a guide names something that does not exist.
//
// Run by hand -- `npm run docs:verify` from packages/telemetryDashboard -- after regenerating the
// reference artifacts, so a rename in the SDK surfaces while you still remember renaming it
// rather than as a support question months later. This repository has no CI by choice.
// Regenerate the artifacts first: npm run docs:reference && python scripts/generateApiReference.py

import { formatFinding, verifyDocSnippets } from "../src/lib/reference/docSnippetVerifier.js";

const findings = verifyDocSnippets();

if (findings.length === 0) {
  process.stdout.write("Documentation snippets resolve against the generated reference.\n");
  process.exit(0);
}

process.stderr.write(`${findings.length} documentation snippet(s) name something that does not exist:\n\n`);
for (const finding of findings) {
  process.stderr.write(`  ${formatFinding(finding)}\n`);
}
process.stderr.write(
  "\nEither fix the guide or regenerate the reference if the code changed:\n" +
    "  npm run docs:reference && python scripts/generateApiReference.py\n"
);
process.exit(1);
