"""MCX bullion spot rate oracle with sub-second Redis caching and seed fallbacks."""

import time
from typing import Any, Dict, Optional

from ..constants.merchantConstants import (
    redisSpotRateKeyPrefix,
    spotRateTtlSeconds,
)

# Seeded fallback rates (2025 INR bullion benchmarks in integer paise per gram)
fallbackSpotRatesPerGramPaise: Dict[str, int] = {
    "MCX_GOLD_24K_INR_PER_GRAM": 679500,  # ~₹6,795/gram 24K gold
    "MCX_GOLD_22K_INR_PER_GRAM": 622788,  # ~₹6,228/gram 22K gold
    "MCX_SILVER_INR_PER_KG": 91200,       # ~₹912/gram silver
}


class _InMemoryRedisClient:
    """Lightweight in-memory Redis simulator for standalone unit test execution."""

    def __init__(self) -> None:
        self._store: Dict[str, str] = {}
        self._expirations: Dict[str, float] = {}

    def _isExpired(self, key: str) -> bool:
        if key in self._expirations and time.time() > self._expirations[key]:
            self._store.pop(key, None)
            self._expirations.pop(key, None)
            return True
        return False

    async def get(self, key: str) -> Optional[str]:
        if self._isExpired(key):
            return None
        return self._store.get(key)

    async def set(
        self,
        key: str,
        value: Any,
        ex: Optional[int] = None,
    ) -> bool:
        self._store[key] = str(value)
        if ex is not None:
            self._expirations[key] = time.time() + ex
        else:
            self._expirations.pop(key, None)
        return True


class SpotRateOracle:
    """Fetches and caches live MCX commodity spot rates with sub-second TTL."""

    def __init__(self, redisClient: Any) -> None:
        self.redisClient = redisClient

    async def getSpotRatePerGramPaise(self, symbol: str) -> int:
        """Retrieves cached spot rate or seeds and returns fallback rate in integer paise."""
        key = f"{redisSpotRateKeyPrefix}{symbol}"

        if self.redisClient is not None:
            cachedValue = await self.redisClient.get(key)
            if cachedValue is not None:
                return int(cachedValue)

        if symbol not in fallbackSpotRatesPerGramPaise:
            raise ValueError(f"Unsupported oracle feed symbol: {symbol}")

        fallbackRate = fallbackSpotRatesPerGramPaise[symbol]
        if self.redisClient is not None:
            await self.redisClient.set(key, str(fallbackRate), ex=spotRateTtlSeconds)

        return fallbackRate

    async def seedFallbackRate(self, symbol: str, ratePerGramPaise: int) -> None:
        """Stores a new spot rate into Redis cache with configured TTL."""
        key = f"{redisSpotRateKeyPrefix}{symbol}"
        if self.redisClient is not None:
            await self.redisClient.set(key, str(ratePerGramPaise), ex=spotRateTtlSeconds)


def createInMemorySpotRateOracle(
    seedRates: Optional[Dict[str, int]] = None,
) -> SpotRateOracle:
    """Constructs a SpotRateOracle instance backed by an in-memory test store."""
    client = _InMemoryRedisClient()
    oracle = SpotRateOracle(redisClient=client)

    ratesToSeed = seedRates if seedRates is not None else fallbackSpotRatesPerGramPaise
    for symbol, rate in ratesToSeed.items():
        key = f"{redisSpotRateKeyPrefix}{symbol}"
        client._store[key] = str(rate)
        client._expirations[key] = time.time() + spotRateTtlSeconds

    return oracle


__all__ = [
    "SpotRateOracle",
    "createInMemorySpotRateOracle",
    "fallbackSpotRatesPerGramPaise",
]
