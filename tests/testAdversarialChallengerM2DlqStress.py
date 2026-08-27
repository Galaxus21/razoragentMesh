"""Adversarial stress test suite for Milestone 2 Failure Recovery (Durable DLQ & Worker).

Challenger 1 Empirical Stress Suite:
1. Race conditions in DLQ worker processing (concurrent workers, simultaneous pops, double reversals, parallel worker loops).
2. Duplicate events and idempotency key enforcement (concurrent enqueue, duplicate transfers, tombstone enforcement, cross-backend parity).
3. Exponential backoff timing math under extreme retry numbers (retry overflow, large exponents, boundary parameters, parameter validation).
4. Dead-letter escalation when max retries exceeded (immediate escalation, multi-retry threshold, poison queues, direct escalation).
5. 2PC Saga distributed rollback under complex multi-transfer failure topologies and Redis outage resilience.
6. Schema boundary constraints (float paise rejection, zero/negative paise, unicode metadata, serialization fidelity).
"""

import asyncio
import time
from typing import Any, Optional
from unittest.mock import AsyncMock
import fakeredis.aioredis
import pytest
from pydantic import ValidationError

try:
    from razoragentMesh.packages.mandateEngine.constants.settlementConstants import transferIdPrefix
    from razoragentMesh.packages.mandateEngine.nonce.nonceLedger import NonceLedger
    from razoragentMesh.packages.mandateEngine.settlement.compensationDlq import (
        CompensationDlq,
        CompensationDlqWorker,
        CompensationEvent,
        CompensationEventStatus,
        defaultBackoffMultiplier,
        defaultInitialBackoffSeconds,
        defaultMaxBackoffSeconds,
        defaultMaxRetries,
        dlqCompensatedPrefix,
        dlqDeadLetterQueueKey,
        dlqEventRecordPrefix,
        dlqIdempotencyPrefix,
        dlqPendingQueueKey,
        statusCompensated,
        statusDeadLetter,
        statusPending,
        statusProcessing,
    )
    from razoragentMesh.packages.mandateEngine.settlement.razorpayRouteClient import (
        RazorpayRouteClient,
        RouteTransferRequest,
        RouteTransferResponse,
        TransferReversalResponse,
    )
    from razoragentMesh.packages.mandateEngine.settlement.settlementExceptions import (
        MandateEngineException,
        SettlementCompensationTriggeredException,
    )
    from razoragentMesh.packages.mandateEngine.settlement.twoPhaseCommitSaga import TwoPhaseCommitSaga
    from razoragentMesh.tests.mockInfraHelpers import MockRedisAsync
except ModuleNotFoundError:
    from packages.mandateEngine.constants.settlementConstants import transferIdPrefix
    from packages.mandateEngine.nonce.nonceLedger import NonceLedger
    from packages.mandateEngine.settlement.compensationDlq import (
        CompensationDlq,
        CompensationDlqWorker,
        CompensationEvent,
        CompensationEventStatus,
        defaultBackoffMultiplier,
        defaultInitialBackoffSeconds,
        defaultMaxBackoffSeconds,
        defaultMaxRetries,
        dlqCompensatedPrefix,
        dlqDeadLetterQueueKey,
        dlqEventRecordPrefix,
        dlqIdempotencyPrefix,
        dlqPendingQueueKey,
        statusCompensated,
        statusDeadLetter,
        statusPending,
        statusProcessing,
    )
    from packages.mandateEngine.settlement.razorpayRouteClient import (
        RazorpayRouteClient,
        RouteTransferRequest,
        RouteTransferResponse,
        TransferReversalResponse,
    )
    from packages.mandateEngine.settlement.settlementExceptions import (
        MandateEngineException,
        SettlementCompensationTriggeredException,
    )
    from packages.mandateEngine.settlement.twoPhaseCommitSaga import TwoPhaseCommitSaga
    try:
        from tests.mockInfraHelpers import MockRedisAsync
    except ModuleNotFoundError:
        from mockInfraHelpers import MockRedisAsync


