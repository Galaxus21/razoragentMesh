"""Proof-of-Work anti-spam shield for Layer 2 ingress protection."""

import hashlib
import time
import uuid
from typing import Any, Dict, Optional, Tuple

from ..constants.gatewayConstants import (
    httpStatusForbidden,
    httpStatusOk,
    httpStatusPaymentRequired,
)
from ..constants.negotiationConstants import (
    microFeePerTurnPaise,
    powChallengeTtlSeconds,
    powLeadingZeros,
    powReplayCacheTtlSeconds,
    protocolName,
    requiredLeadingPrefix,
)
from ..gatewayExceptions import (
    InvalidProofOfWorkException,
    PowChallengeExpiredException,
    PowReplayDetectedException,
)
from ..schemas.x402ChallengeSchema import (
    Http402ChallengeResponse,
    PowVerificationResult,
)

powEscalatedLeadingZeros: int = 5
powHighLoadThreshold: int = 100


class IngressAntiSpamShield:
    """Ingress PoW and x402 micro-metering gate protecting against Sybil attacks."""

    def __init__(self, redisClient: Optional[Any] = None) -> None:
        self._redisClient = redisClient
        self.activeChallenges: Dict[str, int] = {}
        self.challengeDifficulties: Dict[str, int] = {}
        self.authorizedEscrowTokens: Dict[str, int] = {}
        self.consumedChallenges: Dict[str, int] = {}
        self.llmInvocationsCount = 0
        self._ipRequestCounts: Dict[str, int] = {}

    def evaluateDynamicDifficulty(self, clientIp: str, requestCount: int = 0) -> int:
        """Evaluates PoW difficulty for client IP based on request load."""
        effectiveCount = requestCount if requestCount > 0 else self._ipRequestCounts.get(clientIp, 0)
        return evaluateDynamicDifficulty(clientIp, effectiveCount)

    def generateChallenge(
        self, clientIp: str, requestCount: Optional[int] = None
    ) -> Http402ChallengeResponse:
        """Generates a fresh PoW challenge token with 5-minute expiry and dynamic difficulty."""
        uniqueId = uuid.uuid4().hex
        now = int(time.time())
        tokenBytes = f"challenge:{clientIp}:{uniqueId}:{now}".encode("utf-8")
        challenge = hashlib.sha256(tokenBytes).hexdigest()[:32]
        self.activeChallenges[challenge] = now + powChallengeTtlSeconds

        self._ipRequestCounts[clientIp] = self._ipRequestCounts.get(clientIp, 0) + 1
        effectiveCount = requestCount if requestCount is not None else self._ipRequestCounts[clientIp]
        difficulty = self.evaluateDynamicDifficulty(clientIp, effectiveCount)
        self.challengeDifficulties[challenge] = difficulty

        return Http402ChallengeResponse(
            challengeToken=challenge,
            powDifficultyZeros=difficulty,
        )

    def verifyPoWSolution(
        self, challenge: str, nonce: int, difficultyZeros: Optional[int] = None
    ) -> bool:
        """Verifies candidate nonce against challenge string for leading zeros."""
        targetZeros = difficultyZeros or self.challengeDifficulties.get(challenge, powLeadingZeros)
        targetPrefix = "0" * targetZeros
        candidateBytes = f"{challenge}:{nonce}".encode("utf-8")
        digestHex = hashlib.sha256(candidateBytes).hexdigest()
        return digestHex.startswith(targetPrefix)

    def _checkChallengeLiveness(self, challengeToken: str, now: int) -> None:
        """Validates challenge token existence and expiration."""
        if challengeToken not in self.activeChallenges:
            raise InvalidProofOfWorkException("Challenge token not found")
        expiresAt = self.activeChallenges[challengeToken]
        if now > expiresAt:
            self.activeChallenges.pop(challengeToken, None)
            self.challengeDifficulties.pop(challengeToken, None)
            raise PowChallengeExpiredException("Challenge token has expired")

    def _checkReplay(self, challengeToken: str) -> None:
        """Guards against replay attacks by tracking consumed tokens."""
        if challengeToken in self.consumedChallenges:
            raise PowReplayDetectedException("Challenge token already consumed")

    def validatePoWSubmission(
        self,
        challengeToken: str,
        nonce: int,
        requiredDifficulty: Optional[int] = None,
    ) -> PowVerificationResult:
        """Executes full verification workflow: liveness, solution check, and replay guard."""
        now = int(time.time())
        self._checkReplay(challengeToken)
        self._checkChallengeLiveness(challengeToken, now)

        targetZeros = requiredDifficulty or self.challengeDifficulties.get(challengeToken, powLeadingZeros)
        targetPrefix = "0" * targetZeros
        candidateBytes = f"{challengeToken}:{nonce}".encode("utf-8")
        digestHex = hashlib.sha256(candidateBytes).hexdigest()
        if not digestHex.startswith(targetPrefix):
            raise InvalidProofOfWorkException("Proof-of-work solution did not satisfy difficulty target")

        self.consumedChallenges[challengeToken] = now + powReplayCacheTtlSeconds
        self.activeChallenges.pop(challengeToken, None)
        self.challengeDifficulties.pop(challengeToken, None)

        return PowVerificationResult(
            isValid=True,
            challengeToken=challengeToken,
            computedDigest=digestHex,
        )

    def processRequest(
        self,
        challengeToken: Optional[str] = None,
        powNonce: Optional[int] = None,
        escrowSessionToken: Optional[str] = None,
    ) -> Tuple[int, str]:
        """Processes request through combined PoW and micro-escrow authorization gate."""
        if not challengeToken or powNonce is None:
            return httpStatusPaymentRequired, "HTTP 402: Micro-escrow and PoW challenge required"

        if challengeToken not in self.activeChallenges:
            return httpStatusForbidden, "HTTP 403: Invalid or expired challenge"

        if not self.verifyPoWSolution(challengeToken, powNonce):
            return httpStatusForbidden, "HTTP 403: Invalid Proof-of-Work solution"

        if not escrowSessionToken or escrowSessionToken not in self.authorizedEscrowTokens:
            return httpStatusPaymentRequired, "HTTP 402: x402-INR micro-escrow token exhausted"

        balance = self.authorizedEscrowTokens[escrowSessionToken]
        if balance < microFeePerTurnPaise:
            return httpStatusPaymentRequired, "HTTP 402: Insufficient micro-escrow balance"

        self.authorizedEscrowTokens[escrowSessionToken] -= microFeePerTurnPaise
        self.llmInvocationsCount += 1
        return httpStatusOk, "OK"


def evaluateDynamicDifficulty(clientIp: str, requestCount: int) -> int:
    """Evaluates dynamic PoW leading zero difficulty based on client request count."""
    if requestCount >= powHighLoadThreshold:
        return powEscalatedLeadingZeros
    return powLeadingZeros


def solvePoWChallenge(challenge: str, difficultyZeros: int = powLeadingZeros) -> int:
    """Finds integer nonce yielding required leading hex zeros for given challenge."""
    targetPrefix = "0" * difficultyZeros
    nonce = 0
    while True:
        candidateBytes = f"{challenge}:{nonce}".encode("utf-8")
        if hashlib.sha256(candidateBytes).hexdigest().startswith(targetPrefix):
            return nonce
        nonce += 1


__all__ = [
    "Http402ChallengeResponse",
    "IngressAntiSpamShield",
    "PowVerificationResult",
    "evaluateDynamicDifficulty",
    "powEscalatedLeadingZeros",
    "powHighLoadThreshold",
    "solvePoWChallenge",
]
