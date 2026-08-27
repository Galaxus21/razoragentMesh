"""Per-session micro-debit ledger and session state tracking."""

import time
import uuid
from typing import Any, Dict, Optional, Tuple
from pydantic import BaseModel, ConfigDict, Field

from ..constants.arithmeticUtils import validateIntegerPaise
from ..constants.negotiationConstants import (
    defaultSessionTtlSeconds,
    initialEscrowPoolPaise,
)
from ..gatewayExceptions import (
    EscrowSessionNotFoundException,
    InsufficientEscrowBalanceException,
)


class EscrowSession(BaseModel):
    """Active micro-escrow session tracking locked pre-auth balance."""

    model_config = ConfigDict(frozen=True, extra="forbid")

    sessionToken: str = Field(min_length=1)
    buyerAgentDid: str = Field(min_length=1)
    initialHoldPaise: int = Field(gt=0)
    remainingBalancePaise: int = Field(ge=0)
    debitedTotalPaise: int = Field(ge=0)
    totalTurnsDebited: int = Field(ge=0)
    createdAtUnix: int = Field(gt=0)
    expiresAtUnix: int = Field(gt=0)
    isReleased: bool = False


class DebitReceipt(BaseModel):
    """Cryptographic receipt for a single turn micro-metering debit."""

    model_config = ConfigDict(frozen=True, extra="forbid")

    receiptId: str = Field(min_length=1)
    sessionToken: str = Field(min_length=1)
    turnIndex: int = Field(ge=1)
    debitAmountPaise: int = Field(gt=0)
    remainingBalancePaise: int = Field(ge=0)
    receiptSignatureHex: str = Field(min_length=64, max_length=64)
    timestamp: int = Field(gt=0)


class EscrowRefundReceipt(BaseModel):
    """Receipt emitted when remaining pre-auth escrow is unblocked."""

    model_config = ConfigDict(frozen=True, extra="forbid")

    sessionToken: str = Field(min_length=1)
    totalDebitedPaise: int = Field(ge=0)
    refundedBalancePaise: int = Field(ge=0)
    timestamp: int = Field(gt=0)


class EscrowSessionManager:
    """Manages active in-memory and distributed micro-escrow session ledgers."""

    def __init__(self, redisClient: Optional[Any] = None) -> None:
        self._redisClient = redisClient
        self._inMemorySessions: Dict[str, EscrowSession] = {}

    def createSession(
        self,
        buyerAgentDid: str,
        initialHoldPaise: int = initialEscrowPoolPaise,
        ttlSeconds: int = defaultSessionTtlSeconds,
    ) -> EscrowSession:
        """Initializes and registers a new pre-auth escrow session."""
        validateIntegerPaise(initialHoldPaise, "initialHoldPaise")
        now = int(time.time())
        token = f"esc_{uuid.uuid4().hex}"
        session = EscrowSession(
            sessionToken=token,
            buyerAgentDid=buyerAgentDid,
            initialHoldPaise=initialHoldPaise,
            remainingBalancePaise=initialHoldPaise,
            debitedTotalPaise=0,
            totalTurnsDebited=0,
            createdAtUnix=now,
            expiresAtUnix=now + ttlSeconds,
            isReleased=False,
        )
        self._inMemorySessions[token] = session
        return session

    def getSession(self, sessionToken: str) -> EscrowSession:
        """Retrieves and validates active escrow session by token."""
        if sessionToken not in self._inMemorySessions:
            raise EscrowSessionNotFoundException(f"Escrow session '{sessionToken}' not found")
        session = self._inMemorySessions[sessionToken]
        if int(time.time()) > session.expiresAtUnix:
            raise EscrowSessionNotFoundException("Escrow session has expired")
        return session

    def debitSession(
        self,
        sessionToken: str,
        feePaise: int,
    ) -> Tuple[EscrowSession, int, int]:
        """Debits fee from active session ledger and returns updated session with timestamps."""
        validateIntegerPaise(feePaise, "feePaise")
        session = self.getSession(sessionToken)
        if session.isReleased:
            raise EscrowSessionNotFoundException("Escrow session already released")
        if session.remainingBalancePaise < feePaise:
            raise InsufficientEscrowBalanceException("Insufficient micro-escrow balance")

        now = int(time.time())
        newRemaining = session.remainingBalancePaise - feePaise
        newDebited = session.debitedTotalPaise + feePaise
        newTurns = session.totalTurnsDebited + 1

        updatedSession = EscrowSession(
            sessionToken=session.sessionToken,
            buyerAgentDid=session.buyerAgentDid,
            initialHoldPaise=session.initialHoldPaise,
            remainingBalancePaise=newRemaining,
            debitedTotalPaise=newDebited,
            totalTurnsDebited=newTurns,
            createdAtUnix=session.createdAtUnix,
            expiresAtUnix=session.expiresAtUnix,
            isReleased=False,
        )
        self._inMemorySessions[sessionToken] = updatedSession
        return updatedSession, newRemaining, now

    def releaseSession(self, sessionToken: str) -> Tuple[EscrowSession, int, int]:
        """Marks session released, unblocks remaining balance, and returns state."""
        session = self.getSession(sessionToken)
        now = int(time.time())
        refundPaise = session.remainingBalancePaise

        updatedSession = EscrowSession(
            sessionToken=session.sessionToken,
            buyerAgentDid=session.buyerAgentDid,
            initialHoldPaise=session.initialHoldPaise,
            remainingBalancePaise=0,
            debitedTotalPaise=session.debitedTotalPaise,
            totalTurnsDebited=session.totalTurnsDebited,
            createdAtUnix=session.createdAtUnix,
            expiresAtUnix=session.expiresAtUnix,
            isReleased=True,
        )
        self._inMemorySessions[sessionToken] = updatedSession
        return updatedSession, refundPaise, now


__all__ = [
    "DebitReceipt",
    "EscrowRefundReceipt",
    "EscrowSession",
    "EscrowSessionManager",
]
