"""Unit tests for SHA-256 Proof of Work (PoW) solver and header generator."""

import pytest
from razoragent_buyer_sdk import (
    PowSolver,
    PowSolverError,
    buildPowHeaders,
    solvePoWChallenge,
    solvePoWChallengeWithMetrics,
    verifyPoWSolution,
)


def testSolvePoWChallengeEasy() -> None:
    """Verifies solving PoW challenges for low difficulties."""
    challenge = "test_challenge_easy_12345"
    for difficulty in (1, 2, 3):
        nonce = solvePoWChallenge(challenge, difficultyZeros=difficulty)
        assert nonce >= 0
        assert verifyPoWSolution(challenge, nonce, difficultyZeros=difficulty) is True


def testSolvePoWChallengeStandard() -> None:
    """Verifies solving standard difficulty 4 challenge."""
    challenge = "challenge_gateway_production_001"
    nonce = PowSolver.solve(challenge, difficultyZeros=4)
    assert nonce >= 0
    assert PowSolver.verify(challenge, nonce, difficultyZeros=4) is True


def testSolvePoWChallengeWithMetrics() -> None:
    """Verifies metrics tracking during PoW computation."""
    challenge = "challenge_metrics_001"
    result = solvePoWChallengeWithMetrics(challenge, difficultyZeros=2)
    assert result.isValid is True
    assert result.nonce >= 0
    assert result.attemptsCount == result.nonce + 1
    assert result.elapsedTimeMs >= 0.0
    assert result.computedDigest.startswith("00")


def testVerifyPoWSolution() -> None:
    """Verifies verification correctness on valid and invalid nonces."""
    challenge = "challenge_verify_001"
    nonce = solvePoWChallenge(challenge, difficultyZeros=2)
    assert verifyPoWSolution(challenge, nonce, difficultyZeros=2) is True
    assert verifyPoWSolution(challenge, nonce + 999999, difficultyZeros=2) is False
    assert verifyPoWSolution("different_challenge", nonce, difficultyZeros=2) is False


def testBuildPowHeaders() -> None:
    """Verifies generation of protocol headers for gateway authentication."""
    headers = buildPowHeaders(
        challengeToken="c_token_001",
        nonce=4289,
        escrowToken="escrow_tok_001",
        buyerAgentDid="did:agent:e1bc53c4826b553d077b949bc52579df6480bdf507e15312fb1016be3b1fefc3",
    )
    assert headers["X-Mesh-Pow-Challenge"] == "c_token_001"
    assert headers["X-Mesh-Pow-Solution"] == "4289"
    assert headers["X-Mesh-Escrow-Token"] == "escrow_tok_001"
    assert headers["X-Buyer-Agent-Did"] == "did:agent:e1bc53c4826b553d077b949bc52579df6480bdf507e15312fb1016be3b1fefc3"


def testMaxIterationsExceeded() -> None:
    """Verifies raising PowSolverError when iteration ceiling is reached."""
    with pytest.raises(PowSolverError):
        solvePoWChallenge("impossible_challenge", difficultyZeros=5, maxIterations=1)


def testInvalidInputs() -> None:
    """Verifies validation errors on malformed challenge parameters."""
    with pytest.raises(PowSolverError):
        solvePoWChallenge("", difficultyZeros=4)

    with pytest.raises(PowSolverError):
        solvePoWChallenge("valid_challenge", difficultyZeros=0)
