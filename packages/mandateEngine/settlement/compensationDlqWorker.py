"""Asynchronous background worker that drains the 2PC compensation dead-letter queue.

Split out of compensationDlq.py so each module stays within the 300-line limit in
.agents/rules/code-style.md. The queue (CompensationDlq) is storage; this is the process that
drains it, and the two change for different reasons.
"""

import asyncio
from typing import Any, Callable, Coroutine, Optional

from .compensationDlq import (
    CompensationDlq,
    CompensationEvent,
    defaultBackoffMultiplier,
    defaultInitialBackoffSeconds,
    defaultMaxBackoffSeconds,
    statusCompensated,
    statusDeadLetter,
    statusPending,
    statusProcessing,
)
from .razorpayRouteClient import RazorpayRouteClient

__all__ = ["CompensationDlqWorker"]


class CompensationDlqWorker:
    """Asynchronous background worker for processing DLQ compensation events with exponential backoff."""

    def __init__(
        self,
        routeClient: RazorpayRouteClient,
        dlq: CompensationDlq,
        initialBackoffSeconds: float = defaultInitialBackoffSeconds,
        backoffMultiplier: float = defaultBackoffMultiplier,
        maxBackoffSeconds: float = defaultMaxBackoffSeconds,
        sleepFunc: Optional[Callable[[float], Coroutine[Any, Any, None]]] = None,
    ) -> None:
        self.routeClient = routeClient
        self.dlq = dlq
        self.initialBackoffSeconds = initialBackoffSeconds
        self.backoffMultiplier = backoffMultiplier
        self.maxBackoffSeconds = maxBackoffSeconds
        self._sleep = sleepFunc or asyncio.sleep

    def computeBackoffDelay(self, retryCount: int) -> float:
        """Computes exponential backoff delay for given retry attempt: initial * (multiplier ** (retryCount - 1))."""
        if retryCount <= 0:
            return 0.0
        delay = self.initialBackoffSeconds * (self.backoffMultiplier ** (retryCount - 1))
        return min(delay, self.maxBackoffSeconds)

    async def processNext(self) -> Optional[CompensationEvent]:
        """Pulls and executes the next pending compensation reversal."""
        event = await self.dlq.popPendingEvent()
        if event is None:
            return None

        if await self.dlq.isAlreadyCompensated(event.transferId):
            return event.model_copy(update={"status": statusCompensated})

        try:
            reversalResp = await self.routeClient.reverseTransfer(
                transferId=event.transferId,
                amountPaise=event.amountPaise,
                # This worker retries with backoff, so a reversal that timed out after the
                # provider accepted it would otherwise be issued twice. The event carried an
                # idempotencyKey from the start; it was simply never sent.
                idempotencyKey=event.idempotencyKey,
            )
            await self.dlq.markCompensated(event.transferId, reversalId=reversalResp.id)
            return event.model_copy(
                update={
                    "status": statusCompensated,
                    "metadata": {**event.metadata, "reversalId": reversalResp.id},
                }
            )
        except Exception as err:
            newRetryCount = event.retryCount + 1
            if newRetryCount >= event.maxRetries:
                escalatedEvent = event.model_copy(
                    update={
                        "retryCount": newRetryCount,
                        "status": statusDeadLetter,
                        "reason": f"Max retries ({event.maxRetries}) exceeded: {str(err)}",
                        "metadata": {**event.metadata, "lastError": str(err)},
                    }
                )
                await self.dlq.escalateToDeadLetter(escalatedEvent)
                return escalatedEvent
            else:
                delay = self.computeBackoffDelay(newRetryCount)
                await self._sleep(delay)
                retryEvent = event.model_copy(
                    update={
                        "retryCount": newRetryCount,
                        "status": statusPending,
                        "reason": f"Retry {newRetryCount}/{event.maxRetries}: {str(err)}",
                        "metadata": {**event.metadata, "lastError": str(err)},
                    }
                )
                await self.dlq.requeueEvent(retryEvent)
                return retryEvent

    async def processAllPending(self, maxIterations: int = 1000) -> int:
        """Processes all pending events until queue is empty or maxIterations reached."""
        count = 0
        for _ in range(maxIterations):
            res = await self.processNext()
            if res is None:
                break
            count += 1
        return count

    async def runWorkerLoop(
        self,
        pollIntervalSeconds: float = 1.0,
        stopEvent: Optional[asyncio.Event] = None,
    ) -> None:
        """Runs continuous background polling loop until stopEvent is signaled."""
        while stopEvent is None or not stopEvent.is_set():
            event = await self.processNext()
            if event is None:
                if stopEvent is not None:
                    try:
                        await asyncio.wait_for(stopEvent.wait(), timeout=pollIntervalSeconds)
                        break
                    except asyncio.TimeoutError:
                        pass
                else:
                    await self._sleep(pollIntervalSeconds)
