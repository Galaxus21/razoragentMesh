"""Redis-backed Dead Letter Queue (DLQ) and Asynchronous Compensation Worker."""

import asyncio
import time
from typing import Any, Callable, Coroutine, Optional
import uuid
from pydantic import BaseModel, ConfigDict, Field

from ..verification.arithmeticEnclave import validateIntegerPaise
from .razorpayRouteClient import RazorpayRouteClient

# Redis Key Namespaces and Prefixes
dlqPendingQueueKey: str = "razoragent:dlq:pending"
dlqDeadLetterQueueKey: str = "razoragent:dlq:dead_letter"
dlqEventRecordPrefix: str = "razoragent:dlq:event:"
dlqIdempotencyPrefix: str = "razoragent:dlq:idemp:"
dlqCompensatedPrefix: str = "razoragent:dlq:compensated:"

# Default Operational Parameters
defaultIdempotencyTtlSeconds: int = 604800  # 7 days
defaultCompensatedTtlSeconds: int = 2592000  # 30 days
defaultMaxRetries: int = 5
defaultInitialBackoffSeconds: float = 0.5
defaultBackoffMultiplier: float = 2.0
defaultMaxBackoffSeconds: float = 30.0

# Status Constants
statusPending: str = "PENDING"
statusProcessing: str = "PROCESSING"
statusCompensated: str = "COMPENSATED"
statusDeadLetter: str = "DEAD_LETTER"


class CompensationEventStatus:
    """Enumeration constants for compensation event lifecycle states."""

    PENDING: str = statusPending
    PROCESSING: str = statusProcessing
    COMPENSATED: str = statusCompensated
    DEAD_LETTER: str = statusDeadLetter


class CompensationEvent(BaseModel):
    """Frozen immutable model representing a failed 2PC settlement split reversal."""

    model_config = ConfigDict(frozen=True, extra="forbid")

    eventId: str = Field(
        default_factory=lambda: f"dlq_evt_{uuid.uuid4().hex[:12]}",
        min_length=1,
        description="Unique identifier for DLQ event",
    )
    idempotencyKey: str = Field(
        min_length=1,
        description="Unique deduplication key for reversal operation",
    )
    transferId: str = Field(
        min_length=1,
        description="Razorpay Route transfer ID (trf_...)",
    )
    amountPaise: int = Field(
        gt=0,
        description="Conserved integer paise to reverse",
    )
    recipientAccountId: Optional[str] = Field(
        default=None,
        description="Linked recipient vendor account ID (acc_...)",
    )
    paymentId: Optional[str] = Field(
        default=None,
        description="Primary Razorpay payment ID (pay_...)",
    )
    reason: str = Field(
        default="",
        description="Failure cause or exception description",
    )
    retryCount: int = Field(
        default=0,
        ge=0,
        description="Number of retry attempts executed",
    )
    maxRetries: int = Field(
        default=defaultMaxRetries,
        ge=1,
        description="Maximum retry threshold before DLQ escalation",
    )
    status: str = Field(
        default=statusPending,
        description="Lifecycle status: PENDING | PROCESSING | COMPENSATED | DEAD_LETTER",
    )
    createdAt: int = Field(
        default_factory=lambda: int(time.time()),
        gt=0,
        description="Unix timestamp in seconds when event was enqueued",
    )
    metadata: dict[str, Any] = Field(
        default_factory=dict,
        description="Arbitrary contextual diagnostics and audit trace",
    )


