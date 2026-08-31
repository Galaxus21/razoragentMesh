#!/usr/bin/env python3
"""
Measures the test count of every suite in the monorepo and writes it into the
documents that quote it, so no test count is ever hand-typed.

Rule V-01 (verification-standards.md) requires every quantitative claim to carry the
command that produced it. The generated block therefore embeds each command next to
its number, and `--check` fails CI the moment a document drifts from measurement.
"""

import argparse
import re
import subprocess
import sys
from dataclasses import dataclass
from pathlib import Path
from typing import Dict, List, Optional

# --- Types -------------------------------------------------------------------


@dataclass(frozen=True)
class SuiteResult:
    suiteName: str
    command: str
    testCount: int
    failCount: int


# --- Constants ---------------------------------------------------------------

meshRoot: Path = Path(__file__).resolve().parent.parent
workspaceRoot: Path = meshRoot.parent

blockStartMarker: str = "<!-- testcounts:start -->"
blockEndMarker: str = "<!-- testcounts:end -->"

pythonSuiteName: str = "Python backend + Python Buyer SDK"
pythonSuiteCommand: str = "python -m pytest tests/ packages/buyerSdkPy/tests/ --collect-only -q"

nodeSuiteNames: Dict[str, str] = {
    "mcpServer": "MCP discovery server",
    "buyerSdkTs": "TypeScript Buyer SDK",
    "telemetryDashboard": "Telemetry dashboard + SKU Studio",
}
nodeSuiteCommand: str = "npm test"
nodeSummaryKeys = ("tests", "pass", "fail")

documentedFilePaths: List[Path] = [
    meshRoot / "README.md",
    meshRoot / "GUIDE.md",
]

# Lives in the outer workspace, which is a separate (untracked) directory that CI never checks
# out. Synchronised when it is there, so local runs keep it honest; skipped when it is not, rather
# than failing the build over a file this repository cannot contain.
optionalFilePaths: List[Path] = [
    workspaceRoot / ".agents" / "rules" / "project-knowledge-base.md",
]

pytestCollectedPattern = re.compile(r"(\d+)\s+tests?\s+collected")
commandTimeoutSeconds: int = 900


# --- Entry point -------------------------------------------------------------


def main() -> int:
    parser = argparse.ArgumentParser(description="Measure and synchronise monorepo test counts.")
    parser.add_argument("--write", action="store_true", help="regenerate the block in every document")
    parser.add_argument("--check", action="store_true", help="exit non-zero if any document has drifted")
    parsedArgs = parser.parse_args()

    results = measureAllSuites()
    renderedBlock = renderCountsBlock(results)
    print(renderedBlock)

    failingSuites = [result for result in results if result.failCount > 0]
    for result in failingSuites:
        print(f"FAIL: {result.suiteName} reported {result.failCount} failing tests", file=sys.stderr)
    if failingSuites:
        return 1

    if parsedArgs.write:
        return writeBlockToDocuments(renderedBlock)
    if parsedArgs.check:
        return checkBlockInDocuments(renderedBlock)
    return 0


# --- Measurement -------------------------------------------------------------


def measureAllSuites() -> List[SuiteResult]:
    results = [measurePythonSuite()]
    results.extend(measureNodeSuite(packageName) for packageName in nodeSuiteNames)
    return results


def measurePythonSuite() -> SuiteResult:
    """Collection only -- pytest never executes here, so this stays fast in CI."""
    output = runCommand(pythonSuiteCommand, meshRoot)
    match = pytestCollectedPattern.search(output)
    if not match:
        raise RuntimeError(f"could not parse a collected count from:\n{output[-2000:]}")
    return SuiteResult(pythonSuiteName, pythonSuiteCommand, int(match.group(1)), 0)


def measureNodeSuite(packageName: str) -> SuiteResult:
    """`node --test` has no collect-only mode, so these suites do execute."""
    output = runCommand(nodeSuiteCommand, meshRoot / "packages" / packageName)
    summary = parseNodeSummary(output)
    if "tests" not in summary:
        raise RuntimeError(f"could not parse a test summary from {packageName}:\n{output[-2000:]}")
    return SuiteResult(
        nodeSuiteNames[packageName],
        f"cd packages/{packageName} && {nodeSuiteCommand}",
        summary["tests"],
        summary.get("fail", 0),
    )