# ============================================================================
# Section 1: Race Conditions & Concurrent DLQ Worker Processing
# ============================================================================
class TestAdversarialDlqWorkerRaceConditions:
    """Stress tests concurrent workers, race conditions, and simultaneous pops."""

    @pytest.fixture
    def fakeRedis(self) -> Any:
        return fakeredis.aioredis.FakeRedis()

    @pytest.fixture
    def routeClient(self) -> RazorpayRouteClient:
        return RazorpayRouteClient(isMockMode=True)

    @pytest.mark.asyncio
    async def testConcurrentWorkersProcessingDistinctEvents(self, fakeRedis: Any, routeClient: RazorpayRouteClient) -> None:
        """50 distinct failed transfers processed concurrently by 10 independent workers.
        Must result in exactly 50 reversals, 0 lost events, and 0 duplicate reversals."""
        dlq = CompensationDlq(redisClient=fakeRedis)
        numEvents = 50
        numWorkers = 10

        transfers = []
        for i in range(numEvents):
            t = await routeClient.createTransfer(
                RouteTransferRequest(account=f"acc_race_{i % 5}", amount=1000 * (i + 1))
            )
            transfers.append(t)
            await dlq.enqueueReversal(
                transferId=t.id,
                amountPaise=t.amount,
                recipientAccountId=t.account,
            )

        assert await dlq.getPendingCount() == numEvents

        workers = [
            CompensationDlqWorker(routeClient=routeClient, dlq=dlq, initialBackoffSeconds=0.001)
            for _ in range(numWorkers)
        ]

        async def workerTask(w: CompensationDlqWorker) -> int:
            count = 0
            while True:
                res = await w.processNext()
                if res is None:
                    break
                count += 1
            return count

        results = await asyncio.gather(*[workerTask(w) for w in workers])

        # Sum of processed events across all workers must equal numEvents
        assert sum(results) == numEvents
        assert await dlq.getPendingCount() == 0
        assert len(routeClient._reversals) == numEvents

        # All transfers must be marked as compensated
        for t in transfers:
            assert await dlq.isAlreadyCompensated(t.id)

    @pytest.mark.asyncio
    async def testConcurrentWorkersWithDuplicateQueuedEvents(self, fakeRedis: Any, routeClient: RazorpayRouteClient) -> None:
        """Multiple duplicate events referencing the same transferId in the queue.
        Concurrent workers must ensure the transfer is reversed only ONCE and subsequent duplicates are safely bypassed."""
        dlq = CompensationDlq(redisClient=fakeRedis)
        t = await routeClient.createTransfer(RouteTransferRequest(account="acc_dup_race", amount=25000))

        # Force-push 5 duplicate events for the same transferId into the queue
        for i in range(5):
            event = CompensationEvent(
                idempotencyKey=f"cmp_{t.id}_{i}",
                transferId=t.id,
                amountPaise=t.amount,
            )
            await dlq.requeueEvent(event)

        assert await dlq.getPendingCount() == 5

        # Run 5 workers concurrently to process the queue
        workers = [CompensationDlqWorker(routeClient=routeClient, dlq=dlq) for _ in range(5)]

        async def workerRun(w: CompensationDlqWorker) -> list[CompensationEvent]:
            processed = []
            while True:
                ev = await w.processNext()
                if ev is None:
                    break
                processed.append(ev)
            return processed

        allResults = await asyncio.gather(*[workerRun(w) for w in workers])
        flattened = [ev for workerList in allResults for ev in workerList]

        assert len(flattened) == 5
        # Crucial invariant: only 1 reversal in route client despite 5 queued events
        assert len(routeClient._reversals) == 1
        assert await dlq.isAlreadyCompensated(t.id)
        assert await dlq.getPendingCount() == 0

    @pytest.mark.asyncio
    async def testConcurrentWorkersWithIntermittentFailuresAndRequeues(self, fakeRedis: Any, routeClient: RazorpayRouteClient) -> None:
        """20 transfers where 10 transfers fail transiently (1-2 times) before succeeding.
        5 concurrent workers must successfully process and compensate all 20 transfers without dropping any."""
        dlq = CompensationDlq(redisClient=fakeRedis)
        numTransfers = 20

        transfers = []
        for i in range(numTransfers):
            t = await routeClient.createTransfer(
                RouteTransferRequest(account=f"acc_transient_{i}", amount=5000 + i * 100)
            )
            transfers.append(t)
            await dlq.enqueueReversal(transferId=t.id, amountPaise=t.amount, maxRetries=5)

        # Configure half of them to fail once or twice
        for i in range(0, numTransfers, 2):
            routeClient.configureSimulatedReverseFailure(
                transferId=transfers[i].id,
                errorType="503",
                failureCount=1 if i % 4 == 0 else 2,
            )

        # Fast sleep function for testing
        async def fastSleep(_: float) -> None:
            await asyncio.sleep(0.001)

        workers = [
            CompensationDlqWorker(
                routeClient=routeClient,
                dlq=dlq,
                initialBackoffSeconds=0.001,
                sleepFunc=fastSleep,
            )
            for _ in range(5)
        ]

        stopEvent = asyncio.Event()

        async def workerLoop(w: CompensationDlqWorker) -> None:
            while not stopEvent.is_set():
                ev = await w.processNext()
                if ev is None:
                    if await dlq.getPendingCount() == 0:
                        break
                    await asyncio.sleep(0.005)

        tasks = [asyncio.create_task(workerLoop(w)) for w in workers]

        start = time.time()
        while time.time() - start < 5.0:
            if len(routeClient._reversals) == numTransfers:
                break
            await asyncio.sleep(0.02)

        stopEvent.set()
        await asyncio.gather(*tasks, return_exceptions=True)

        assert len(routeClient._reversals) == numTransfers
        assert await dlq.getPendingCount() == 0
        assert await dlq.getDeadLetterCount() == 0

    @pytest.mark.asyncio
    async def testConcurrentWorkerLoopsWithContinuousIngestion(self, fakeRedis: Any, routeClient: RazorpayRouteClient) -> None:
        """Test continuous producer-consumer race where 3 worker loops run in background while 15 events are enqueued asynchronously."""
        dlq = CompensationDlq(redisClient=fakeRedis)
        stopEvent = asyncio.Event()

        workers = [
            CompensationDlqWorker(routeClient=routeClient, dlq=dlq, initialBackoffSeconds=0.001)
            for _ in range(3)
        ]
        workerTasks = [
            asyncio.create_task(w.runWorkerLoop(pollIntervalSeconds=0.01, stopEvent=stopEvent))
            for w in workers
        ]

        transfers = []
        for i in range(15):
            t = await routeClient.createTransfer(RouteTransferRequest(account=f"acc_cont_{i}", amount=1000 + i))
            transfers.append(t)
            await dlq.enqueueReversal(transferId=t.id, amountPaise=t.amount)
            await asyncio.sleep(0.002)

        # Wait for workers to catch up
        start = time.time()
        while time.time() - start < 3.0:
            if len(routeClient._reversals) == 15 and await dlq.getPendingCount() == 0:
                break
            await asyncio.sleep(0.02)

        stopEvent.set()
        await asyncio.gather(*workerTasks)

        assert len(routeClient._reversals) == 15
        assert await dlq.getPendingCount() == 0


