"""Micro-escrow client for Razorpay UPI Pre-Auth micro-metering pool."""

import hashlib
import hmac
import time
import uuid
from typing import Any, Dict, Optional
from pydantic import BaseModel, ConfigDict, Field

from razoragentMesh.packages.mandateEngine.arithmeticEnclave import validateIntegerPaise
from razoragentMesh.packages.x402Gateway.gatewayConstants import (
    defaultSessionTtlSeconds,
    initialEscrowPoolPaise,
    microFeePerTurnPaise,
)
from razoragentMesh.packages.x402Gateway.gatewayExceptions import (
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


class MicroEscrowClient:
    """Razorpay UPI Pre-Auth micro-escrow manager for x402-INR metering."""

    def __init__(
        self,
        gatewaySecret: str = "rzp_test_escrow_secret_key_32bytes",
        redisClient: Optional[Any] = None,
    ) -> None:
        self._gatewaySecret = gatewaySecret
        self._redisClient = redisClient
        self._inMemorySessions: Dict[str, EscrowSession] = {}

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
            expiresAtUnix=now + defaultSessionTtlSeconds,
            isReleased=False,
        )
        self._inMemorySessions[token] = session
        return session

    async def getSession(self, sessionToken: str) -> EscrowSession:
        """Retrieves active escrow session by token."""
        if sessionToken not in self._inMemorySessions:
            raise EscrowSessionNotFoundException(f"Escrow session '{sessionToken}' not found")
        session = self._inMemorySessions[sessionToken]
        if int(time.time()) > session.expiresAtUnix:
            raise EscrowSessionNotFoundException("Escrow session has expired")
        return session

    async def debitTurnFee(
        self,
        sessionToken: str,
        turnIndex: int,
        feePaise: int = microFeePerTurnPaise,
    ) -> DebitReceipt:
        """Deducts micro-metering fee for an active negotiation turn."""
        validateIntegerPaise(feePaise, "feePaise")
        validateIntegerPaise(turnIndex, "turnIndex")

        session = await self.getSession(sessionToken)
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
        session = await self.getSession(sessionToken)
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

        return EscrowRefundReceipt(
            sessionToken=sessionToken,
            totalDebitedPaise=session.debitedTotalPaise,
            refundedBalancePaise=refundPaise,
            timestamp=now,
        )
