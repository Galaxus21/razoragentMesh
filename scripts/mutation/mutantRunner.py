"""Runs one mutant at a time and records whether any test objected."""

import subprocess
import sys
from dataclasses import dataclass, field
from pathlib import Path
from typing import List, Set, Tuple

from .auditTargets import (
    collectionErrorExitCodes, detailCollectionError, detailTimeout,
    diagnosticExcerptLength, exitCodeAllPassed, exitCodeNoTestsCollected,
    exitCodeTestsFailed, maxCommandLength, mutantTimeoutSeconds, outcomeError,
    outcomeKilled, outcomeSurvived, unknownTestIdMarker,
)
from .mutationOperators import (
    Mutant, generateMutants, renderMutantSource, renderNormalisedSource,
)
from .workspaceCoverage import LineTestMap, runInWorkspace


@dataclass
class ModuleResult:
    """Mutation outcome for one source module."""

    modulePath: str
    killedCount: int = 0
    timeoutCount: int = 0
    collectionErrorCount: int = 0
    survivors: List[Mutant] = field(default_factory=list)
    uncoveredMutants: List[Mutant] = field(default_factory=list)

    @property
    def scoredCount(self) -> int:
        return self.killedCount + len(self.survivors)

    @property
    def scorePercent(self) -> float:
        if self.scoredCount == 0:
            return 0.0
        return 100.0 * self.killedCount / self.scoredCount


def selectTestArguments(nodeIds: Set[str]) -> List[str]:
    """Chooses pytest targets, collapsing to whole files if the id list is too long.

    A hot line can be covered by hundreds of tests, and Windows caps a command line
    near 32k characters. Past the threshold the node ids reduce to their unique
    files: coarser, but still derived from measurement -- it never selects a file
    that no covering test lives in.
    """
    ordered = sorted(nodeIds)
    if sum(len(nodeId) + 1 for nodeId in ordered) <= maxCommandLength:
        return ordered
    return sorted({nodeId.split("::", 1)[0] for nodeId in ordered})


def runSelectedTests(workspaceMesh: Path, nodeIds: Set[str]) -> Tuple[str, str]:
    """Runs the selected tests against whatever is currently on disk."""
    if not nodeIds:
        return outcomeError, "no tests were selected"
    command = [
        sys.executable, "-m", "pytest", *selectTestArguments(nodeIds),
        "-x", "-q", "--no-header", "-p", "no:cacheprovider",
    ]
    try:
        completed = runInWorkspace(command, workspaceMesh, mutantTimeoutSeconds)
    except subprocess.TimeoutExpired:
        # A mutant that hangs the suite would hang any run of it, so the suite does
        # register it -- but it is counted apart from a clean assertion failure.
        return outcomeKilled, detailTimeout

    if completed.returncode == exitCodeAllPassed:
        return outcomeSurvived, ""
    if completed.returncode == exitCodeTestsFailed:
        return outcomeKilled, ""
    if completed.returncode == exitCodeNoTestsCollected:
        return outcomeError, "no tests collected for the selected ids"
    return _classifyUnexpectedExit(completed)


def _classifyUnexpectedExit(completed: subprocess.CompletedProcess) -> Tuple[str, str]:
    """Decides whether an unusual exit code is the mutant's doing or the harness's.

    A mutant can leave the module un-importable, and pytest then fails during
    collection rather than in an assertion. The suite has still objected -- the run goes
    red -- so it counts as killed. It is counted apart from an assertion failure
    because nothing about the tests' *strength* caught it: any test at all would
    have. A node id the harness invented is a different matter entirely, and must
    stop the run rather than be quietly scored as a kill.

    That last check reads both streams deliberately. Pytest reports `not found:` on
    *stderr* and exits 4, which is also in `collectionErrorExitCodes` -- so looking
    only at stdout would let a mis-selected node id fall through and be scored as a
    kill, silently inflating the very number this harness exists to produce.
    """
    combinedOutput = f"{completed.stdout}\n{completed.stderr}"
    if unknownTestIdMarker in combinedOutput:
        return outcomeError, f"harness selected an unknown test id:\n{combinedOutput[-diagnosticExcerptLength:]}"
    if completed.returncode in collectionErrorExitCodes:
        return outcomeKilled, detailCollectionError
    return outcomeError, (
        f"pytest exit {completed.returncode}:\n{combinedOutput[-diagnosticExcerptLength:]}"
    )


def _testsCoveringModule(modulePath: str, lineToTests: LineTestMap) -> Set[str]:
    """Every test that reaches any line of the module.

    Used for module-level statements, which execute at import time and so carry no
    test context of their own, and as the fallback whenever a line has none.
    """
    covering: Set[str] = set()
    for (filePath, _lineNumber), nodeIds in lineToTests.items():
        if filePath == modulePath:
            covering |= nodeIds
    return covering


def _assertRoundTripPasses(workspaceMesh: Path, targetFile: Path, source: str, tests: Set[str]) -> None:
    """Confirms the unparsed but unmutated module still passes.

    Mutants are written as unparsed source. If normalising the file were by itself
    enough to break a test, every later result would be meaningless.
    """
    targetFile.write_text(renderNormalisedSource(source), encoding="utf-8")
    outcome, detail = runSelectedTests(workspaceMesh, tests)
    if outcome != outcomeSurvived:
        raise RuntimeError(
            f"{targetFile.name}: unmutated round-trip does not pass "
            f"({outcome} {detail}) -- results would be invalid"
        )


def evaluateModule(
    workspaceMesh: Path, modulePath: str, lineToTests: LineTestMap, progressPrefix: str
) -> ModuleResult:
    """Generates and runs every mutant for one module, restoring the file after."""
    targetFile = workspaceMesh / modulePath
    originalSource = targetFile.read_text(encoding="utf-8")
    moduleTests = _testsCoveringModule(modulePath, lineToTests)
    result = ModuleResult(modulePath=modulePath)
    mutants = generateMutants(modulePath, originalSource)

    try:
        _assertRoundTripPasses(workspaceMesh, targetFile, originalSource, moduleTests)
        for ordinal, mutant in enumerate(mutants, start=1):
            _evaluateMutant(workspaceMesh, targetFile, originalSource, mutant, lineToTests, moduleTests, result)
            print(
                f"{progressPrefix} {ordinal}/{len(mutants)} "
                f"killed={result.killedCount} survived={len(result.survivors)}",
                end="\r", flush=True,
            )
    finally:
        targetFile.write_text(originalSource, encoding="utf-8")

    print(" " * 78, end="\r")
    return result


def _evaluateMutant(
    workspaceMesh: Path, targetFile: Path, originalSource: str, mutant: Mutant,
    lineToTests: LineTestMap, moduleTests: Set[str], result: ModuleResult,
) -> None:
    """Runs a single mutant and files the outcome onto the module result."""
    selected = lineToTests.get((mutant.modulePath, mutant.lineNumber)) or moduleTests
    if not selected:
        result.uncoveredMutants.append(mutant)
        return

    targetFile.write_text(renderMutantSource(originalSource, mutant), encoding="utf-8")
    outcome, detail = runSelectedTests(workspaceMesh, selected)
    if outcome == outcomeKilled:
        result.killedCount += 1
        if detail == detailTimeout:
            result.timeoutCount += 1
        elif detail == detailCollectionError:
            result.collectionErrorCount += 1
    elif outcome == outcomeSurvived:
        result.survivors.append(mutant)
    else:
        raise RuntimeError(f"{mutant.modulePath} site {mutant.siteIndex}: {detail}")