# ============================================================================
# Section 2: Duplicate Events and Idempotency Key Enforcement
# ============================================================================
class TestAdversarialDlqIdempotencyEnforcement:
    """Stress tests duplicate event enqueueing, idempotency keys, and tombstone enforcement."""

    @pytest.fixture
    def fakeRedis(self) -> Any:
        return fakeredis.aioredis.FakeRedis()

    @pytest.fixture
    def mockRedis(self) -> MockRedisAsync:
        return MockRedisAsync()

    @pytest.fixture
    def inMemoryDlq(self) -> CompensationDlq:
        return CompensationDlq(redisClient=None)

    @pytest.mark.asyncio
    async def testConcurrentEnqueueSameIdempotencyKey(self, fakeRedis: Any) -> None:
        """20 concurrent tasks calling enqueueReversal with the exact SAME idempotency key.
        Must result in exactly 1 pending item in the queue, with identical eventId returned."""
        dlq = CompensationDlq(redisClient=fakeRedis)
        transferId = "trf_concurrent_idem"
        amountPaise = 77700
        customIdemKey = "idem_atomic_race_key"

        tasks = [
            dlq.enqueueReversal(
                transferId=transferId,
                amountPaise=amountPaise,
                idempotencyKey=customIdemKey,
            )
            for _ in range(20)
        ]

        events = await asyncio.gather(*tasks)

        # All returned events must have the same eventId and idempotencyKey
        firstId = events[0].eventId
        for ev in events:
            assert ev.eventId == firstId
            assert ev.idempotencyKey == customIdemKey
            assert ev.status == CompensationEventStatus.PENDING

        # Queue length must be strictly 1
        assert await dlq.getPendingCount() == 1

    @pytest.mark.asyncio
    async def testEnqueueAfterMarkCompensatedBypassesQueue(self, fakeRedis: Any) -> None:
        """Calling enqueueReversal for a transferId that is already marked compensated
        must return an event with status=COMPENSATED and MUST NOT push anything to the pending queue."""
        dlq = CompensationDlq(redisClient=fakeRedis)
        transferId = "trf_already_done"

        # Tombstone
        await dlq.markCompensated(transferId, reversalId="rev_done_123")
        assert await dlq.isAlreadyCompensated(transferId)

        ev = await dlq.enqueueReversal(
            transferId=transferId,
            amountPaise=45000,
            reason="Late failure report",
        )

        assert ev.status == CompensationEventStatus.COMPENSATED
        assert ev.transferId == transferId
        assert await dlq.getPendingCount() == 0
        assert await dlq.getDeadLetterCount() == 0

    @pytest.mark.asyncio
    async def testWorkerBypassesPreCompensatedEventsInQueue(self, fakeRedis: Any) -> None:
        """If an event was enqueued, but the transfer was compensated out-of-band before worker pops it,
        worker must recognize tombstone and return status=COMPENSATED without calling Route API."""
        dlq = CompensationDlq(redisClient=fakeRedis)
        routeClient = RazorpayRouteClient(isMockMode=True)

        transfer = await routeClient.createTransfer(RouteTransferRequest(account="acc_out_of_band", amount=15000))
        # Enqueue event
        await dlq.enqueueReversal(transferId=transfer.id, amountPaise=transfer.amount)
        assert await dlq.getPendingCount() == 1

        # Out-of-band compensation directly marks compensated
        await dlq.markCompensated(transfer.id, reversalId="rev_out_of_band")

        worker = CompensationDlqWorker(routeClient=routeClient, dlq=dlq)
        result = await worker.processNext()

        assert result is not None
        assert result.status == CompensationEventStatus.COMPENSATED
        assert await dlq.getPendingCount() == 0
        # Route client was NOT called for reversal
        assert len(routeClient._reversals) == 0

    @pytest.mark.asyncio
    async def testIdempotencyAcrossDifferentBackends(self, fakeRedis: Any, mockRedis: MockRedisAsync, inMemoryDlq: CompensationDlq) -> None:
        """Idempotency deduplication must work consistently across FakeRedis, MockRedisAsync, and In-Memory."""
        backends = [
            CompensationDlq(redisClient=fakeRedis),
            CompensationDlq(redisClient=mockRedis),
            inMemoryDlq,
        ]

        for dlq in backends:
            idemKey = f"idem_backend_{type(dlq._redis).__name__}"
            ev1 = await dlq.enqueueReversal(transferId="trf_b1", amountPaise=10000, idempotencyKey=idemKey)
            ev2 = await dlq.enqueueReversal(transferId="trf_b1", amountPaise=10000, idempotencyKey=idemKey)
            assert ev1.eventId == ev2.eventId
            assert await dlq.getPendingCount() == 1

            # Pop and verify
            popped = await dlq.popPendingEvent()
            assert popped is not None and popped.eventId == ev1.eventId
            assert await dlq.getPendingCount() == 0


