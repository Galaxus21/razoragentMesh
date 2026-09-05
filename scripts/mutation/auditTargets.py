"""Which modules are scored, where the result is published, and the run limits."""

from pathlib import Path
from typing import Set, Tuple

meshRoot: Path = Path(__file__).resolve().parent.parent.parent

blockStartMarker: str = "<!-- mutationscore:start -->"
blockEndMarker: str = "<!-- mutationscore:end -->"

# The financial and security core: the modules where a defect costs money or leaks
# data. Chosen before any score was measured, so the selection cannot flatter it.
coreModulePaths: Tuple[str, ...] = (
    "packages/mandateEngine/verification/arithmeticEnclave.py",
    "packages/mandateEngine/tax/gstrInvoiceEngine.py",
    "packages/mandateEngine/verification/budgetGate.py",
    "packages/mandateEngine/crypto/jcsCanonicalizer.py",
    "packages/mandateEngine/tax/gstinValidator.py",
    "packages/mandateEngine/settlement/webhookVerifier.py",
    "packages/mandateEngine/nonce/nonceLedger.py",
    "packages/x402Gateway/src/schemas/callbackUrlValidator.py",
)

testTargets: Tuple[str, ...] = ("tests", "packages/buyerSdkPy/tests")

# Directories that make the workspace copy expensive and that no Python test reads.
excludedDirectoryNames: Set[str] = {
    "node_modules", ".next", ".git", "__pycache__", ".pytest_cache",
    ".hypothesis", "dist", ".mypy_cache", "coverage",
}

# Excluded above, but restored afterwards: the cross-SDK tests shell out to Node.
crossSdkDependencyPaths: Tuple[str, ...] = (
    "packages/buyerSdkTs/node_modules",
    "packages/mcpServer/node_modules",
)

_auditDoc = meshRoot / "docs" / "TEST_QUALITY_AUDIT.md"
if not _auditDoc.exists():
    _auditDoc = meshRoot.parent / "TEST_QUALITY_AUDIT.md"
documentedFilePaths: Tuple[Path, ...] = (_auditDoc,) if _auditDoc.exists() else ()

# A mutant that hangs has still escaped the suite, but it must not stall the run.
mutantTimeoutSeconds: int = 120
coverageTimeoutSeconds: int = 1800

# Windows caps a command line near 32k characters; past this the selected node ids
# are collapsed to their unique files.
maxCommandLength: int = 24000

exitCodeAllPassed: int = 0
exitCodeTestsFailed: int = 1
exitCodeInterrupted: int = 2
exitCodeUsageError: int = 4
exitCodeNoTestsCollected: int = 5

# A mutant can break a module badly enough that pytest cannot import the test files
# that reach it. pytest reports that as a collection error and exits 2 or 4 rather
# than 1 -- verified against the pinned pytest 9.1.1 on 2026-08-31.
collectionErrorExitCodes: Tuple[int, ...] = (exitCodeInterrupted, exitCodeUsageError)

# pytest's wording when a node id does not resolve. That is the harness's fault
# rather than the mutant's, so it must stop the run instead of being scored.
unknownTestIdMarker: str = "not found:"

outcomeKilled: str = "killed"
outcomeSurvived: str = "survived"
outcomeError: str = "error"

detailTimeout: str = "timeout"
detailCollectionError: str = "collection-error"

# Enough of pytest's tail to diagnose a harness fault from the error alone.
diagnosticExcerptLength: int = 2000
