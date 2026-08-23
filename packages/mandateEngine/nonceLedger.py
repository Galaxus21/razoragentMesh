"""Distributed Nonce Ledger with Redis SETNX and NTP drift windowing."""

import time
from typing import Any, Optional

from razoragentMesh.packages.mandateEngine.settlementExceptions import (
    FutureTimestampException,
    NonceReplayException,
    TimestampExpiredException,
)

nonceTtlSeconds: int = 120
minNtpDriftToleranceSeconds: int = 5
maxNtpDriftToleranceSeconds: int = 60
nonceRedisKeyPrefix: str = "razoragent:nonce:"


class NonceLedger:
    """Tracks and validates nonces against replay attacks and clock drift."""

    def __init__(self, redisClient: Any) -> None:
        self._redis = redisClient

    def verifyTimestampWindow(
        self,
        timestamp: int,
        serverTime: Optional[int] = None,
    ) -> bool:
        """Enforces that the client timestamp is within [T - 5s, T + 60s]."""
        currentTime = serverTime if serverTime is not None else int(time.time())
        minAllowed = currentTime - minNtpDriftToleranceSeconds
        maxAllowed = currentTime + maxNtpDriftToleranceSeconds

        if timestamp < minAllowed:
            raise TimestampExpiredException(
                f"Timestamp expired: {timestamp} is older than allowed window {minAllowed}"
            )
        if timestamp > maxAllowed:
            raise FutureTimestampException(
                f"Future timestamp detected: {timestamp} exceeds allowed future drift {maxAllowed}"
            )
        return True

    async def validateAndRecordNonce(
        self,
        nonce: str,
        timestamp: int,
        serverTime: Optional[int] = None,
    ) -> bool:
        """Validates timestamp window and records nonce atomically in Redis."""
        self.verifyTimestampWindow(timestamp=timestamp, serverTime=serverTime)
        redisKey = f"{nonceRedisKeyPrefix}{nonce}"

        # SET key 1 EX 120 NX returns True if key was set, None/False if already exists
        resultSet = await self._redis.set(redisKey, "1", ex=nonceTtlSeconds, nx=True)
        if not resultSet:
            raise NonceReplayException(
                f"Replay attack detected (409): nonce '{nonce}' has already been consumed"
            )
        return True
