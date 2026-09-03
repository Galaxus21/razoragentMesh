"""Guards the benchmark harness against tests that reimplements their subjects.

Each benchmark is named after a scenario (TC-01, TC-02, ...) and must import the production module
its scenario actually exercises. This guard verifies each benchmark imports the module it claims to
benchmark, rather than just checking that some production code appears somewhere in the file.

Three benchmarks legitimately define their own implementations (TC-05, TC-06, TC-09) and are
listed as known self-contained. Adding a fourth fails here; repairing one of the three also fails,
so the entry gets removed with the fix.

The expected-import map is keyed by file name and lists the production module(s) that must be
imported. Each benchmark's actual imports are checked against this map.
"""

import re
from pathlib import Path

import pytest

repositoryRoot = Path(__file__).resolve().parents[2]
benchmarkDirectory = repositoryRoot / "tests" / "benchmarkHarness"

# Pattern to detect any production import from the mesh.
productionImportPattern = re.compile(
    r"^\s*(?:from|import)\s+(?:packages|razoragent_buyer_sdk|razoragentMesh)\b", re.MULTILINE
)

# Verified on 2026-09-02: each of these imports nothing from packages/ and defines its own copy of
# the subsystem it claims to benchmark.
knownSelfContainedBenchmarks = {
    "testTc05NegativeConstraint.py",
    "testTc06AntiSpamSybil.py",
    "testTc09ConcurrencyDoubleLock.py",
}

# Per-file expected-import map: each benchmark must import the module(s) its scenario names.
# TC-XX scenarios are named after the subsystem they exercise.
expectedBenchmarkImports = {
    "testTc01NominalSettlement.py": r"(?:packages\.mandateEngine\.settlement|mandateEngine.*settlement)",
    "testTc02B2bNegotiation.py": r"packages\.mandateEngine\.verification",
    "testTc03BudgetBreach.py": r"packages\.mandateEngine(?:\.verification\.budgetGate)?",
    "testTc04OosSelfHealing.py": r"packages\.vectorHealer.*(?:oosInterceptor|OosInterceptor)",
    "testTc05NegativeConstraint.py": None,  # Self-contained benchmark
    "testTc06AntiSpamSybil.py": None,  # Self-contained benchmark
    "testTc07NonceReplay.py": r"packages\.mandateEngine\.nonce",
    "testTc08FloatMathDrift.py": r"packages\.mandateEngine\.verification",
    "testTc09ConcurrencyDoubleLock.py": None,  # Self-contained benchmark
    "testTc10RouteRollback2Pc.py": r"packages\.mandateEngine\.settlement",
}


def _benchmarkFiles() -> list[Path]:
    return sorted(path for path in benchmarkDirectory.glob("test*.py"))


def testBenchmarkDirectoryIsNotEmpty() -> None:
    """A passing run must not be an empty run."""
    assert len(_benchmarkFiles()) > 5


def testEachBenchmarkImportsItsSubject() -> None:
    """Each benchmark must import the production module its scenario names."""
    offenders = {}
    for path in _benchmarkFiles():
        fileName = path.name
        if fileName not in expectedBenchmarkImports:
            offenders[fileName] = f"No expected import defined for {fileName}"
            continue

        expectedPattern = expectedBenchmarkImports[fileName]
        if expectedPattern is None:
            # Self-contained benchmark; verify it has NO production imports.
            content = path.read_text(encoding="utf-8")
            if productionImportPattern.search(content):
                offenders[fileName] = "Expected to be self-contained, but imports production code"
            continue

        content = path.read_text(encoding="utf-8")
        expectedRegex = re.compile(expectedPattern)
        if not expectedRegex.search(content):
            offenders[fileName] = f"Missing expected import matching: {expectedPattern}"

    assert not offenders, (
        f"These benchmarks do not import their expected modules:\n"
        + "\n".join(f"  {name}: {reason}" for name, reason in sorted(offenders.items()))
    )


@pytest.mark.parametrize("fileName", sorted(knownSelfContainedBenchmarks))
def testKnownSelfContainedBenchmarkIsStillBroken(fileName: str) -> None:
    """If one is repaired, this fails so the allowlist entry is removed with the fix."""
    path = benchmarkDirectory / fileName
    assert path.exists(), f"{fileName} was removed -- drop it from knownSelfContainedBenchmarks"
    assert not productionImportPattern.search(path.read_text(encoding="utf-8")), (
        f"{fileName} now imports production code. Remove it from knownSelfContainedBenchmarks "
        f"and from Phase 6.6."
    )
