"""Comprehensive Unit and Integration Test Suite for Milestone 2 Failure Recovery.

Covers:
1. CompensationEvent schema, validation, immutability, and serialization.
2. CompensationDlq queue operations, Redis backend parity, idempotency ledger, dead-letter queue.
3. CompensationDlqWorker exponential backoff, retry progression, transient recovery, persistent escalation.
4. TwoPhaseCommitSaga resilient rollback compensation with durable DLQ capture.
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
    from tests.mockInfraHelpers import MockRedisAsync


# ============================================================================
# Class 1: TestCompensationEventSchema
# ============================================================================
class TestCompensationEventSchema:
    """Tests the frozen immutable Pydantic schema CompensationEvent."""

    def testEventNominalCreation(self) -> None:
        """Test valid CompensationEvent instantiation with custom and default fields."""
        event = CompensationEvent(
            idempotencyKey="idem_test_001",
            transferId="trf_test_001",
            amountPaise=50000,
            recipientAccountId="acc_merchant_01",
            paymentId="pay_test_001",
            reason="Route API timeout",
            metadata={"source": "test"},
        )
        assert event.eventId.startswith("dlq_evt_")
        assert event.idempotencyKey == "idem_test_001"
        assert event.transferId == "trf_test_001"
        assert event.amountPaise == 50000
        assert event.recipientAccountId == "acc_merchant_01"
        assert event.paymentId == "pay_test_001"
        assert event.reason == "Route API timeout"
        assert event.retryCount == 0
        assert event.maxRetries == defaultMaxRetries
        assert event.status == CompensationEventStatus.PENDING
        assert event.createdAt > 0
        assert event.metadata == {"source": "test"}

    def testEventImmutabilityFrozen(self) -> None:
        """Attempting to mutate any field on CompensationEvent must raise ValidationError/AttributeError/TypeError."""
        event = CompensationEvent(
            idempotencyKey="idem_test_002",
            transferId="trf_test_002",
            amountPaise=10000,
        )
        with pytest.raises((ValidationError, AttributeError, TypeError)):
            event.retryCount = 1  # type: ignore

        with pytest.raises((ValidationError, AttributeError, TypeError)):
            event.status = CompensationEventStatus.COMPENSATED  # type: ignore

    def testEventPositiveAmountPaiseConstraint(self) -> None:
        """amountPaise must be strictly positive (> 0)."""
        with pytest.raises(ValidationError):
            CompensationEvent(
                idempotencyKey="idem_0",
                transferId="trf_0",
                amountPaise=0,
            )

        with pytest.raises(ValidationError):
            CompensationEvent(
                idempotencyKey="idem_neg",
                transferId="trf_neg",
                amountPaise=-500,
            )

    def testEventNonNegativeRetryConstraints(self) -> None:
        """retryCount must be >= 0 and maxRetries must be >= 1."""
        with pytest.raises(ValidationError):
            CompensationEvent(
                idempotencyKey="idem_r1",
                transferId="trf_r1",
                amountPaise=1000,
                retryCount=-1,
            )

        with pytest.raises(ValidationError):
            CompensationEvent(
                idempotencyKey="idem_r2",
                transferId="trf_r2",
                amountPaise=1000,
                maxRetries=0,
            )

    def testEventNonEmptyIdentifierConstraints(self) -> None:
        """Empty strings for eventId, idempotencyKey, transferId must raise ValidationError."""
        with pytest.raises(ValidationError):
            CompensationEvent(
                eventId="",
                idempotencyKey="idem_x",
                transferId="trf_x",
                amountPaise=1000,
            )

        with pytest.raises(ValidationError):
            CompensationEvent(
                idempotencyKey="",
                transferId="trf_x",
                amountPaise=1000,
            )

        with pytest.raises(ValidationError):
            CompensationEvent(
                idempotencyKey="idem_x",
                transferId="",
                amountPaise=1000,
            )

    def testEventExtraFieldsForbidden(self) -> None:
        """Passing extra undefined fields must raise ValidationError."""
        with pytest.raises(ValidationError):
            CompensationEvent(
                idempotencyKey="idem_extra",
                transferId="trf_extra",
                amountPaise=1000,
                extraField="unauthorized",  # type: ignore
            )

    def testEventSerializationRoundtrip(self) -> None:
        """model_dump_json() and model_validate_json() roundtrip must produce identical object."""
        original = CompensationEvent(
            idempotencyKey="idem_roundtrip",
            transferId="trf_roundtrip",
            amountPaise=75000,
            recipientAccountId="acc_roundtrip",
            paymentId="pay_roundtrip",
            reason="Test serialization roundtrip",
            retryCount=2,
            maxRetries=5,
            status=CompensationEventStatus.PROCESSING,
            metadata={"key1": "val1", "num": 42},
        )
        jsonStr = original.model_dump_json()
        restored = CompensationEvent.model_validate_json(jsonStr)
        assert restored == original
        assert restored.model_dump() == original.model_dump()


# ============================================================================
# Class 2: TestCompensationDlqQueue
# ============================================================================
class TestCompensationDlqQueue:
    """Tests Redis DLQ queue operations, idempotency deduplication, and dead-letter queue."""

    @pytest.fixture
    def fakeRedis(self) -> Any:
        return fakeredis.aioredis.FakeRedis()

    @pytest.fixture
    def mockRedis(self) -> MockRedisAsync:
        return MockRedisAsync()

    @pytest.mark.asyncio
    async def testDlqEnqueueReversalNominal(self, fakeRedis: Any) -> None:
        """Enqueueing a reversal creates a record and adds to pending queue."""
        dlq = CompensationDlq(redisClient=fakeRedis)
        event = await dlq.enqueueReversal(
            transferId="trf_dlq_001",
            amountPaise=50000,
            recipientAccountId="acc_001",
            paymentId="pay_001",
            reason="Route 500 error",
            metadata={"err": "timeout"},
        )
        assert event.transferId == "trf_dlq_001"
        assert event.amountPaise == 50000
        assert event.status == CompensationEventStatus.PENDING
        assert await dlq.getPendingCount() == 1
        assert await dlq.getDeadLetterCount() == 0

        # Retrieve record by eventId
        fetched = await dlq.getEvent(event.eventId)
        assert fetched is not None
        assert fetched.eventId == event.eventId
        assert fetched.transferId == "trf_dlq_001"

    @pytest.mark.asyncio
    async def testDlqPopPendingEventFifoOrder(self, fakeRedis: Any) -> None:
        """Pending events must pop in exact FIFO order."""
        dlq = CompensationDlq(redisClient=fakeRedis)
        e1 = await dlq.enqueueReversal(transferId="trf_a", amountPaise=1000)
        e2 = await dlq.enqueueReversal(transferId="trf_b", amountPaise=2000)
        e3 = await dlq.enqueueReversal(transferId="trf_c", amountPaise=3000)

        assert await dlq.getPendingCount() == 3

        p1 = await dlq.popPendingEvent()
        assert p1 is not None and p1.transferId == "trf_a"

        p2 = await dlq.popPendingEvent()
        assert p2 is not None and p2.transferId == "trf_b"

        p3 = await dlq.popPendingEvent()
        assert p3 is not None and p3.transferId == "trf_c"

        p4 = await dlq.popPendingEvent()
        assert p4 is None
        assert await dlq.getPendingCount() == 0

    @pytest.mark.asyncio
    async def testDlqIdempotencyLedger(self, fakeRedis: Any) -> None:
        """Verify isAlreadyCompensated and idempotency deduplication."""
        dlq = CompensationDlq(redisClient=fakeRedis)
        assert not await dlq.isAlreadyCompensated("trf_idem_1")

        # Mark compensated
        await dlq.markCompensated("trf_idem_1", reversalId="rev_123")
        assert await dlq.isAlreadyCompensated("trf_idem_1")

        # Enqueueing already compensated transfer returns COMPENSATED event without queueing
        evComp = await dlq.enqueueReversal(transferId="trf_idem_1", amountPaise=25000)
        assert evComp.status == CompensationEventStatus.COMPENSATED
        assert await dlq.getPendingCount() == 0

        # Enqueueing identical idempotency key twice returns original event without duplicating
        evNew1 = await dlq.enqueueReversal(
            transferId="trf_idem_2",
            amountPaise=10000,
            idempotencyKey="idem_custom_key",
        )
        assert await dlq.getPendingCount() == 1

        evNew2 = await dlq.enqueueReversal(
            transferId="trf_idem_2",
            amountPaise=10000,
            idempotencyKey="idem_custom_key",
        )
        assert evNew2.eventId == evNew1.eventId
        assert await dlq.getPendingCount() == 1

    @pytest.mark.asyncio
    async def testDlqDeadLetterEscalation(self, fakeRedis: Any) -> None:
        """Escalating an event pushes it to dead letter queue with DEAD_LETTER status."""
        dlq = CompensationDlq(redisClient=fakeRedis)
        event = await dlq.enqueueReversal(transferId="trf_esc_1", amountPaise=15000)
        popped = await dlq.popPendingEvent()
        assert popped is not None

        await dlq.escalateToDeadLetter(popped)
        assert await dlq.getPendingCount() == 0
        assert await dlq.getDeadLetterCount() == 1

        dlEvents = await dlq.getDeadLetterEvents()
        assert len(dlEvents) == 1
        assert dlEvents[0].eventId == event.eventId
        assert dlEvents[0].status == CompensationEventStatus.DEAD_LETTER

    @pytest.mark.asyncio
    async def testDlqBackendParityFakeRedisAndMockRedis(self, fakeRedis: Any, mockRedis: MockRedisAsync) -> None:
        """Ensure DLQ operates with 100% parity across FakeRedis, MockRedisAsync, and in-memory fallback."""
        backends = [
            CompensationDlq(redisClient=fakeRedis),
            CompensationDlq(redisClient=mockRedis),
            CompensationDlq(redisClient=None),
        ]

        for dlq in backends:
            evt = await dlq.enqueueReversal(transferId="trf_parity", amountPaise=45000)
            assert await dlq.getPendingCount() == 1
            assert not await dlq.isAlreadyCompensated("trf_parity")

            popped = await dlq.popPendingEvent()
            assert popped is not None
            assert popped.transferId == "trf_parity"
            assert await dlq.getPendingCount() == 0

            await dlq.markCompensated("trf_parity", reversalId="rev_p1")
            assert await dlq.isAlreadyCompensated("trf_parity")

            # Escalate
            await dlq.escalateToDeadLetter(popped)
            assert await dlq.getDeadLetterCount() == 1
            deadLetterItems = await dlq.getDeadLetterEvents()
            assert len(deadLetterItems) == 1
            assert deadLetterItems[0].status == CompensationEventStatus.DEAD_LETTER


# ============================================================================
# Class 3: TestCompensationDlqWorker
# ============================================================================
class TestCompensationDlqWorker:
    """Tests async worker execution, retries, backoff, and escalation."""

    @pytest.fixture
    def routeClient(self) -> RazorpayRouteClient:
        client = RazorpayRouteClient(isMockMode=True)
        return client

    @pytest.fixture
    def dlq(self) -> CompensationDlq:
        return CompensationDlq(redisClient=fakeredis.aioredis.FakeRedis())

    @pytest.mark.asyncio
    async def testWorkerProcessSingleSuccess(self, routeClient: RazorpayRouteClient, dlq: CompensationDlq) -> None:
        """Worker successfully reverses pending transfer and marks it compensated."""
        # Seed transfer in routeClient
        transferRes = await routeClient.createTransfer(
            RouteTransferRequest(account="acc_vendor_1", amount=35000)
        )
        await dlq.enqueueReversal(
            transferId=transferRes.id,
            amountPaise=35000,
            recipientAccountId="acc_vendor_1",
        )
        assert await dlq.getPendingCount() == 1

        worker = CompensationDlqWorker(routeClient=routeClient, dlq=dlq)
        resultEvent = await worker.processNext()

        assert resultEvent is not None
        assert resultEvent.status == CompensationEventStatus.COMPENSATED
        assert await dlq.isAlreadyCompensated(transferRes.id)
        assert await dlq.getPendingCount() == 0
        assert len(routeClient._reversals) == 1

    @pytest.mark.asyncio
    async def testWorkerIdempotencyDeduplication(self, routeClient: RazorpayRouteClient, dlq: CompensationDlq) -> None:
        """If transfer is already marked compensated, worker skips reversal without error."""
        transferRes = await routeClient.createTransfer(
            RouteTransferRequest(account="acc_vendor_dup", amount=20000)
        )
        # Pre-mark compensated
        await dlq.markCompensated(transferRes.id, reversalId="rev_pre_existing")

        # Manually force-enqueue an event
        event = CompensationEvent(
            idempotencyKey=f"cmp_{transferRes.id}",
            transferId=transferRes.id,
            amountPaise=20000,
        )
        await dlq.requeueEvent(event)

        worker = CompensationDlqWorker(routeClient=routeClient, dlq=dlq)
        resultEvent = await worker.processNext()

        assert resultEvent is not None
        assert resultEvent.status == CompensationEventStatus.COMPENSATED
        # No new reversal created in routeClient
        assert len(routeClient._reversals) == 0

    def testWorkerExponentialBackoffCalculation(self, routeClient: RazorpayRouteClient, dlq: CompensationDlq) -> None:
        """Verify exponential backoff calculation: initial * (multiplier ** (retryCount - 1))."""
        worker = CompensationDlqWorker(
            routeClient=routeClient,
            dlq=dlq,
            initialBackoffSeconds=0.5,
            backoffMultiplier=2.0,
            maxBackoffSeconds=30.0,
        )
        assert worker.computeBackoffDelay(0) == 0.0
        assert worker.computeBackoffDelay(1) == 0.5
        assert worker.computeBackoffDelay(2) == 1.0
        assert worker.computeBackoffDelay(3) == 2.0
        assert worker.computeBackoffDelay(4) == 4.0
        assert worker.computeBackoffDelay(5) == 8.0
        assert worker.computeBackoffDelay(6) == 16.0
        assert worker.computeBackoffDelay(7) == 30.0  # Clamped to maxBackoffSeconds
        assert worker.computeBackoffDelay(10) == 30.0

    @pytest.mark.asyncio
    async def testWorkerTransientFailureRecovery(self, routeClient: RazorpayRouteClient, dlq: CompensationDlq) -> None:
        """Simulate transient failure: 1 failure then success. Worker retries and succeeds."""
        transferRes = await routeClient.createTransfer(
            RouteTransferRequest(account="acc_vendor_transient", amount=12000)
        )
        routeClient.configureSimulatedReverseFailure(
            transferId=transferRes.id,
            errorType="timeout",
            failureCount=1,  # 1 failure, then next attempt succeeds
        )

        await dlq.enqueueReversal(
            transferId=transferRes.id,
            amountPaise=12000,
            maxRetries=3,
        )

        sleepSpy = AsyncMock()
        worker = CompensationDlqWorker(
            routeClient=routeClient,
            dlq=dlq,
            initialBackoffSeconds=0.1,
            sleepFunc=sleepSpy,
        )

        # 1st processing attempt -> fails, sleeps with backoff, requeues
        ev1 = await worker.processNext()
        assert ev1 is not None
        assert ev1.retryCount == 1
        assert ev1.status == CompensationEventStatus.PENDING
        assert "Retry 1/3" in ev1.reason
        assert sleepSpy.await_count == 1
        assert await dlq.getPendingCount() == 1

        # 2nd processing attempt -> succeeds
        ev2 = await worker.processNext()
        assert ev2 is not None
        assert ev2.status == CompensationEventStatus.COMPENSATED
        assert await dlq.isAlreadyCompensated(transferRes.id)
        assert await dlq.getPendingCount() == 0
        assert len(routeClient._reversals) == 1

    @pytest.mark.asyncio
    async def testWorkerPersistentFailureEscalation(self, routeClient: RazorpayRouteClient, dlq: CompensationDlq) -> None:
        """Simulate persistent failure: exceeds maxRetries and escalates to DEAD_LETTER."""
        transferRes = await routeClient.createTransfer(
            RouteTransferRequest(account="acc_vendor_persist", amount=18000)
        )
        routeClient.configureSimulatedReverseFailure(
            transferId=transferRes.id,
            errorType="500",
            failureCount=None,  # Always fail
        )

        await dlq.enqueueReversal(
            transferId=transferRes.id,
            amountPaise=18000,
            maxRetries=3,
        )

        sleepSpy = AsyncMock()
        worker = CompensationDlqWorker(
            routeClient=routeClient,
            dlq=dlq,
            initialBackoffSeconds=0.1,
            sleepFunc=sleepSpy,
        )

        # Attempt 1: retryCount becomes 1
        ev1 = await worker.processNext()
        assert ev1 is not None and ev1.retryCount == 1 and ev1.status == CompensationEventStatus.PENDING

        # Attempt 2: retryCount becomes 2
        ev2 = await worker.processNext()
        assert ev2 is not None and ev2.retryCount == 2 and ev2.status == CompensationEventStatus.PENDING

        # Attempt 3: retryCount becomes 3 -> maxRetries reached -> DEAD_LETTER
        ev3 = await worker.processNext()
        assert ev3 is not None
        assert ev3.retryCount == 3
        assert ev3.status == CompensationEventStatus.DEAD_LETTER
        assert "Max retries (3) exceeded" in ev3.reason

        assert await dlq.getPendingCount() == 0
        assert await dlq.getDeadLetterCount() == 1

    @pytest.mark.asyncio
    async def testWorkerProcessAllPendingBatch(self, routeClient: RazorpayRouteClient, dlq: CompensationDlq) -> None:
        """processAllPending processes all queued items until pending queue is empty."""
        for i in range(5):
            t = await routeClient.createTransfer(RouteTransferRequest(account=f"acc_batch_{i}", amount=1000 * (i + 1)))
            await dlq.enqueueReversal(transferId=t.id, amountPaise=t.amount)

        assert await dlq.getPendingCount() == 5

        worker = CompensationDlqWorker(routeClient=routeClient, dlq=dlq)
        processedCount = await worker.processAllPending()

        assert processedCount == 5
        assert await dlq.getPendingCount() == 0
        assert len(routeClient._reversals) == 5

    @pytest.mark.asyncio
    async def testWorkerRunLoopLifecycleAndGracefulShutdown(self, routeClient: RazorpayRouteClient, dlq: CompensationDlq) -> None:
        """runWorkerLoop starts background processing and exits cleanly on stopEvent."""
        stopEvent = asyncio.Event()
        worker = CompensationDlqWorker(
            routeClient=routeClient,
            dlq=dlq,
            initialBackoffSeconds=0.001,
        )

        loopTask = asyncio.create_task(
            worker.runWorkerLoop(pollIntervalSeconds=0.01, stopEvent=stopEvent)
        )

        t = await routeClient.createTransfer(RouteTransferRequest(account="acc_loop", amount=9999))
        await dlq.enqueueReversal(transferId=t.id, amountPaise=t.amount)

        # Allow worker loop to pick up item
        await asyncio.sleep(0.05)
        assert await dlq.isAlreadyCompensated(t.id)

        # Stop worker
        stopEvent.set()
        await asyncio.wait_for(loopTask, timeout=1.0)
        assert loopTask.done()


# ============================================================================
# Class 4: TestTwoPhaseCommitSagaDlqIntegration
# ============================================================================
class TestTwoPhaseCommitSagaDlqIntegration:
    """Tests 2PC Saga integration with failure simulation and durable DLQ capture."""

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
    async def testSagaNominalRollbackWithoutDlqPush(
        self,
        routeClient: RazorpayRouteClient,
        nonceLedger: NonceLedger,
        dlq: CompensationDlq,
    ) -> None:
        """When 2PC rollback succeeds cleanly, DLQ pending queue remains empty and all transfers reversed."""
        saga = TwoPhaseCommitSaga(routeClient=routeClient, nonceLedger=nonceLedger, dlq=dlq)

        # Set failure on 3rd transfer
        routeClient.simulatedFailureAccount = "acc_logistics"

        requests = [
            RouteTransferRequest(account="acc_merchant", amount=380000, notes={"paymentId": "pay_100"}),
            RouteTransferRequest(account="acc_protocol", amount=2000, notes={"paymentId": "pay_100"}),
            RouteTransferRequest(account="acc_logistics", amount=38000, notes={"paymentId": "pay_100"}),
        ]

        with pytest.raises(SettlementCompensationTriggeredException) as excInfo:
            await saga.executeSplitPhase(requests)

        assert "triggered rollback of 2 transfers" in str(excInfo.value)
        # Reversals executed successfully in LIFO order
        assert len(routeClient._reversals) == 2
        # DLQ has 0 pending events
        assert await dlq.getPendingCount() == 0

    @pytest.mark.asyncio
    async def testSagaReversalFailureEnqueuesToDlqAndContinues(
        self,
        routeClient: RazorpayRouteClient,
        nonceLedger: NonceLedger,
        dlq: CompensationDlq,
    ) -> None:
        """When a reversal fails during rollback, saga captures it in DLQ and continues reversing remaining transfers."""
        saga = TwoPhaseCommitSaga(routeClient=routeClient, nonceLedger=nonceLedger, dlq=dlq)

        # Fail creation on logistics
        routeClient.simulatedFailureAccount = "acc_logistics"
        # Fail reversal on protocol transfer
        routeClient.configureSimulatedReverseFailure(
            account="acc_protocol",
            errorType="500",
        )

        requests = [
            RouteTransferRequest(account="acc_merchant", amount=380000, notes={"paymentId": "pay_200"}),
            RouteTransferRequest(account="acc_protocol", amount=2000, notes={"paymentId": "pay_200"}),
            RouteTransferRequest(account="acc_logistics", amount=38000, notes={"paymentId": "pay_200"}),
        ]

        with pytest.raises(SettlementCompensationTriggeredException) as excInfo:
            await saga.executeSplitPhase(requests)

        assert "triggered rollback of 2 transfers" in str(excInfo.value)

        # 1 reversal succeeded (merchant)
        assert len(routeClient._reversals) == 1
        # 1 reversal failed and was captured in DLQ (protocol)
        assert await dlq.getPendingCount() == 1

        failedEvent = await dlq.popPendingEvent()
        assert failedEvent is not None
        assert failedEvent.recipientAccountId == "acc_protocol"
        assert failedEvent.amountPaise == 2000
        assert failedEvent.paymentId == "pay_200"
        assert "2PC reversal failure" in failedEvent.reason

    @pytest.mark.asyncio
    async def testSagaAllReversalsFailAndCapture(
        self,
        routeClient: RazorpayRouteClient,
        nonceLedger: NonceLedger,
        dlq: CompensationDlq,
    ) -> None:
        """When all reversals fail during rollback, saga captures both in DLQ without aborting."""
        saga = TwoPhaseCommitSaga(routeClient=routeClient, nonceLedger=nonceLedger, dlq=dlq)

        routeClient.simulatedFailureAccount = "acc_logistics"
        # Fail all reversals
        routeClient.configureSimulatedReverseFailure(
            errorType="timeout",
            failureCount=None,
        )

        requests = [
            RouteTransferRequest(account="acc_merchant", amount=380000, notes={"paymentId": "pay_300"}),
            RouteTransferRequest(account="acc_protocol", amount=2000, notes={"paymentId": "pay_300"}),
            RouteTransferRequest(account="acc_logistics", amount=38000, notes={"paymentId": "pay_300"}),
        ]

        with pytest.raises(SettlementCompensationTriggeredException):
            await saga.executeSplitPhase(requests)

        assert len(routeClient._reversals) == 0
        assert await dlq.getPendingCount() == 2

    @pytest.mark.asyncio
    async def testSagaDlqWorkerEndToEndEventualCompensation(
        self,
        routeClient: RazorpayRouteClient,
        nonceLedger: NonceLedger,
        dlq: CompensationDlq,
    ) -> None:
        """End-to-end flow: Saga failure captures to DLQ -> Worker recovers and completes 100% reversals."""
        saga = TwoPhaseCommitSaga(routeClient=routeClient, nonceLedger=nonceLedger, dlq=dlq)

        routeClient.simulatedFailureAccount = "acc_logistics"
        routeClient.configureSimulatedReverseFailure(
            account="acc_protocol",
            errorType="500",
            failureCount=1,  # Fails during saga, then route service recovers
        )

        requests = [
            RouteTransferRequest(account="acc_merchant", amount=380000, notes={"paymentId": "pay_e2e"}),
            RouteTransferRequest(account="acc_protocol", amount=2000, notes={"paymentId": "pay_e2e"}),
            RouteTransferRequest(account="acc_logistics", amount=38000, notes={"paymentId": "pay_e2e"}),
        ]

        with pytest.raises(SettlementCompensationTriggeredException):
            await saga.executeSplitPhase(requests)

        assert len(routeClient._reversals) == 1
        assert await dlq.getPendingCount() == 1

        # Now run DLQ Worker (simulated failure count was 1, so RouteClient is now healthy)
        worker = CompensationDlqWorker(routeClient=routeClient, dlq=dlq)
        processed = await worker.processAllPending()

        assert processed == 1
        assert await dlq.getPendingCount() == 0
        # Both transfers are now reversed!
        assert len(routeClient._reversals) == 2
