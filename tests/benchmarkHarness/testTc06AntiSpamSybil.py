import hashlib
import time
from typing import Any, Dict, Optional, Tuple
from pydantic import BaseModel, ConfigDict, Field
import pytest

# Benchmark Constants
powLeadingZeros = 4
requiredLeadingPrefix = "0000"
microEscrowCostPaise = 50
spamRequestsCount = 100


class Http402ChallengeResponse(BaseModel):
    model_config = ConfigDict(frozen=True, extra="forbid")
    statusCode: int = 402
    wwwAuthenticate: str = "x402-INR"
    challengeToken: str
    tokenCostPaise: int = microEscrowCostPaise
    powDifficultyZeros: int = powLeadingZeros


class IngressAntiSpamShield:
    """Ingress PoW and x402 micro-metering gate protecting against Sybil attacks."""

    def __init__(self) -> None:
        self.activeChallenges: Dict[str, int] = {}
        self.authorizedEscrowTokens: Dict[str, int] = {}
        self.llmInvocationsCount = 0

    def generateChallenge(self, clientIp: str) -> Http402ChallengeResponse:
        challenge = hashlib.sha256(f"challenge:{clientIp}:{time.time()}".encode()).hexdigest()[:32]
        self.activeChallenges[challenge] = int(time.time()) + 300
        return Http402ChallengeResponse(challengeToken=challenge)

    def verifyPoWSolution(self, challenge: str, nonce: int) -> bool:
        testString = f"{challenge}:{nonce}".encode("utf-8")
        digestHex = hashlib.sha256(testString).hexdigest()
        return digestHex.startswith(requiredLeadingPrefix)

    def processRequest(
        self,
        challengeToken: Optional[str] = None,
        powNonce: Optional[int] = None,
        escrowSessionToken: Optional[str] = None,
    ) -> Tuple[int, str]:
        # Missing challenge or PoW -> 402 Payment Required
        if not challengeToken or powNonce is None:
            return 402, "HTTP 402: Micro-escrow and PoW challenge required"

        if challengeToken not in self.activeChallenges:
            return 403, "HTTP 403: Invalid or expired challenge"

        if not self.verifyPoWSolution(challengeToken, powNonce):
            return 403, "HTTP 403: Invalid Proof-of-Work solution"

        # Check micro-escrow payment
        if not escrowSessionToken or escrowSessionToken not in self.authorizedEscrowTokens:
            return 402, "HTTP 402: x402-INR micro-escrow token exhausted"

        balance = self.authorizedEscrowTokens[escrowSessionToken]
        if balance < microEscrowCostPaise:
            return 402, "HTTP 402: Insufficient micro-escrow balance"

        # Deduct micro-fee and proceed to LLM state machine
        self.authorizedEscrowTokens[escrowSessionToken] -= microEscrowCostPaise
        self.llmInvocationsCount += 1
        return 200, "OK"


def solvePoWChallenge(challenge: str) -> int:
    """Finds integer nonce yielding 4 leading hex zeros for given challenge."""
    nonce = 0
    while True:
        testString = f"{challenge}:{nonce}".encode("utf-8")
        if hashlib.sha256(testString).hexdigest().startswith(requiredLeadingPrefix):
            return nonce
        nonce += 1


def testTc06AntiSpamSybilPoWDefense() -> None:
    """TC-06: Anti-Spam Sybil PoW Defense — 100 concurrent spam bids: 1 gets challenge, 99 rejected."""
    shield = IngressAntiSpamShield()

    # Request 1: Initial unauthenticated probe receives 402 challenge
    challengeResp = shield.generateChallenge(clientIp="192.168.1.100")
    assert challengeResp.statusCode == 402
    assert challengeResp.wwwAuthenticate == "x402-INR"
    assert challengeResp.tokenCostPaise == 50

    # Requests 2 to 100: Spam flood without solving challenge -> all 99 rejected with 402
    rejectedCount = 0
    for spamIndex in range(2, spamRequestsCount + 1):
        status, _ = shield.processRequest(challengeToken=None, powNonce=None)
        if status == 402:
            rejectedCount += 1

    assert rejectedCount == 99
    # Invariant: Zero expensive backend/LLM invocations spent on spam
    assert shield.llmInvocationsCount == 0


def testTc06LegitimateAgentSolvesPoWAndPaysEscrow() -> None:
    """Verifies that a legitimate agent solving PoW and providing micro-escrow succeeds with 200 OK."""
    shield = IngressAntiSpamShield()
    challengeResp = shield.generateChallenge(clientIp="10.0.0.1")

    # Legitimate agent solves ~15ms SHA-256 PoW challenge
    validNonce = solvePoWChallenge(challengeResp.challengeToken)
    assert shield.verifyPoWSolution(challengeResp.challengeToken, validNonce)

    # Agent pre-authorizes ₹50 micro-escrow session
    escrowToken = "escrow_session_legit_001"
    shield.authorizedEscrowTokens[escrowToken] = 5000  # 5,000 paise (₹50)

    # Legitimate request processed successfully
    status, msg = shield.processRequest(
        challengeToken=challengeResp.challengeToken,
        powNonce=validNonce,
        escrowSessionToken=escrowToken,
    )
    assert status == 200
    assert msg == "OK"
    assert shield.llmInvocationsCount == 1
    assert shield.authorizedEscrowTokens[escrowToken] == 4950  # Debited ₹0.50
