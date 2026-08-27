"""Adversarial stress tests for PowSolver, concurrent solving, and edge difficulties."""

import concurrent.futures
import pytest
from razoragent_buyer_sdk import (
    PowSolver,
    PowSolverError,
    buildPowHeaders,
    solvePoWChallenge,
    solvePoWChallengeWithMetrics,
    verifyPoWSolution,
)


def testPowVariedDifficulties() -> None:
    """Tests PoW solution and verification across difficulties 1 to 4."""
    challenge = "stress_challenge_matrix_001"
    for diff in (1, 2, 3, 4):
        nonce = solvePoWChallenge(challenge, difficultyZeros=diff)
        assert nonce >= 0
        assert verifyPoWSolution(challenge, nonce, difficultyZeros=diff) is True
        # Verify that lower difficulty also satisfies prefix
        assert verifyPoWSolution(challenge, nonce, difficultyZeros=1) is True


def testPowInvalidParameters() -> None:
    """Tests validation of invalid difficulty, empty challenges, and iteration exhaustion."""
    # Zero difficulty
    with pytest.raises(PowSolverError) as excZero:
        solvePoWChallenge("challenge_1", difficultyZeros=0)
    assert "difficultyZeros must be at least 1" in str(excZero.value)

    # Negative difficulty
    with pytest.raises(PowSolverError):
        solvePoWChallenge("challenge_1", difficultyZeros=-3)

    # Empty challenge string
    with pytest.raises(PowSolverError) as excEmpty:
        solvePoWChallenge("", difficultyZeros=2)
    assert "challengeToken cannot be empty" in str(excEmpty.value)

    # Max iteration exhaustion
    with pytest.raises(PowSolverError) as excIter:
        solvePoWChallenge("difficult_challenge_token", difficultyZeros=5, maxIterations=5)
    assert "Exceeded max iterations" in str(excIter.value)


def testPowVerifyEdgeCases() -> None:
    """Stress tests verifyPoWSolution on malformed and negative parameters."""
    challenge = "verify_edge_challenge"
    nonce = solvePoWChallenge(challenge, difficultyZeros=2)

    # Valid check
    assert verifyPoWSolution(challenge, nonce, difficultyZeros=2) is True

    # Negative nonce returns False
    assert verifyPoWSolution(challenge, -1, difficultyZeros=2) is False

    # Empty challenge returns False
    assert verifyPoWSolution("", nonce, difficultyZeros=2) is False

    # Zero or negative difficulty returns False
    assert verifyPoWSolution(challenge, nonce, difficultyZeros=0) is False
    assert verifyPoWSolution(challenge, nonce, difficultyZeros=-1) is False

    # Off-by-one nonce
    assert verifyPoWSolution(challenge, nonce + 1, difficultyZeros=4) is False


def testConcurrentPowSolving() -> None:
    """Stress tests 50 simultaneous PoW challenge solves using thread pool executor."""
    def worker(index: int) -> tuple[int, bool]:
        ch = f"concurrent_challenge_{index}_{index * 17}"
        res = solvePoWChallengeWithMetrics(ch, difficultyZeros=2)
        isValid = verifyPoWSolution(ch, res.nonce, difficultyZeros=2)
        return index, isValid

    with concurrent.futures.ThreadPoolExecutor(max_workers=10) as executor:
        futures = [executor.submit(worker, i) for i in range(50)]
        for future in concurrent.futures.as_completed(futures):
            idx, valid = future.result()
            assert valid is True


def testPowHeaderVariations() -> None:
    """Tests header generation across all parameter combinations."""
    # Minimal headers
    hMin = buildPowHeaders("tok_123", 456)
    assert hMin["X-Mesh-Pow-Challenge"] == "tok_123"
    assert hMin["X-Mesh-Pow-Solution"] == "456"
    assert "X-Mesh-Escrow-Token" not in hMin
    assert "X-Buyer-Agent-Did" not in hMin

    # Full headers
    hFull = buildPowHeaders("tok_123", 456, escrowToken="escrow_789", buyerAgentDid="did:agent:abc")
    assert hFull["X-Mesh-Pow-Challenge"] == "tok_123"
    assert hFull["X-Mesh-Pow-Solution"] == "456"
    assert hFull["X-Mesh-Escrow-Token"] == "escrow_789"
    assert hFull["X-Buyer-Agent-Did"] == "did:agent:abc"