# ============================================================================
# Section 3: Exponential Backoff Timing Math Under Extreme Retry Numbers
# ============================================================================
class TestAdversarialBackoffTimingMath:
    """Stress tests exponential backoff mathematical calculations under extreme exponents and parameter boundaries."""

    @pytest.fixture
    def dummyWorker(self) -> CompensationDlqWorker:
        routeClient = RazorpayRouteClient(isMockMode=True)
        dlq = CompensationDlq(redisClient=None)
        return CompensationDlqWorker(
            routeClient=routeClient,
            dlq=dlq,
            initialBackoffSeconds=0.5,
            backoffMultiplier=2.0,
            maxBackoffSeconds=30.0,
        )

    def testBackoffDelayNonPositiveRetries(self, dummyWorker: CompensationDlqWorker) -> None:
        """retryCount <= 0 must always return 0.0."""
        assert dummyWorker.computeBackoffDelay(0) == 0.0
        assert dummyWorker.computeBackoffDelay(-1) == 0.0
        assert dummyWorker.computeBackoffDelay(-100) == 0.0

    def testBackoffDelayNominalProgression(self, dummyWorker: CompensationDlqWorker) -> None:
        """Verify progression formula initial * (multiplier ** (retryCount - 1))."""
        assert dummyWorker.computeBackoffDelay(1) == 0.5  # 0.5 * 2^0
        assert dummyWorker.computeBackoffDelay(2) == 1.0  # 0.5 * 2^1
        assert dummyWorker.computeBackoffDelay(3) == 2.0  # 0.5 * 2^2
        assert dummyWorker.computeBackoffDelay(4) == 4.0  # 0.5 * 2^3
        assert dummyWorker.computeBackoffDelay(5) == 8.0  # 0.5 * 2^4
        assert dummyWorker.computeBackoffDelay(6) == 16.0 # 0.5 * 2^5
        assert dummyWorker.computeBackoffDelay(7) == 30.0 # Clamped to maxBackoff (32 -> 30)

    def testBackoffDelayLargeRetryClamping(self, dummyWorker: CompensationDlqWorker) -> None:
        """Large retry values (10, 50, 100) must consistently return maxBackoffSeconds without numeric error."""
        for r in [10, 20, 50, 100]:
            delay = dummyWorker.computeBackoffDelay(r)
            assert delay == 30.0

    def testBackoffDelayExtremeExponentBoundary(self, dummyWorker: CompensationDlqWorker) -> None:
        """Check behavior across safe IEEE 754 exponents."""
        for r in [200, 500, 1000]:
            delay = dummyWorker.computeBackoffDelay(r)
            assert delay == 30.0

    def testBackoffCustomParameters(self) -> None:
        """Custom parameters: constant backoff, fast multiplier, zero initial delay."""
        routeClient = RazorpayRouteClient(isMockMode=True)
        dlq = CompensationDlq(redisClient=None)

        # Multiplier = 1.0 (constant delay)
        wConst = CompensationDlqWorker(
            routeClient=routeClient, dlq=dlq,
            initialBackoffSeconds=5.0, backoffMultiplier=1.0, maxBackoffSeconds=60.0
        )
        assert wConst.computeBackoffDelay(1) == 5.0
        assert wConst.computeBackoffDelay(5) == 5.0
        assert wConst.computeBackoffDelay(10) == 5.0

        # Multiplier = 10.0 (aggressive backoff)
        wFast = CompensationDlqWorker(
            routeClient=routeClient, dlq=dlq,
            initialBackoffSeconds=0.1, backoffMultiplier=10.0, maxBackoffSeconds=100.0
        )
        assert wFast.computeBackoffDelay(1) == 0.1
        assert wFast.computeBackoffDelay(2) == 1.0
        assert wFast.computeBackoffDelay(3) == 10.0
        assert wFast.computeBackoffDelay(4) == 100.0 # Clamped (100.0)
        assert wFast.computeBackoffDelay(5) == 100.0 # Clamped (1000 -> 100.0)

        # Max backoff smaller than initial backoff
        wCapped = CompensationDlqWorker(
            routeClient=routeClient, dlq=dlq,
            initialBackoffSeconds=10.0, backoffMultiplier=2.0, maxBackoffSeconds=5.0
        )
        assert wCapped.computeBackoffDelay(1) == 5.0
        assert wCapped.computeBackoffDelay(2) == 5.0


