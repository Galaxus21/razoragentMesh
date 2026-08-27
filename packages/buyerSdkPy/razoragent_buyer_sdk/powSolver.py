"""High-throughput SHA-256 Proof of Work (PoW) solver for x402-INR gateway challenges."""

import hashlib
import time
from typing import Dict, Optional

from .constants import (
    defaultPowDifficulty,
    headerBuyerAgentDid,
    headerEscrowToken,
    headerPowChallenge,
    headerPowSolution,
    maxPowSolveIterations,
)
from .exceptions import PowSolverError
from .models import PowSolutionResult


def solvePoWChallenge(
    challengeToken: str,
    difficultyZeros: int = defaultPowDifficulty,
    maxIterations: int = maxPowSolveIterations,
) -> int:
    """Finds integer nonce yielding required leading hex zeros for given challenge."""
    if not challengeToken:
        raise PowSolverError("challengeToken cannot be empty")
    if difficultyZeros < 1:
        raise PowSolverError("difficultyZeros must be at least 1")

    targetPrefix = "0" * difficultyZeros
    nonce = 0
    while nonce < maxIterations:
        candidateBytes = f"{challengeToken}:{nonce}".encode("utf-8")
        digest = hashlib.sha256(candidateBytes).hexdigest()
        if digest.startswith(targetPrefix):
            return nonce
        nonce += 1

    raise PowSolverError(
        f"Exceeded max iterations ({maxIterations}) without finding solution for difficulty {difficultyZeros}"
    )


def solvePoWChallengeWithMetrics(
    challengeToken: str,
    difficultyZeros: int = defaultPowDifficulty,
    maxIterations: int = maxPowSolveIterations,
) -> PowSolutionResult:
    """Solves PoW challenge and returns timing and performance metrics."""
    startTime = time.perf_counter()
    nonce = solvePoWChallenge(challengeToken, difficultyZeros=difficultyZeros, maxIterations=maxIterations)
    elapsedMs = (time.perf_counter() - startTime) * 1000.0

    candidateBytes = f"{challengeToken}:{nonce}".encode("utf-8")
    digest = hashlib.sha256(candidateBytes).hexdigest()

    return PowSolutionResult(
        nonce=nonce,
        computedDigest=digest,
        attemptsCount=nonce + 1,
        elapsedTimeMs=round(elapsedMs, 3),
        isValid=True,
    )


def verifyPoWSolution(
    challengeToken: str,
    nonce: int,
    difficultyZeros: int = defaultPowDifficulty,
) -> bool:
    """Verifies that candidate nonce produces target leading zeros against challenge."""
    if not challengeToken or nonce < 0 or difficultyZeros < 1:
        return False
    targetPrefix = "0" * difficultyZeros
    candidateBytes = f"{challengeToken}:{nonce}".encode("utf-8")
    digest = hashlib.sha256(candidateBytes).hexdigest()
    return digest.startswith(targetPrefix)


def buildPowHeaders(
    challengeToken: str,
    nonce: int,
    escrowToken: Optional[str] = None,
    buyerAgentDid: Optional[str] = None,
) -> Dict[str, str]:
    """Constructs HTTP headers satisfying x402-INR gateway PoW and escrow authorization."""
    headers: Dict[str, str] = {
        headerPowChallenge: challengeToken,
        headerPowSolution: str(nonce),
    }
    if escrowToken:
        headers[headerEscrowToken] = escrowToken
    if buyerAgentDid:
        headers[headerBuyerAgentDid] = buyerAgentDid
    return headers


class PowSolver:
    """Wrapper class providing static and instance interfaces for PoW operations."""

    @staticmethod
    def solve(
        challengeToken: str,
        difficultyZeros: int = defaultPowDifficulty,
        maxIterations: int = maxPowSolveIterations,
    ) -> int:
        """Solves PoW challenge."""
        return solvePoWChallenge(challengeToken, difficultyZeros, maxIterations)

    @staticmethod
    def solveWithMetrics(
        challengeToken: str,
        difficultyZeros: int = defaultPowDifficulty,
        maxIterations: int = maxPowSolveIterations,
    ) -> PowSolutionResult:
        """Solves PoW challenge returning solution metrics."""
        return solvePoWChallengeWithMetrics(challengeToken, difficultyZeros, maxIterations)

    @staticmethod
    def verify(
        challengeToken: str,
        nonce: int,
        difficultyZeros: int = defaultPowDifficulty,
    ) -> bool:
        """Verifies candidate PoW nonce."""
        return verifyPoWSolution(challengeToken, nonce, difficultyZeros)

    @staticmethod
    def createHeaders(
        challengeToken: str,
        nonce: int,
        escrowToken: Optional[str] = None,
        buyerAgentDid: Optional[str] = None,
    ) -> Dict[str, str]:
        """Creates PoW HTTP headers."""
        return buildPowHeaders(challengeToken, nonce, escrowToken, buyerAgentDid)


__all__ = [
    "PowSolver",
    "buildPowHeaders",
    "solvePoWChallenge",
    "solvePoWChallengeWithMetrics",
    "verifyPoWSolution",
]
