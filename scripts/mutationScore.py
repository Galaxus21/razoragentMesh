#!/usr/bin/env python3
"""
Measures how much of the test suite's protection is real, by mutating the
financial and security core and checking whether any test objects.

A passing suite proves the tests agree with the code. It does not prove the tests
would object if the code were wrong. This script asks the second question: it
introduces one small, plausible defect at a time and reports which ones the suite
fails to catch. Every survivor is a change that could be committed today with a
green build.

    python scripts/mutationScore.py            # measure and print
    python scripts/mutationScore.py --write    # sync docs/TEST_QUALITY_AUDIT.md
    python scripts/mutationScore.py --check    # fail if that document has drifted

What it cannot tell you: mutation testing only perturbs code that exists. A guard
that was never written has nothing to mutate, so a module can score 100% and still
accept input its author never considered. See the method section of
docs/TEST_QUALITY_AUDIT.md.

The working tree is never modified -- everything runs against a filtered copy of
the repository in a temporary directory.
"""

import argparse
import sys
import tempfile
from pathlib import Path
from typing import List

sys.path.insert(0, str(Path(__file__).resolve().parent))

from mutation.auditTargets import coreModulePaths  # noqa: E402
from mutation.mutantRunner import ModuleResult, evaluateModule  # noqa: E402
from mutation.scoreDocument import (  # noqa: E402
    checkBlockInDocuments, renderScoreBlock, writeBlockToDocuments,
)
from mutation.workspaceCoverage import buildWorkspace, measureCoverageContexts  # noqa: E402


def parseArguments() -> argparse.Namespace:
    parser = argparse.ArgumentParser(
        description="Measure the mutation score of the financial and security core."
    )
    parser.add_argument("--write", action="store_true", help="regenerate the block in the audit document")
    parser.add_argument("--check", action="store_true", help="exit non-zero if the document has drifted")
    parser.add_argument("--modules", nargs="*", default=None, help="limit the run to these module paths")
    return parser.parse_args()


def measureAllModules(modulePaths: tuple) -> List[ModuleResult]:
    """Builds the workspace, measures test reach, then scores every module."""
    with tempfile.TemporaryDirectory(prefix="razoragent-mutation-") as temporaryRoot:
        workspaceMesh = buildWorkspace(Path(temporaryRoot))
        print(f"workspace: {workspaceMesh}")
        print("measuring which test reaches which line ...")
        lineToTests = measureCoverageContexts(workspaceMesh, modulePaths)
        print(f"covered lines carrying a named test: {len(lineToTests)}")

        results: List[ModuleResult] = []
        for moduleOrdinal, modulePath in enumerate(modulePaths, start=1):
            prefix = f"[{moduleOrdinal}/{len(modulePaths)}] {Path(modulePath).name}"
            print(f"{prefix} ...")
            result = evaluateModule(workspaceMesh, modulePath, lineToTests, prefix)
            results.append(result)
            print(
                f"{prefix}: {result.killedCount}/{result.scoredCount} killed "
                f"({result.scorePercent:.1f}%), {len(result.survivors)} survived"
            )
    return results


def main() -> int:
    parsedArgs = parseArguments()
    modulePaths = tuple(parsedArgs.modules) if parsedArgs.modules else coreModulePaths

    results = measureAllModules(modulePaths)
    renderedBlock = renderScoreBlock(results)
    print()
    print(renderedBlock)

    if parsedArgs.write:
        return writeBlockToDocuments(renderedBlock)
    if parsedArgs.check:
        return checkBlockInDocuments(renderedBlock)
    return 0


if __name__ == "__main__":
    sys.exit(main())