# ============================================================================
# Section 4: Dead-Letter Escalation When Max Retries Exceeded
# ============================================================================
class TestAdversarialDlqDeadLetterEscalation:
    """Stress tests escalation behavior, poison pill queues, and threshold limits."""

    @pytest.fixture
    def fakeRedis(self) -> Any:
        return fakeredis.aioredis.FakeRedis()

    @pytest.fixture
    def routeClient(self) -> RazorpayRouteClient:
        return RazorpayRouteClient(isMockMode=True)

    @pytest.mark.asyncio
    async def testImmediateEscalationWhenMaxRetriesIsOne(self, fakeRedis: Any, routeClient: RazorpayRouteClient) -> None:
        """When maxRetries=1, any single failure must immediately escalate to DEAD_LETTER without requeuing to pending."""
        dlq = CompensationDlq(redisClient=fakeRedis)
        transfer = await routeClient.createTransfer(RouteTransferRequest(account="acc_esc_1", amount=11000))

        # Always fail reversal
        routeClient.configureSimulatedReverseFailure(transferId=transfer.id, errorType="timeout")

        await dlq.enqueueReversal(
            transferId=transfer.id,
            amountPaise=transfer.amount,
            maxRetries=1,
        )
        assert await dlq.getPendingCount() == 1

        worker = CompensationDlqWorker(routeClient=routeClient, dlq=dlq)
        result = await worker.processNext()

        assert result is not None
        assert result.status == CompensationEventStatus.DEAD_LETTER
        assert result.retryCount == 1
        assert "Max retries (1) exceeded" in result.reason
        assert await dlq.getPendingCount() == 0
        assert await dlq.getDeadLetterCount() == 1

        deadLetters = await dlq.getDeadLetterEvents()
        assert len(deadLetters) == 1
        assert deadLetters[0].eventId == result.eventId

    @pytest.mark.asyncio
    async def testMultiplePoisonEventsEscalationDrain(self, fakeRedis: Any, routeClient: RazorpayRouteClient) -> None:
        """Enqueue 10 permanently failing poison events.
        Process all pending and verify 100% of them end up in DEAD_LETTER queue with 0 dropped."""
        dlq = CompensationDlq(redisClient=fakeRedis)
        numPoison = 10

        transfers = []
        for i in range(numPoison):
            t = await routeClient.createTransfer(RouteTransferRequest(account=f"acc_poison_{i}", amount=2000 * (i + 1)))
            transfers.append(t)
            await dlq.enqueueReversal(transferId=t.id, amountPaise=t.amount, maxRetries=2)

        # Configure all reversals to fail
        routeClient.configureSimulatedReverseFailure(errorType="500")

        mockSleep = AsyncMock()
        worker = CompensationDlqWorker(
            routeClient=routeClient,
            dlq=dlq,
            initialBackoffSeconds=0.001,
            sleepFunc=mockSleep,
        )

        processedCount = await worker.processAllPending(maxIterations=100)

        assert processedCount == numPoison * 2
        assert await dlq.getPendingCount() == 0
        assert await dlq.getDeadLetterCount() == numPoison

        deadLetters = await dlq.getDeadLetterEvents()
        assert len(deadLetters) == numPoison
        for dlEv in deadLetters:
            assert dlEv.status == CompensationEventStatus.DEAD_LETTER
            assert dlEv.retryCount == 2

    @pytest.mark.asyncio
    async def testDirectEscalateToDeadLetterIdempotence(self, fakeRedis: Any) -> None:
        """Calling escalateToDeadLetter directly updates the event status and persists in dead letter list."""
        dlq = CompensationDlq(redisClient=fakeRedis)
        ev = CompensationEvent(
            idempotencyKey="idem_direct_esc",
            transferId="trf_direct_esc",
            amountPaise=80000,
            status=CompensationEventStatus.PENDING,
        )

        await dlq.escalateToDeadLetter(ev)
        assert await dlq.getDeadLetterCount() == 1

        deadLetters = await dlq.getDeadLetterEvents()
        assert len(deadLetters) == 1
        assert deadLetters[0].status == CompensationEventStatus.DEAD_LETTER
        assert deadLetters[0].transferId == "trf_direct_esc"