def parseNodeSummary(output: str) -> Dict[str, int]:
    """
    Summary lines are `<marker> tests 130`. The marker varies by reporter and host --
    a symbol under the spec reporter, '#' under TAP, and a literal backslash-u escape
    when node cannot encode the symbol for a Windows console -- so match on the trailing
    `<keyword> <integer>` pair instead of trying to describe every possible prefix.
    """
    summary: Dict[str, int] = {}
    for line in output.splitlines():
        fields = line.split()
        if len(fields) < 2 or fields[-2] not in nodeSummaryKeys or not fields[-1].isdigit():
            continue
        summary[fields[-2]] = int(fields[-1])
    return summary


def runCommand(command: str, workingDir: Path) -> str:
    completed = subprocess.run(
        command,
        cwd=str(workingDir),
        shell=True,
        capture_output=True,
        text=True,
        encoding="utf-8",
        errors="replace",
        timeout=commandTimeoutSeconds,
    )
    return f"{completed.stdout}\n{completed.stderr}"


# --- Rendering ---------------------------------------------------------------


def renderCountsBlock(results: List[SuiteResult]) -> str:
    totalCount = sum(result.testCount for result in results)
    lines = [
        blockStartMarker,
        "<!-- Generated by scripts/countTests.py -- do not edit by hand. -->",
        "",
        "| Suite | Tests | Command that produced this number |",
        "|---|---:|---|",
    ]
    lines.extend(
        f"| {result.suiteName} | {result.testCount} | `{result.command}` |" for result in results
    )
    lines.extend(
        [
            f"| **Total** | **{totalCount:,}** | `python scripts/countTests.py` |",
            "",
            blockEndMarker,
        ]
    )
    return "\n".join(lines)


# --- Document synchronisation ------------------------------------------------


def resolveDocumentPaths() -> List[Path]:
    """Every required document, plus the optional ones that are actually present."""
    resolved = list(documentedFilePaths)
    for documentPath in optionalFilePaths:
        if documentPath.exists():
            resolved.append(documentPath)
        else:
            print(f"skipping {documentPath.name}: outside this repository and not checked out")
    return resolved


def writeBlockToDocuments(renderedBlock: str) -> int:
    for documentPath in resolveDocumentPaths():
        updatedText = replaceBlock(documentPath.read_text(encoding="utf-8"), renderedBlock)
        if updatedText is None:
            print(f"ERROR: {documentPath} has no {blockStartMarker} block", file=sys.stderr)
            return 1
        documentPath.write_text(updatedText, encoding="utf-8")
        print(f"updated {documentPath.relative_to(workspaceRoot)}")
    return 0


def checkBlockInDocuments(renderedBlock: str) -> int:
    hasDrifted = False
    for documentPath in resolveDocumentPaths():
        existingBlock = extractBlock(documentPath.read_text(encoding="utf-8"))
        if existingBlock is None:
            print(f"ERROR: {documentPath} has no {blockStartMarker} block", file=sys.stderr)
            hasDrifted = True
            continue
        if existingBlock.strip() != renderedBlock.strip():
            print(f"DRIFT: {documentPath} disagrees with measurement", file=sys.stderr)
            hasDrifted = True
    if hasDrifted:
        print("\nRun `python scripts/countTests.py --write` to resynchronise.", file=sys.stderr)
        return 1
    print("OK: every documented test count matches measurement.")
    return 0


def extractBlock(text: str) -> Optional[str]:
    startIndex = text.find(blockStartMarker)
    endIndex = text.find(blockEndMarker)
    if startIndex == -1 or endIndex == -1:
        return None
    return text[startIndex : endIndex + len(blockEndMarker)]


def replaceBlock(text: str, renderedBlock: str) -> Optional[str]:
    existingBlock = extractBlock(text)
    if existingBlock is None:
        return None
    return text.replace(existingBlock, renderedBlock)


if __name__ == "__main__":
    sys.exit(main())
