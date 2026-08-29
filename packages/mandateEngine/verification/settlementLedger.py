"""Durable per-mandate settlement guards: cumulative spend accounting and cart replay defence.

`NonceLedger` prevents replaying an *identical* ExecutionMandate. It cannot prevent a buyer from
minting a fresh ExecutionMandate (new nonce) against the same merchant-signed CartMandate, nor
can it bound total spend across separate transactions. Both of those are enforced here.

Availability policy: these guards **fail open** with a warning when Redis is unreachable. A
settlement engine that refuses all traffic because its accounting store is down is worse for a
live demo than one that briefly cannot enforce a ceiling. Production should fail closed -- see the
Scope & Limitations section of the README.
"""

import logging
from typing import Any, Optional

from ..settlement.settlementExceptions import (
    CartAlreadySettledException,
    CumulativeBudgetExceededException,
)

logger = logging.getLogger(__name__)

spendRedisKeyPrefix: str = "razoragent:spend:"
settledCartRedisKeyPrefix: str = "razoragent:settled:"
settledCartTtlSeconds: int = 604800  # 7 days; outlives any mandate validity window
minimumSpendTtlSeconds: int = 60

__all__ = ["SettlementLedger", "settledCartRedisKeyPrefix", "spendRedisKeyPrefix"]


class SettlementLedger:
    """Redis-backed cumulative spend counter and settled-cart registry."""

    def __init__(self, redisClient: Any) -> None:
        self._redis = redisClient

    async def claimCartSettlement(self, cartMandateHash: str) -> None:
        """Claims a cart for settlement exactly once.

        Raises CartAlreadySettledException if this cart has been settled before.
        """
        if self._redis is None:
            logger.warning("SettlementLedger: no Redis client; cart replay guard is INACTIVE")
            return
        redisKey = f"{settledCartRedisKeyPrefix}{cartMandateHash}"
        try:
            wasClaimed = await self._redis.set(redisKey, "1", ex=settledCartTtlSeconds, nx=True)
        except Exception as redisError:
            logger.warning("SettlementLedger: cart replay guard unavailable (%s); failing open", redisError)
            return
        if not wasClaimed:
            raise CartAlreadySettledException(
                f"Cart {cartMandateHash} has already been settled: ₹0 charged"
            )

    async def recordCumulativeSpend(
        self,
        mandateId: str,
        amountPaise: int,
        maxBudgetPaise: int,
        expiresAtUnix: Optional[int] = None,
        serverTime: Optional[int] = None,
    ) -> int:
        """Adds amountPaise to this mandate's running total and enforces the cumulative ceiling.

        Increments first and rolls back on breach, so concurrent settlements against the same
        mandate cannot interleave their way past the cap via a check-then-act race.
        Returns the new cumulative total in paise.
        """
        if self._redis is None:
            logger.warning("SettlementLedger: no Redis client; cumulative budget cap is INACTIVE")
            return amountPaise
        redisKey = f"{spendRedisKeyPrefix}{mandateId}"
        try:
            cumulativePaise = await self._redis.incrby(redisKey, amountPaise)
            await self._applySpendExpiry(redisKey, expiresAtUnix, serverTime)
        except Exception as redisError:
            logger.warning("SettlementLedger: cumulative budget cap unavailable (%s); failing open", redisError)
            return amountPaise

        if cumulativePaise > maxBudgetPaise:
            await self._rollbackSpend(redisKey, amountPaise)
            raise CumulativeBudgetExceededException(
                f"Cumulative spend {cumulativePaise} paise would exceed delegated budget "
                f"{maxBudgetPaise} paise for mandate {mandateId}: ₹0 charged"
            )
        return cumulativePaise

    async def releaseCartClaim(self, cartMandateHash: str) -> None:
        """Releases a cart claim taken for a settlement that then failed.

        The claim is a reservation, not a record of payment: it is taken before capture so two
        concurrent settlements cannot both proceed. If the settlement does not complete, holding
        the claim would lock a legitimate buyer out of retrying their own cart.
        """
        if self._redis is None:
            return
        try:
            await self._redis.delete(f"{settledCartRedisKeyPrefix}{cartMandateHash}")
        except Exception as redisError:
            logger.warning("SettlementLedger: could not release cart claim (%s)", redisError)

    async def releaseCumulativeSpend(self, mandateId: str, amountPaise: int) -> None:
        """Returns provisionally-booked spend to a mandate after a failed settlement."""
        if self._redis is None:
            return
        await self._rollbackSpend(f"{spendRedisKeyPrefix}{mandateId}", amountPaise)

    async def getCumulativeSpend(self, mandateId: str) -> int:
        """Returns paise already settled against this mandate, or 0 when unavailable."""
        if self._redis is None:
            return 0
        try:
            recorded = await self._redis.get(f"{spendRedisKeyPrefix}{mandateId}")
        except Exception:
            return 0
        return int(recorded) if recorded is not None else 0

    async def _applySpendExpiry(
        self,
        redisKey: str,
        expiresAtUnix: Optional[int],
        serverTime: Optional[int],
    ) -> None:
        """Expires the counter when the mandate does, so budgets do not leak across mandates."""
        if expiresAtUnix is None:
            return
        import time

        now = serverTime if serverTime is not None else int(time.time())
        ttlSeconds = max(expiresAtUnix - now, minimumSpendTtlSeconds)
        await self._redis.expire(redisKey, ttlSeconds)

    async def _rollbackSpend(self, redisKey: str, amountPaise: int) -> None:
        """Undoes a provisional increment after a ceiling breach."""
        try:
            await self._redis.incrby(redisKey, -amountPaise)
        except Exception as redisError:
            logger.warning("SettlementLedger: spend rollback failed for %s (%s)", redisKey, redisError)