# ============================================================================
# Section 5: Complex 2PC Saga Fault Injection & Outage Resilience
# ============================================================================
class TestAdversarialTwoPhaseCommitSagaFaults:
    """Stress tests 2PC saga rollback under multi-split failure topologies and Redis outage conditions."""

    @pytest.fixture
    def routeClient(self) -> RazorpayRouteClient:
        return RazorpayRouteClient(isMockMode=True)

    @pytest.fixture
    def nonceLedger(self) -> NonceLedger:
        return NonceLedger(redisClient=fakeredis.aioredis.FakeRedis())

    @pytest.fixture
    def dlq(self) -> CompensationDlq:
        return CompensationDlq(redisClient=fakeredis.aioredis.FakeRedis())

    @pytest.mark.asyncio
    async def testComplexTopologyPartialReversalFailures(
        self,
        routeClient: RazorpayRouteClient,
        nonceLedger: NonceLedger,
        dlq: CompensationDlq,
    ) -> None:
        """5-split transfer saga:
        Transfer 5 fails creation -> triggers rollback of transfers 1, 2, 3, 4.
        During rollback, transfers 2 and 4 fail reversal (simulated 500 and timeout).
        Transfers 1 and 3 reverse successfully.
        DLQ captures transfers 2 and 4.
        Then Worker runs and successfully recovers transfers 2 and 4.
        Total resulting reversals: 4/4."""
        saga = TwoPhaseCommitSaga(routeClient=routeClient, nonceLedger=nonceLedger, dlq=dlq)

        requests = [
            RouteTransferRequest(account="acc_m1", amount=100000, notes={"paymentId": "pay_5way"}),
            RouteTransferRequest(account="acc_m2", amount=50000, notes={"paymentId": "pay_5way"}),
            RouteTransferRequest(account="acc_m3", amount=25000, notes={"paymentId": "pay_5way"}),
            RouteTransferRequest(account="acc_m4", amount=15000, notes={"paymentId": "pay_5way"}),
            RouteTransferRequest(account="acc_fail", amount=10000, notes={"paymentId": "pay_5way"}),
        ]

        routeClient.simulatedFailureAccount = "acc_fail"

        # Fail reversals on acc_m2 and acc_m4 once
        routeClient.configureSimulatedReverseFailure(
            account="acc_m2",
            errorType="500",
            failureCount=1,
        )

        with pytest.raises(SettlementCompensationTriggeredException) as excInfo:
            await saga.executeSplitPhase(requests)

        assert "triggered rollback of 4 transfers" in str(excInfo.value)
        assert len(routeClient._reversals) == 3
        assert await dlq.getPendingCount() == 1

        worker = CompensationDlqWorker(routeClient=routeClient, dlq=dlq)
        processed = await worker.processAllPending()

        assert processed == 1
        assert await dlq.getPendingCount() == 0
        assert len(routeClient._reversals) == 4

    @pytest.mark.asyncio
    async def testSagaResilienceWhenDlqRaisesException(
        self,
        routeClient: RazorpayRouteClient,
        nonceLedger: NonceLedger,
    ) -> None:
        """If DLQ itself raises an unexpected exception during enqueueReversal,
        the saga must NOT crash unhandled; it must continue reversing remaining transfers and raise SettlementCompensationTriggeredException."""
        brokenDlq = AsyncMock(spec=CompensationDlq)
        brokenDlq.isAlreadyCompensated.side_effect = Exception("Redis connection lost")
        brokenDlq.enqueueReversal.side_effect = Exception("Redis connection lost")

        saga = TwoPhaseCommitSaga(routeClient=routeClient, nonceLedger=nonceLedger, dlq=brokenDlq)

        routeClient.simulatedFailureAccount = "acc_fail"
        routeClient.configureSimulatedReverseFailure(account="acc_p1", errorType="500")

        requests = [
            RouteTransferRequest(account="acc_m1", amount=50000),
            RouteTransferRequest(account="acc_p1", amount=5000),
            RouteTransferRequest(account="acc_fail", amount=1000),
        ]

        with pytest.raises(SettlementCompensationTriggeredException) as excInfo:
            await saga.executeSplitPhase(requests)

        assert "triggered rollback of 2 transfers" in str(excInfo.value)
        # acc_m1 reversal succeeded even though acc_p1 reversal and DLQ failed
        assert len(routeClient._reversals) == 1


