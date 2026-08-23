import asyncio
from typing import Any, Dict, List, Tuple
import pytest

# Benchmark Constants
raceSkuId = "SKU-301"
initialUnitStock = 1
lockQuantity = 1
lockTtlSeconds = 60


async def attemptReserveInventoryLock(
    mockRedis: Any,
    skuId: str,
    quantity: int,
    lockToken: str,
    ttlSeconds: int = lockTtlSeconds,
) -> Tuple[int, int]:
    """Invokes atomic Redis Lua script for inventory locking."""
    stockKey = f"sku:{skuId}:stock"
    fencingKey = f"sku:{skuId}:fence"

    # Evaluates atomic Lua script
    result = await mockRedis.eval(
        "", 2, stockKey, fencingKey, quantity, lockToken, ttlSeconds
    )
    status, tokenOrStock = result[0], result[1]
    return status, tokenOrStock


@pytest.mark.asyncio
async def testTc09ConcurrencyDoubleLockRace(mockRedisClient: Any) -> None:
    """TC-09: Concurrency Double Lock — 2 parallel locks on 1 unit: exactly 1 succeeds, 1 gets 409."""
    stockKey = f"sku:{raceSkuId}:stock"
    # Ensure stock is exactly 1 unit
    await mockRedisClient.set(stockKey, initialUnitStock)

    tokenA = "lock_token_agent_alpha_tc09"
    tokenB = "lock_token_agent_beta_tc09"

    # Launch two asynchronous concurrent lock requests at the exact same moment
    taskA = asyncio.create_task(
        attemptReserveInventoryLock(mockRedisClient, raceSkuId, lockQuantity, tokenA)
    )
    taskB = asyncio.create_task(
        attemptReserveInventoryLock(mockRedisClient, raceSkuId, lockQuantity, tokenB)
    )

    results = await asyncio.gather(taskA, taskB)
    resultA, resultB = results[0], results[1]

    # Exactly one task must succeed (status == 1) and exactly one must fail (status == -1)
    statuses = [resultA[0], resultB[0]]
    assert statuses.count(1) == 1, f"Expected exactly 1 success, got {statuses}"
    assert statuses.count(-1) == 1, f"Expected exactly 1 failure (409), got {statuses}"

    # Verify monotonic fencing token on success
    successfulResult = resultA if resultA[0] == 1 else resultB
    assert successfulResult[1] >= 1  # Monotonic fencing token >= 1

    # Invariant: Redis inventory stock must be exactly 0 (no negative allocation)
    finalStock = int(await mockRedisClient.get(stockKey) or 0)
    assert finalStock == 0


@pytest.mark.asyncio
async def testTc09LockExhaustedStockRejection(mockRedisClient: Any) -> None:
    """Verifies that subsequent lock attempts on 0 stock are immediately rejected with -1."""
    stockKey = f"sku:{raceSkuId}:stock"
    await mockRedisClient.set(stockKey, 0)

    status, stock = await attemptReserveInventoryLock(
        mockRedisClient, raceSkuId, 1, "lock_token_rejected_001"
    )
    assert status == -1
    assert stock == 0
