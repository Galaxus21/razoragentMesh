"""Guards the benchmark harness against tests that assert their own reimplementations.

A test that defines the class it is named after, then exercises that definition, passes whatever the
production code does -- including when the production code is deleted. Three files in the harness do
exactly this today: they import no production module at all and simulate the subsystem from scratch,
so their green ticks say nothing about `packages/`.

They are listed rather than hidden, and the list is a ratchet. Adding a fourth self-contained
benchmark fails here; repairing one of the three also fails here, so the entry gets removed with the
fix rather than outliving it.

Filed as Phase 6.6.
"""

import re
from pathlib import Path

import pytest

repositoryRoot = Path(__file__).resolve().parents[2]
benchmarkDirectory = repositoryRoot / "tests" / "benchmarkHarness"

# An import of anything the mesh actually ships.
productionImportPattern = re.compile(
    r"^\s*(?:from|import)\s+(?:packages|razoragent_buyer_sdk|razoragentMesh)\b", re.MULTILINE
)

# Verified on 2026-08-31: each of these imports nothing from packages/ and defines its own copy of
# the subsystem it claims to benchmark.
knownSelfContainedBenchmarks = {
    "testTc05NegativeConstraint.py",
    "testTc06AntiSpamSybil.py",
    "testTc09ConcurrencyDoubleLock.py",
}


def _benchmarkFiles() -> list[Path]:
    return sorted(path for path in benchmarkDirectory.glob("test*.py"))


def testBenchmarkDirectoryIsNotEmpty() -> None:
    """A passing run must not be an empty run."""
    assert len(_benchmarkFiles()) > 5


def testNoNewSelfContainedBenchmarkAppears() -> None:
    """Every benchmark except the three known ones exercises real production code."""
    offenders = {
        path.name
        for path in _benchmarkFiles()
        if not productionImportPattern.search(path.read_text(encoding="utf-8"))
    }
    unexpected = offenders - knownSelfContainedBenchmarks
    assert not unexpected, (
        f"These benchmarks import no production code, so they assert only themselves: "
        f"{sorted(unexpected)}"
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
