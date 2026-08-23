"""Micro-escrow client for Razorpay UPI Pre-Auth micro-metering pool."""

import hashlib
import hmac
import uuid
from typing import Any, Dict, Optional

from razoragentMesh.packages.mandateEngine.verification.arithmeticEnclave import validateIntegerPaise
from ..constants.negotiationConstants import (
    defaultGatewaySecret,
    defaultSessionTtlSeconds,
    initialEscrowPoolPaise,
    microFeePerTurnPaise,
)
from .escrowSessionManager import (
    DebitReceipt,
    EscrowRefundReceipt,
    EscrowSession,
    EscrowSessionManager,
)


class MicroEscrowClient:
    """Razorpay UPI Pre-Auth micro-escrow manager for x402-INR metering."""

    def __init__(
        self,
        gatewaySecret: str = defaultGatewaySecret,
        redisClient: Optional[Any] = None,
    ) -> None:
        self._gatewaySecret = gatewaySecret
        self._sessionManager = EscrowSessionManager(redisClient=redisClient)

    @property
    def _inMemorySessions(self) -> Dict[str, EscrowSession]:
        """Provides backward-compatible access to in-memory session ledger."""
        return self._sessionManager._inMemorySessions

    def _generateReceiptSignature(self, token: str, turn: int, debit: int, rem: int, ts: int) -> str:
        """Computes HMAC-SHA256 signature for debit receipt."""
        msg = f"{token}:{turn}:{debit}:{rem}:{ts}".encode("utf-8")
        return hmac.new(self._gatewaySecret.encode("utf-8"), msg, hashlib.sha256).hexdigest()

    async def createEscrowSession(
        self,
        buyerAgentDid: str,
        initialHoldPaise: int = initialEscrowPoolPaise,
    ) -> EscrowSession:
        """Blocks pre-auth funds on buyer UPI delegation and initializes session."""
        return self._sessionManager.createSession(
            buyerAgentDid=buyerAgentDid,
            initialHoldPaise=initialHoldPaise,
            ttlSeconds=defaultSessionTtlSeconds,
        )

    async def getSession(self, sessionToken: str) -> EscrowSession:
        """Retrieves active escrow session by token."""
        return self._sessionManager.getSession(sessionToken)

    async def debitTurnFee(
        self,
        sessionToken: str,
        turnIndex: int,
        feePaise: int = microFeePerTurnPaise,
    ) -> DebitReceipt:
        """Deducts micro-metering fee for an active negotiation turn."""
        validateIntegerPaise(turnIndex, "turnIndex")
        _, newRemaining, now = self._sessionManager.debitSession(
            sessionToken=sessionToken,
            feePaise=feePaise,
        )
        sig = self._generateReceiptSignature(sessionToken, turnIndex, feePaise, newRemaining, now)
        return DebitReceipt(
            receiptId=f"rcpt_{uuid.uuid4().hex[:16]}",
            sessionToken=sessionToken,
            turnIndex=turnIndex,
            debitAmountPaise=feePaise,
            remainingBalancePaise=newRemaining,
            receiptSignatureHex=sig,
            timestamp=now,
        )

    async def releaseUnspentEscrow(self, sessionToken: str) -> EscrowRefundReceipt:
        """Releases unspent pre-auth balance back to buyer pool."""
        updatedSession, refundPaise, now = self._sessionManager.releaseSession(sessionToken)
        return EscrowRefundReceipt(
            sessionToken=sessionToken,
            totalDebitedPaise=updatedSession.debitedTotalPaise,
            refundedBalancePaise=refundPaise,
            timestamp=now,
        )


__all__ = [
    "DebitReceipt",
    "EscrowRefundReceipt",
    "EscrowSession",
    "MicroEscrowClient",
]
