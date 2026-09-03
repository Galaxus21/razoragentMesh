"""The throwaway workspace, and the measurement of which test reaches which line.

Nothing here touches the working tree. The repository is copied once into a temp
directory (minus node_modules and friends) and every mutant is written there.

The coverage pass exists for speed with a side benefit in fairness. Without it each
mutant would need the whole 1,252-test suite -- a minute apiece, hours across a few
hundred mutants. With it a mutant runs only the tests that actually execute the line
it changed, and that selection is derived from measurement rather than a hand-picked
file list, so it neither flatters nor penalises the score.
"""

import json
import os
import shutil
import subprocess
import sys
from pathlib import Path
from typing import Dict, List, Optional, Set, Tuple

from .auditTargets import (
    coverageTimeoutSeconds, crossSdkDependencyPaths, excludedDirectoryNames,
    meshRoot, testTargets,
)

LineTestMap = Dict[Tuple[str, int], Set[str]]


# --- Workspace ---------------------------------------------------------------


def buildWorkspace(destinationRoot: Path) -> Path:
    """Copies the repository into a temp directory, minus the heavy directories.

    The package name is the directory name -- every backend module imports
    `razoragentMesh.packages.*` -- so the copy keeps that name and sits one level
    below a root that goes on sys.path.
    """
    workspaceMesh = destinationRoot / meshRoot.name

    def ignore(directory: str, names: List[str]) -> Set[str]:
        return {name for name in names if name in excludedDirectoryNames}

    shutil.copytree(meshRoot, workspaceMesh, ignore=ignore, symlinks=False)
    _restoreCrossSdkDependencies(workspaceMesh)
    return workspaceMesh


def _restoreCrossSdkDependencies(workspaceMesh: Path) -> None:
    """Copies back the one node_modules the Python suite genuinely needs.

    `tests/testCrossSdkTsPyCompatibility.py` shells out to Node to sign in
    TypeScript and verify in Python. Those six tests are the strongest oracle in
    the repository, so dropping them from the run to save a directory copy would
    quietly make the score less trustworthy. 42MB is a cheap price for keeping
    them in.
    """
    for relativePath in crossSdkDependencyPaths:
        source = meshRoot / relativePath
        if source.is_dir():
            shutil.copytree(source, workspaceMesh / relativePath, symlinks=False)


def runInWorkspace(
    command: List[str], workspaceMesh: Path, timeoutSeconds: int
) -> subprocess.CompletedProcess:
    """Runs a command inside the workspace copy with the parent directory importable."""
    environment = dict(os.environ)
    environment["PYTHONPATH"] = os.pathsep.join([str(workspaceMesh), str(workspaceMesh.parent)])
    environment["PYTHONDONTWRITEBYTECODE"] = "1"
    return subprocess.run(
        command,
        cwd=str(workspaceMesh),
        capture_output=True,
        text=True,
        encoding="utf-8",
        errors="replace",
        timeout=timeoutSeconds,
        env=environment,
    )


# --- Coverage-directed test selection ----------------------------------------


def measureCoverageContexts(workspaceMesh: Path, modulePaths: Tuple[str, ...]) -> LineTestMap:
    """Records which test function executes which line of the scored modules."""
    rcPath = _writeCoverageConfig(workspaceMesh, modulePaths)

    completed = runInWorkspace(
        [sys.executable, "-m", "coverage", "run", f"--rcfile={rcPath}",
         "-m", "pytest", *testTargets, "-q", "-p", "no:cacheprovider"],
        workspaceMesh,
        coverageTimeoutSeconds,
    )
    if "passed" not in completed.stdout:
        raise RuntimeError(
            "baseline suite did not report a pass line under coverage:\n"
            f"{completed.stdout[-3000:]}\n{completed.stderr[-2000:]}"
        )

    jsonPath = workspaceMesh / "coverage-contexts.json"
    runInWorkspace(
        [sys.executable, "-m", "coverage", "json", f"--rcfile={rcPath}",
         "--show-contexts", "-o", str(jsonPath)],
        workspaceMesh,
        coverageTimeoutSeconds,
    )
    return _parseContextReport(
        json.loads(jsonPath.read_text(encoding="utf-8")), buildTestModuleIndex(workspaceMesh)
    )


def _writeCoverageConfig(workspaceMesh: Path, modulePaths: Tuple[str, ...]) -> Path:
    """Writes a coverage config limited to the scored modules."""
    rcPath = workspaceMesh / ".coveragerc-mutation"
    includeLines = "\n".join(f"    {path}" for path in modulePaths)
    rcPath.write_text(
        "[run]\ndynamic_context = test_function\nbranch = False\ninclude =\n"
        f"{includeLines}\n",
        encoding="utf-8",
    )
    return rcPath


def _parseContextReport(report: dict, moduleIndex: Dict[str, str]) -> LineTestMap:
    """Turns coverage's contexts-per-line into pytest node ids per line."""
    lineToTests: LineTestMap = {}
    for rawPath, fileReport in report.get("files", {}).items():
        normalisedPath = rawPath.replace("\\", "/")
        for lineText, contexts in fileReport.get("contexts", {}).items():
            nodeIds = {
                nodeId
                for nodeId in (contextToNodeId(context, moduleIndex) for context in contexts)
                if nodeId
            }
            if nodeIds:
                lineToTests[(normalisedPath, int(lineText))] = nodeIds
    return lineToTests


def buildTestModuleIndex(workspaceMesh: Path) -> Dict[str, str]:
    """Maps a test module's bare name to its path, which is how contexts name it."""
    index: Dict[str, str] = {}
    for testRoot in testTargets:
        for testFile in (workspaceMesh / testRoot).rglob("test*.py"):
            index[testFile.stem] = testFile.relative_to(workspaceMesh).as_posix()
    return index


def contextToNodeId(context: str, moduleIndex: Dict[str, str]) -> Optional[str]:
    """Turns a coverage dynamic context into a pytest node id.

    Coverage names the executing test by module basename and qualname
    (`test_property_enclave_math.TestPropertyGstZeroDrift.test_case`), while pytest
    wants a path. The 119 test modules have no basename collisions, so the first
    segment resolves unambiguously. A parametrised test collapses to its function,
    which is what we want: selecting the function runs every parameter of it.
    """
    trimmed = context.split("|", 1)[0].strip()
    if not trimmed or "." not in trimmed:
        return None
    moduleName, _, qualName = trimmed.partition(".")
    modulePath = moduleIndex.get(moduleName)
    if not modulePath or not qualName:
        return None
    return modulePath + "::" + qualName.replace(".", "::")