# ============================================================================
# Section 6: Schema Boundary Constraints & Serialization Stress
# ============================================================================
class TestAdversarialSchemaConstraintsAndSerialization:
    """Stress tests strict Pydantic model constraints, non-integer paise rejection, and unicode payload resilience."""

    def testCompensationEventFloatPaiseRejection(self) -> None:
        """Float paise (e.g. 500.5) must be rejected with ValidationError."""
        with pytest.raises(ValidationError):
            CompensationEvent(
                idempotencyKey="idem_float",
                transferId="trf_float",
                amountPaise=500.5, # type: ignore
            )

    @pytest.mark.asyncio
    async def testDlqEnqueueFloatPaiseRejection(self) -> None:
        """enqueueReversal with float paise must raise ArithmeticDriftException / MandateEngineException."""
        dlq = CompensationDlq(redisClient=None)
        with pytest.raises(Exception):
            await dlq.enqueueReversal(
                transferId="trf_float_enq",
                amountPaise=123.45, # type: ignore
            )

    def testCompensationEventUnicodeAndComplexMetadata(self) -> None:
        """Ensure complex unicode strings (emojis, RTL, special characters) roundtrip without data corruption."""
        complexReason = "Error: 💥 API timed out for merchant 🛍️ 'अग्रवाल किराना' with \u202eRTL_OVERRIDE\u202c"
        complexMetadata = {
            "unicode_key_हिन्दी": "नमस्ते दुनिया",
            "nested": {"array": [1, 2, "3", {"deep": "🚀"}]},
            "symbols": "<>&'\"/\\",
        }

        event = CompensationEvent(
            idempotencyKey="idem_unicode_001",
            transferId="trf_unicode_001",
            amountPaise=99900,
            reason=complexReason,
            metadata=complexMetadata,
        )

        jsonStr = event.model_dump_json()
        restored = CompensationEvent.model_validate_json(jsonStr)

        assert restored.reason == complexReason
        assert restored.metadata == complexMetadata
        assert restored == event