class CompensationDlq:
    """Redis-backed Dead Letter Queue manager for 2PC compensation failures."""

    def __init__(
        self,
        redisClient: Any = None,
        pendingQueueKey: str = dlqPendingQueueKey,
        deadLetterQueueKey: str = dlqDeadLetterQueueKey,
        defaultMaxRetries: int = defaultMaxRetries,
    ) -> None:
        self._redis = redisClient
        self.pendingQueueKey = pendingQueueKey
        self.deadLetterQueueKey = deadLetterQueueKey
        self.defaultMaxRetries = defaultMaxRetries
        self._inMemoryLists: dict[str, list[str]] = {}
        self._inMemoryStore: dict[str, Any] = {}

    async def _get(self, key: str) -> Optional[str]:
        if self._redis is None:
            val = self._inMemoryStore.get(key)
            return str(val) if val is not None else None
        res = self._redis.get(key)
        if asyncio.iscoroutine(res):
            res = await res
        if res is None:
            return None
        return res if isinstance(res, str) else res.decode("utf-8")

    async def _set(self, key: str, value: Any, ex: Optional[int] = None, nx: bool = False) -> bool:
        if self._redis is None:
            if nx and key in self._inMemoryStore:
                return False
            self._inMemoryStore[key] = value
            return True
        res = self._redis.set(key, value, ex=ex, nx=nx)
        if asyncio.iscoroutine(res):
            res = await res
        return bool(res)

    async def _rpush(self, key: str, value: str) -> None:
        if self._redis is not None and hasattr(self._redis, "rpush"):
            res = self._redis.rpush(key, value)
            if asyncio.iscoroutine(res):
                await res
        elif self._redis is not None and hasattr(self._redis, "store") and isinstance(getattr(self._redis, "store"), dict):
            store = self._redis.store
            store.setdefault(key, []).append(value)
        else:
            self._inMemoryLists.setdefault(key, []).append(value)

    async def _lpop(self, key: str) -> Optional[str]:
        if self._redis is not None and hasattr(self._redis, "lpop"):
            res = self._redis.lpop(key)
            if asyncio.iscoroutine(res):
                res = await res
            if res is None:
                return None
            return res if isinstance(res, str) else res.decode("utf-8")
        elif self._redis is not None and hasattr(self._redis, "store") and isinstance(getattr(self._redis, "store"), dict):
            lst = self._redis.store.get(key)
            if isinstance(lst, list) and len(lst) > 0:
                item = lst.pop(0)
                return item if isinstance(item, str) else item.decode("utf-8")
            return None
        else:
            lst = self._inMemoryLists.get(key, [])
            if lst and len(lst) > 0:
                return lst.pop(0)
            return None

    async def _llen(self, key: str) -> int:
        if self._redis is not None and hasattr(self._redis, "llen"):
            res = self._redis.llen(key)
            if asyncio.iscoroutine(res):
                res = await res
            return int(res or 0)
        elif self._redis is not None and hasattr(self._redis, "store") and isinstance(getattr(self._redis, "store"), dict):
            lst = self._redis.store.get(key)
            return len(lst) if isinstance(lst, list) else 0
        else:
            return len(self._inMemoryLists.get(key, []))

    async def _lrange(self, key: str, start: int, stop: int) -> list[str]:
        if self._redis is not None and hasattr(self._redis, "lrange"):
            res = self._redis.lrange(key, start, stop)
            if asyncio.iscoroutine(res):
                res = await res
            if not res:
                return []
            return [item if isinstance(item, str) else item.decode("utf-8") for item in res]
        elif self._redis is not None and hasattr(self._redis, "store") and isinstance(getattr(self._redis, "store"), dict):
            lst = self._redis.store.get(key, [])
            if isinstance(lst, list):
                end = None if stop == -1 else stop + 1
                sliceItems = lst[start:end]
                return [item if isinstance(item, str) else item.decode("utf-8") for item in sliceItems]
            return []
        else:
            lst = self._inMemoryLists.get(key, [])
            end = None if stop == -1 else stop + 1
            return lst[start:end]

    async def isAlreadyCompensated(self, transferId: str) -> bool:
        """Checks if a transfer has already been successfully reversed."""
        key = f"{dlqCompensatedPrefix}{transferId}"
        val = await self._get(key)
        return bool(val)

    async def markCompensated(
        self,
        transferId: str,
        reversalId: Optional[str] = None,
        ttlSeconds: int = defaultCompensatedTtlSeconds,
    ) -> None:
        """Records transfer reversal tombstone in Redis."""
        key = f"{dlqCompensatedPrefix}{transferId}"
        val = reversalId or statusCompensated
        await self._set(key, val, ex=ttlSeconds)

    async def enqueueReversal(
        self,
        transferId: str,
        amountPaise: int,
        recipientAccountId: Optional[str] = None,
        paymentId: Optional[str] = None,
        reason: str = "",
        metadata: Optional[dict[str, Any]] = None,
        maxRetries: Optional[int] = None,
        idempotencyKey: Optional[str] = None,
    ) -> CompensationEvent:
        """Idempotently enqueues a failed transfer reversal into the Redis pending queue."""
        validateIntegerPaise(amountPaise, "amountPaise")

        if await self.isAlreadyCompensated(transferId):
            return CompensationEvent(
                idempotencyKey=idempotencyKey or f"cmp_{transferId}",
                transferId=transferId,
                amountPaise=amountPaise,
                recipientAccountId=recipientAccountId,
                paymentId=paymentId,
                reason=reason or "Already compensated",
                status=statusCompensated,
                metadata=metadata or {},
            )

        idemKey = idempotencyKey or f"cmp_{transferId}"
        idemRedisKey = f"{dlqIdempotencyPrefix}{idemKey}"

        existingRecord = await self._get(idemRedisKey)
        if existingRecord:
            try:
                return CompensationEvent.model_validate_json(existingRecord)
            except Exception:
                pass

        event = CompensationEvent(
            idempotencyKey=idemKey,
            transferId=transferId,
            amountPaise=amountPaise,
            recipientAccountId=recipientAccountId,
            paymentId=paymentId,
            reason=reason,
            retryCount=0,
            maxRetries=maxRetries or self.defaultMaxRetries,
            status=statusPending,
            metadata=metadata or {},
        )
        eventJson = event.model_dump_json()

        await self._set(idemRedisKey, eventJson, ex=defaultIdempotencyTtlSeconds, nx=True)
        eventKey = f"{dlqEventRecordPrefix}{event.eventId}"
        await self._set(eventKey, eventJson, ex=defaultIdempotencyTtlSeconds)
        await self._rpush(self.pendingQueueKey, eventJson)
        return event

    async def popPendingEvent(self) -> Optional[CompensationEvent]:
        """Pops the next pending compensation event from the Redis queue."""
        rawStr = await self._lpop(self.pendingQueueKey)
        if not rawStr:
            return None
        return CompensationEvent.model_validate_json(rawStr)

    async def requeueEvent(self, event: CompensationEvent) -> None:
        """Re-enqueues an updated retry event back to the pending queue."""
        eventJson = event.model_dump_json()
        eventKey = f"{dlqEventRecordPrefix}{event.eventId}"
        await self._set(eventKey, eventJson, ex=defaultIdempotencyTtlSeconds)
        await self._rpush(self.pendingQueueKey, eventJson)

    async def escalateToDeadLetter(self, event: CompensationEvent) -> None:
        """Escalates a permanently failed compensation event to the dead letter queue."""
        escalated = (
            event.model_copy(update={"status": statusDeadLetter})
            if event.status != statusDeadLetter
            else event
        )
        eventJson = escalated.model_dump_json()
        eventKey = f"{dlqEventRecordPrefix}{escalated.eventId}"
        await self._set(eventKey, eventJson, ex=defaultIdempotencyTtlSeconds)
        await self._rpush(self.deadLetterQueueKey, eventJson)

    async def getPendingQueueLength(self) -> int:
        """Returns the number of pending compensation events in the queue."""
        return await self._llen(self.pendingQueueKey)

    async def getPendingCount(self) -> int:
        """Alias for getPendingQueueLength."""
        return await self.getPendingQueueLength()

    async def getDeadLetterQueueLength(self) -> int:
        """Returns the number of escalated dead letter events."""
        return await self._llen(self.deadLetterQueueKey)

    async def getDeadLetterCount(self) -> int:
        """Alias for getDeadLetterQueueLength."""
        return await self.getDeadLetterQueueLength()

    async def getDeadLetterEvents(self) -> list[CompensationEvent]:
        """Returns all events currently stored in the dead letter queue."""
        rawList = await self._lrange(self.deadLetterQueueKey, 0, -1)
        return [CompensationEvent.model_validate_json(item) for item in rawList]

    async def getEvent(self, eventId: str) -> Optional[CompensationEvent]:
        """Retrieves a specific compensation event by its event ID."""
        eventKey = f"{dlqEventRecordPrefix}{eventId}"
        rawStr = await self._get(eventKey)
        if not rawStr:
            return None
        return CompensationEvent.model_validate_json(rawStr)


def __getattr__(name: str):
    """Re-exports CompensationDlqWorker from its own module.

    Kept as a lazy attribute rather than a top-level import to avoid a circular import:
    compensationDlqWorker imports this module. Existing
    `from .compensationDlq import CompensationDlqWorker` call sites continue to work.
    """
    if name == "CompensationDlqWorker":
        from .compensationDlqWorker import CompensationDlqWorker as _Worker
        return _Worker
    raise AttributeError(f"module {__name__!r} has no attribute {name!r}")
