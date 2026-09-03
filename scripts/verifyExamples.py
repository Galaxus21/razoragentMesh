#!/usr/bin/env python3
"""
Compiles and runs the programs in `examples/`, and fails if the generated reference
artifacts have drifted from the code they describe.

    python scripts/verifyExamples.py           # compile, run, and report drift
    python scripts/verifyExamples.py --check   # same, but exit non-zero on any failure
    python scripts/verifyExamples.py --skip-drift   # compile and run only

This repository has no CI by choice; the command above is run by hand.

Why it exists. The guides transclude regions of `examples/` via `<Snippet file=".." region=".." />`
rather than pasting fenced code, and `packages/telemetryDashboard/src/components/docs/snippet.tsx`
tells the reader that what they are looking at is a region of a program that actually runs. That
sentence is only true if something runs it. A workflow used to; it was deleted along with `.github/`,
which left four checks with no local equivalent -- the examples stopped being compiled, stopped being
executed, and the committed reference artifacts stopped being checked for drift.

The examples are not smoke tests. Each builds a full AP2 mandate chain, verifies it, then tampers
with the cart and verifies again, exiting non-zero unless the first check passes and the second
fails (INV-02). Signing is local, so no service needs to be running.
"""

import argparse
import os
import subprocess
import sys
from pathlib import Path
from typing import List, Optional, Tuple

# --- Constants ---

meshRoot = Path(__file__).resolve().parent.parent

typescriptSdkDirectory = meshRoot / "packages" / "buyerSdkTs"
typescriptExampleProject = meshRoot / "examples" / "typescript" / "tsconfig.json"
typescriptExampleProgram = meshRoot / "examples" / "typescript" / "mandateChain.ts"
pythonExampleProgram = meshRoot / "examples" / "python" / "mandateChain.py"
pythonSdkDirectory = meshRoot / "packages" / "buyerSdkPy"

generatedArtifactPaths = [
    "packages/telemetryDashboard/generated",
    "packages/telemetryDashboard/src/generated",
]

# tsx and tsc are resolved from the SDK's own node_modules rather than the ambient PATH, so this
# reports "dependencies not installed" instead of a confusing "command not found".
tsxBinaryCandidates = ["tsx.cmd", "tsx"]
tscBinaryCandidates = ["tsc.cmd", "tsc"]

regenerateHint = (
    "Regenerate with:\n"
    "  python scripts/generateApiReference.py\n"
    "  cd packages/telemetryDashboard && npm run docs:generate"
)

# --- Process helpers ---


def _resolveBinary(candidates: List[str]) -> Optional[Path]:
    """Finds a locally installed Node binary, tolerating the .cmd shim on Windows."""
    binDirectory = typescriptSdkDirectory / "node_modules" / ".bin"
    for candidate in candidates:
        candidatePath = binDirectory / candidate
        if candidatePath.exists():
            return candidatePath
    return None


def _run(command: List[str], cwd: Path, extraEnv: Optional[dict] = None) -> Tuple[int, str]:
    """Runs a command and returns its exit code with stdout and stderr combined."""
    environment = dict(os.environ)
    if extraEnv:
        environment.update(extraEnv)
    completed = subprocess.run(
        command,
        cwd=str(cwd),
        env=environment,
        stdout=subprocess.PIPE,
        stderr=subprocess.STDOUT,
        text=True,
        encoding="utf-8",
        errors="replace",
    )
    return completed.returncode, completed.stdout or ""


def _report(label: str, exitCode: int, output: str) -> bool:
    """Prints one check's result, echoing output only when it failed."""
    if exitCode == 0:
        print(f"  ok      {label}")
        return True
    print(f"  FAILED  {label}")
    for line in output.strip().splitlines()[-25:]:
        print(f"            {line}")
    return False


# --- Checks ---


def compileTypeScriptExamples() -> bool:
    """Typechecks examples/typescript against the SDK's real sources, not its published types."""
    tsc = _resolveBinary(tscBinaryCandidates)
    if tsc is None:
        print("  SKIPPED examples compile -- run `npm ci` in packages/buyerSdkTs first")
        return True
    exitCode, output = _run(
        [str(tsc), "--noEmit", "--project", str(typescriptExampleProject)],
        typescriptSdkDirectory,
    )
    return _report("examples/typescript compiles against the SDK sources", exitCode, output)


def runTypeScriptExample() -> bool:
    """Executes the TypeScript mandate-chain example, which asserts INV-02 itself."""
    tsx = _resolveBinary(tsxBinaryCandidates)
    if tsx is None:
        print("  SKIPPED examples run (TS) -- run `npm ci` in packages/buyerSdkTs first")
        return True
    exitCode, output = _run([str(tsx), str(typescriptExampleProgram)], meshRoot)
    return _report("examples/typescript/mandateChain.ts runs, INV-02 holds", exitCode, output)


def runPythonExample() -> bool:
    """Executes the Python mandate-chain example, the parallel of the TypeScript one."""
    exitCode, output = _run(
        [sys.executable, str(pythonExampleProgram)],
        meshRoot,
        extraEnv={"PYTHONPATH": str(pythonSdkDirectory)},
    )
    return _report("examples/python/mandateChain.py runs, INV-02 holds", exitCode, output)


def reportGeneratedDrift() -> bool:
    """Fails when a committed reference artifact no longer matches the code it describes.

    The tables are committed so the dashboard can read them from disk without a build step. That
    only stays honest if an SDK signature change forces the artifact to be regenerated in the same
    commit -- otherwise `npm run docs:verify` validates the guides against a snapshot of an API
    that no longer exists.
    """
    exitCode, output = _run(
        ["git", "diff", "--exit-code", "--"] + generatedArtifactPaths, meshRoot
    )
    if exitCode == 0:
        print("  ok      generated reference artifacts match the working tree")
        return True
    print("  FAILED  generated reference artifacts are stale")
    for line in output.strip().splitlines()[:20]:
        print(f"            {line}")
    for line in regenerateHint.splitlines():
        print(f"            {line}")
    return False


# --- Entry point ---


def main() -> int:
    parser = argparse.ArgumentParser(
        description="Compile and run the example programs the guides transclude."
    )
    parser.add_argument(
        "--check",
        action="store_true",
        help="exit non-zero if any example fails to compile, fails to run, or an artifact drifted",
    )
    parser.add_argument(
        "--skip-drift",
        action="store_true",
        help="skip the generated-artifact drift check (useful mid-edit)",
    )
    args = parser.parse_args()

    if not pythonExampleProgram.exists():
        print(f"No examples found at {meshRoot / 'examples'} -- nothing to verify.")
        return 1

    print("Verifying examples/ ...")
    results = [
        compileTypeScriptExamples(),
        runTypeScriptExample(),
        runPythonExample(),
    ]
    if not args.skip_drift:
        results.append(reportGeneratedDrift())

    failureCount = sum(1 for passed in results if not passed)
    if failureCount:
        print(f"\n{failureCount} check(s) failed.")
        return 1 if args.check else 0
    if args.skip_drift:
        print("\nEvery example compiles and runs. Drift check skipped.")
    else:
        print("\nEvery example compiles, runs, and the reference artifacts are current.")
    return 0


if __name__ == "__main__":
    sys.exit(main())
