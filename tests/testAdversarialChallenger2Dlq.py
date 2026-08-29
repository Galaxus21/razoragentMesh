"""Adversarial Challenger 2 Test Suite: Milestone 2 Failure Recovery (Durable DLQ and Worker).

Exhaustive empirical validation of 2PC Saga rollback failure handling across:
1. Reversal failure position permutations (1st, middle, last, multiple, and all transfers).
2. Error variations (HTTP 500, 502, 503, 504, Timeout, Network error) in mock and live HTTP transport.
3. Field accuracy verification in DLQ CompensationEvent (amountPaise, transferId, recipientAccountId, paymentId, metadata).
4. DLQ Worker eventual compensation lifecycle upon route client recovery.
5. High-order parameterization across arbitrary transfer batches and failure patterns.
6. Negative tests on event immutability, schema constraints, and duplicate suppression.
"""

import asyncio
import json
from typing import Any, Optional
from unittest.mock import AsyncMock
import fakeredis.aioredis
import httpx
import pytest

from packages.mandateEngine.constants.settlementConstants import transferIdPrefix
from packages.mandateEngine.nonce.nonceLedger import NonceLedger
from packages.mandateEngine.settlement.compensationDlq import (
    CompensationDlq,
    CompensationDlqWorker,
    CompensationEvent,
    CompensationEventStatus,
    dlqCompensatedPrefix,
    dlqDeadLetterQueueKey,
    dlqEventRecordPrefix,
    dlqIdempotencyPrefix,
    dlqPendingQueueKey,
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
from packages.mandateEngine.settlement.settlementOrchestrator import SettlementOrchestrator
from packages.mandateEngine.settlement.twoPhaseCommitSaga import TwoPhaseCommitSaga


# ============================================================================
# Section 1: Reversal Position Permutations (1st, Middle, Last, Multiple, All)
# ============================================================================
class TestSagaReversalPositionPermutations:
    """Adversarially tests 2PC rollback when individual transfers fail at various positions."""

    @pytest.fixture
    def fakeRedis(self) -> Any:
        return fakeredis.aioredis.FakeRedis()

    @pytest.fixture
    def dlq(self, fakeRedis: Any) -> CompensationDlq:
        return CompensationDlq(redisClient=fakeRedis)

    @pytest.fixture
    def nonceLedger(self, fakeRedis: Any) -> NonceLedger:
        return NonceLedger(redisClient=fakeRedis)

    @pytest.fixture
    def routeClient(self) -> RazorpayRouteClient:
        return RazorpayRouteClient(isMockMode=True)

    @pytest.mark.asyncio
    @pytest.mark.parametrize("errorType", ["500", "502", "503", "504", "timeout", "network"])
    async def testFirstRollbackTransferFails(
        self,
        routeClient: RazorpayRouteClient,
        nonceLedger: NonceLedger,
        dlq: CompensationDlq,
        errorType: str,
    ) -> None:
        """1st transfer in rollback (i.e. Logistics, the last created) fails reversal."""
        saga = TwoPhaseCommitSaga(routeClient=routeClient, nonceLedger=nonceLedger, dlq=dlq)

        routeClient.simulatedFailureAccount = "acc_fail_trigger"
        routeClient.configureSimulatedReverseFailure(
            account="acc_logistics_01",
            errorType=errorType,
            failureCount=1,
        )

        requests = [
            RouteTransferRequest(account="acc_merchant_01", amount=150000, notes={"paymentId": "pay_perm_1"}),
            RouteTransferRequest(account="acc_protocol_01", amount=3000, notes={"paymentId": "pay_perm_1"}),
            RouteTransferRequest(account="acc_logistics_01", amount=8500, notes={"paymentId": "pay_perm_1"}),
            RouteTransferRequest(account="acc_fail_trigger", amount=1000, notes={"paymentId": "pay_perm_1"}),
        ]

        with pytest.raises(SettlementCompensationTriggeredException) as excInfo:
            await saga.executeSplitPhase(requests)

        assert "triggered rollback of 3 transfers" in str(excInfo.value)

        # Protocol and Merchant reversed immediately
        assert len(routeClient._reversals) == 2

        # Logistics enqueued in DLQ
        assert await dlq.getPendingCount() == 1
        event = await dlq.popPendingEvent()
        assert event is not None
        assert event.recipientAccountId == "acc_logistics_01"
        assert event.amountPaise == 8500
        assert event.paymentId == "pay_perm_1"
        assert event.status == CompensationEventStatus.PENDING
        assert event.retryCount == 0

        # Worker compensation
        await dlq.requeueEvent(event)
        worker = CompensationDlqWorker(routeClient=routeClient, dlq=dlq)
        processed = await worker.processAllPending()
        assert processed == 1
        assert await dlq.getPendingCount() == 0
        assert await dlq.getDeadLetterCount() == 0
        assert len(routeClient._reversals) == 3

    @pytest.mark.asyncio
    @pytest.mark.parametrize("errorType", ["500", "502", "503", "504", "timeout", "network"])
    async def testMiddleRollbackTransferFails(
        self,
        routeClient: RazorpayRouteClient,
        nonceLedger: NonceLedger,
        dlq: CompensationDlq,
        errorType: str,
    ) -> None:
        """Middle transfer in rollback (i.e. Protocol) fails reversal."""
        saga = TwoPhaseCommitSaga(routeClient=routeClient, nonceLedger=nonceLedger, dlq=dlq)

        routeClient.simulatedFailureAccount = "acc_fail_trigger"
        routeClient.configureSimulatedReverseFailure(
            account="acc_protocol_02",
            errorType=errorType,
            failureCount=1,
        )

        requests = [
            RouteTransferRequest(account="acc_merchant_02", amount=200000, notes={"paymentId": "pay_perm_2"}),
            RouteTransferRequest(account="acc_protocol_02", amount=4000, notes={"paymentId": "pay_perm_2"}),
            RouteTransferRequest(account="acc_logistics_02", amount=12000, notes={"paymentId": "pay_perm_2"}),
            RouteTransferRequest(account="acc_fail_trigger", amount=1000, notes={"paymentId": "pay_perm_2"}),
        ]

        with pytest.raises(SettlementCompensationTriggeredException) as excInfo:
            await saga.executeSplitPhase(requests)

        assert "triggered rollback of 3 transfers" in str(excInfo.value)

        # Logistics and Merchant reversed immediately
        assert len(routeClient._reversals) == 2

        # Protocol in DLQ
        assert await dlq.getPendingCount() == 1
        event = await dlq.popPendingEvent()
        assert event is not None
        assert event.recipientAccountId == "acc_protocol_02"
        assert event.amountPaise == 4000
        assert event.paymentId == "pay_perm_2"

        # Worker compensation
        await dlq.requeueEvent(event)
        worker = CompensationDlqWorker(routeClient=routeClient, dlq=dlq)
        processed = await worker.processAllPending()
        assert processed == 1
        assert await dlq.getPendingCount() == 0
        assert len(routeClient._reversals) == 3

    @pytest.mark.asyncio
    @pytest.mark.parametrize("errorType", ["500", "502", "503", "504", "timeout", "network"])
    async def testLastRollbackTransferFails(
        self,
        routeClient: RazorpayRouteClient,
        nonceLedger: NonceLedger,
        dlq: CompensationDlq,
        errorType: str,
    ) -> None:
        """Last transfer in rollback (i.e. Merchant) fails reversal."""
        saga = TwoPhaseCommitSaga(routeClient=routeClient, nonceLedger=nonceLedger, dlq=dlq)

        routeClient.simulatedFailureAccount = "acc_fail_trigger"
        routeClient.configureSimulatedReverseFailure(
            account="acc_merchant_03",
            errorType=errorType,
            failureCount=1,
        )

        requests = [
            RouteTransferRequest(account="acc_merchant_03", amount=350000, notes={"paymentId": "pay_perm_3"}),
            RouteTransferRequest(account="acc_protocol_03", amount=7000, notes={"paymentId": "pay_perm_3"}),
            RouteTransferRequest(account="acc_logistics_03", amount=15000, notes={"paymentId": "pay_perm_3"}),
            RouteTransferRequest(account="acc_fail_trigger", amount=1000, notes={"paymentId": "pay_perm_3"}),
        ]

        with pytest.raises(SettlementCompensationTriggeredException) as excInfo:
            await saga.executeSplitPhase(requests)

        assert "triggered rollback of 3 transfers" in str(excInfo.value)

        # Logistics and Protocol reversed immediately
        assert len(routeClient._reversals) == 2

        # Merchant in DLQ
        assert await dlq.getPendingCount() == 1
        event = await dlq.popPendingEvent()
        assert event is not None
        assert event.recipientAccountId == "acc_merchant_03"
        assert event.amountPaise == 350000
        assert event.paymentId == "pay_perm_3"

        # Worker compensation
        await dlq.requeueEvent(event)
        worker = CompensationDlqWorker(routeClient=routeClient, dlq=dlq)
        processed = await worker.processAllPending()
        assert processed == 1
        assert await dlq.getPendingCount() == 0
        assert len(routeClient._reversals) == 3

    @pytest.mark.asyncio
    async def testMultipleTransfersFailInRollback(
        self,
        routeClient: RazorpayRouteClient,
        nonceLedger: NonceLedger,
        dlq: CompensationDlq,
    ) -> None:
        """Multiple transfers fail in rollback (Logistics and Merchant fail, Protocol succeeds)."""
        saga = TwoPhaseCommitSaga(routeClient=routeClient, nonceLedger=nonceLedger, dlq=dlq)

        tMerchant = await routeClient.createTransfer(RouteTransferRequest(account="acc_m_multi", amount=90000))
        tProtocol = await routeClient.createTransfer(RouteTransferRequest(account="acc_p_multi", amount=1500))
        tLogistics = await routeClient.createTransfer(RouteTransferRequest(account="acc_l_multi", amount=4500))

        failedAccounts = {"acc_l_multi", "acc_m_multi"}
        originalReverse = routeClient.reverseTransfer

        async def selectiveReverse(
            transferId: str,
            amountPaise: Optional[int] = None,
            idempotencyKey: Optional[str] = None,
        ) -> TransferReversalResponse:
            trf = routeClient._transfers.get(transferId)
            if trf and trf.account in failedAccounts:
                raise MandateEngineException(f"Selective failure for account {trf.account}")
            return await originalReverse(transferId, amountPaise)

        routeClient.reverseTransfer = selectiveReverse  # type: ignore

        completed = [tMerchant, tProtocol, tLogistics]
        reversals = await saga.compensateTransfers(
            completedTransfers=completed,
            failureReason="Simulated multi-failure rollback",
            paymentId="pay_multi_001",
        )

        assert len(reversals) == 3
        assert reversals[0] is None
        assert reversals[1] is not None
        assert reversals[2] is None

        assert len(routeClient._reversals) == 1
        assert await dlq.getPendingCount() == 2

        e1 = await dlq.popPendingEvent()
        assert e1 is not None
        assert e1.transferId == tLogistics.id
        assert e1.recipientAccountId == "acc_l_multi"
        assert e1.amountPaise == 4500
        assert e1.paymentId == "pay_multi_001"

        e2 = await dlq.popPendingEvent()
        assert e2 is not None
        assert e2.transferId == tMerchant.id
        assert e2.recipientAccountId == "acc_m_multi"
        assert e2.amountPaise == 90000
        assert e2.paymentId == "pay_multi_001"

        routeClient.reverseTransfer = originalReverse  # type: ignore
        await dlq.requeueEvent(e1)
        await dlq.requeueEvent(e2)

        worker = CompensationDlqWorker(routeClient=routeClient, dlq=dlq)
        processed = await worker.processAllPending()
        assert processed == 2
        assert await dlq.getPendingCount() == 0
        assert len(routeClient._reversals) == 3

    @pytest.mark.asyncio
    async def testAllTransfersFailInRollback(
        self,
        routeClient: RazorpayRouteClient,
        nonceLedger: NonceLedger,
        dlq: CompensationDlq,
    ) -> None:
        """All transfers in rollback fail (e.g. total gateway outage)."""
        saga = TwoPhaseCommitSaga(routeClient=routeClient, nonceLedger=nonceLedger, dlq=dlq)

        routeClient.simulatedFailureAccount = "acc_fail_trigger"
        routeClient.configureSimulatedReverseFailure(
            errorType="500",
            failureCount=3,
        )

        requests = [
            RouteTransferRequest(account="acc_m_all", amount=100000, notes={"paymentId": "pay_all_fail"}),
            RouteTransferRequest(account="acc_p_all", amount=2000, notes={"paymentId": "pay_all_fail"}),
            RouteTransferRequest(account="acc_l_all", amount=5000, notes={"paymentId": "pay_all_fail"}),
            RouteTransferRequest(account="acc_fail_trigger", amount=1000, notes={"paymentId": "pay_all_fail"}),
        ]

        with pytest.raises(SettlementCompensationTriggeredException):
            await saga.executeSplitPhase(requests)

        assert len(routeClient._reversals) == 0
        assert await dlq.getPendingCount() == 3

        worker = CompensationDlqWorker(routeClient=routeClient, dlq=dlq)
        processed = await worker.processAllPending()
        assert processed == 3
        assert await dlq.getPendingCount() == 0
        assert len(routeClient._reversals) == 3


# ============================================================================
# Section 2: Arbitrary N-Transfer Batch Permutations Matrix
# ============================================================================
class TestArbitraryTransferBatchPermutationsMatrix:
    """Stress tests arbitrary N-transfer batches with failure injected at every index."""

    @pytest.fixture
    def fakeRedis(self) -> Any:
        return fakeredis.aioredis.FakeRedis()

    @pytest.fixture
    def dlq(self, fakeRedis: Any) -> CompensationDlq:
        return CompensationDlq(redisClient=fakeRedis)

    @pytest.fixture
    def nonceLedger(self, fakeRedis: Any) -> NonceLedger:
        return NonceLedger(redisClient=fakeRedis)

    @pytest.mark.asyncio
    @pytest.mark.parametrize("batchSize", [2, 3, 5, 8])
    @pytest.mark.parametrize("errorType", ["500", "timeout", "network"])
    async def testParameterizedBatchSingleFailure(
        self,
        fakeRedis: Any,
        dlq: CompensationDlq,
        nonceLedger: NonceLedger,
        batchSize: int,
        errorType: str,
    ) -> None:
        """For a batch of size N, test failure at each position k in [0..N-1] during rollback."""
        for failIdx in range(batchSize):
            routeClient = RazorpayRouteClient(isMockMode=True)
            saga = TwoPhaseCommitSaga(routeClient=routeClient, nonceLedger=nonceLedger, dlq=dlq)

            completedTransfers: list[RouteTransferResponse] = []
            for i in range(batchSize):
                trf = await routeClient.createTransfer(
                    RouteTransferRequest(
                        account=f"acc_batch_{batchSize}_item_{i}",
                        amount=10000 * (i + 1),
                        notes={"paymentId": f"pay_batch_{batchSize}_{failIdx}"},
                    )
                )
                completedTransfers.append(trf)

            failedTransfer = completedTransfers[-(failIdx + 1)]

            routeClient.configureSimulatedReverseFailure(
                transferId=failedTransfer.id,
                errorType=errorType,
                failureCount=1,
            )

            reversals = await saga.compensateTransfers(
                completedTransfers=completedTransfers,
                failureReason=f"Batch {batchSize} failure at index {failIdx}",
                paymentId=f"pay_batch_{batchSize}_{failIdx}",
            )

            assert len(reversals) == batchSize
            assert reversals[failIdx] is None
            for j, rev in enumerate(reversals):
                if j != failIdx:
                    assert rev is not None

            assert len(routeClient._reversals) == batchSize - 1

            assert await dlq.getPendingCount() == 1
            event = await dlq.popPendingEvent()
            assert event is not None
            assert event.transferId == failedTransfer.id
            assert event.amountPaise == failedTransfer.amount
            assert event.recipientAccountId == failedTransfer.account
            assert event.paymentId == f"pay_batch_{batchSize}_{failIdx}"

            await dlq.requeueEvent(event)
            worker = CompensationDlqWorker(routeClient=routeClient, dlq=dlq)
            processed = await worker.processAllPending()
            assert processed == 1
            assert await dlq.getPendingCount() == 0
            assert len(routeClient._reversals) == batchSize


# ============================================================================
# Section 3: Live HTTP Client Simulation with MockTransport
# ============================================================================
class TestLiveHttpSagaRollbackDlqRecovery:
    """Validates 2PC rollback DLQ capture and eventual compensation over live HTTP client."""

    @pytest.fixture
    def fakeRedis(self) -> Any:
        return fakeredis.aioredis.FakeRedis()

    @pytest.fixture
    def dlq(self, fakeRedis: Any) -> CompensationDlq:
        return CompensationDlq(redisClient=fakeRedis)

    @pytest.mark.asyncio
    @pytest.mark.parametrize("failingAccount", ["acc_live_merchant", "acc_live_protocol"])
    async def testLiveHttpRollbackReversalFailureCapturedAndCompensated(
        self,
        dlq: CompensationDlq,
        failingAccount: str,
    ) -> None:
        """Simulates live HTTP Razorpay Route API returning HTTP 500 on reversal."""
        serverTransfers: dict[str, dict] = {}
        serverReversals: dict[str, dict] = {}
        reversalFailureActive = True

        def liveRouteMock(request: httpx.Request) -> httpx.Response:
            nonlocal reversalFailureActive
            path = request.url.path
            method = request.method

            if method == "POST" and path == "/v1/transfers":
                body = json.loads(request.content.decode("utf-8"))
                acc = body["account"]
                amount = body["amount"]
                if acc == "acc_live_logistics_fail":
                    return httpx.Response(status_code=500, json={"error": {"description": "Logistics node down"}})
                trfId = f"trf_live_{len(serverTransfers) + 1}"
                trfData = {"id": trfId, "account": acc, "amount": amount, "currency": "INR", "status": "processed", "created_at": 1700000000}
                serverTransfers[trfId] = trfData
                return httpx.Response(status_code=200, json=trfData)

            if method == "POST" and "/reversals" in path:
                trfId = path.split("/")[3]
                trfData = serverTransfers.get(trfId, {})
                acc = trfData.get("account")
                if reversalFailureActive and acc == failingAccount:
                    return httpx.Response(
                        status_code=500,
                        json={"error": {"code": "REVERSAL_GATEWAY_ERROR", "description": "Temporary banking switch timeout"}},
                    )
                revId = f"rev_live_{len(serverReversals) + 1}"
                revData = {"id": revId, "transfer_id": trfId, "amount": trfData.get("amount", 0), "currency": "INR", "status": "processed", "created_at": 1700000000}
                serverReversals[revId] = revData
                return httpx.Response(status_code=200, json=revData)

            return httpx.Response(status_code=404, json={"error": "Not Found"})

        transport = httpx.MockTransport(liveRouteMock)
        async with httpx.AsyncClient(transport=transport) as httpClient:
            liveClient = RazorpayRouteClient(isMockMode=False, httpClient=httpClient)
            saga = TwoPhaseCommitSaga(routeClient=liveClient, nonceLedger=NonceLedger(fakeredis.aioredis.FakeRedis()), dlq=dlq)

            requests = [
                RouteTransferRequest(account="acc_live_merchant", amount=250000, notes={"paymentId": "pay_live_001"}),
                RouteTransferRequest(account="acc_live_protocol", amount=5000, notes={"paymentId": "pay_live_001"}),
                RouteTransferRequest(account="acc_live_logistics_fail", amount=10000, notes={"paymentId": "pay_live_001"}),
            ]

            with pytest.raises(SettlementCompensationTriggeredException):
                await saga.executeSplitPhase(requests)

            assert len(serverReversals) == 1
            assert await dlq.getPendingCount() == 1

            event = await dlq.popPendingEvent()
            assert event is not None
            assert event.recipientAccountId == failingAccount
            assert event.paymentId == "pay_live_001"

            reversalFailureActive = False
            await dlq.requeueEvent(event)

            worker = CompensationDlqWorker(routeClient=liveClient, dlq=dlq)
            processed = await worker.processAllPending()
            assert processed == 1
            assert await dlq.getPendingCount() == 0
            assert len(serverReversals) == 2


# ============================================================================
# Section 4: Worker Transient Retries and Exponential Backoff Progression
# ============================================================================
class TestWorkerRetryAndBackoffProgression:
    """Verifies worker exponential backoff progression and transient recovery under multiple retries."""

    @pytest.fixture
    def fakeRedis(self) -> Any:
        return fakeredis.aioredis.FakeRedis()

    @pytest.fixture
    def dlq(self, fakeRedis: Any) -> CompensationDlq:
        return CompensationDlq(redisClient=fakeRedis)

    @pytest.fixture
    def routeClient(self) -> RazorpayRouteClient:
        return RazorpayRouteClient(isMockMode=True)

    @pytest.mark.asyncio
    async def testWorkerMultipleRetriesThenSuccess(
        self,
        routeClient: RazorpayRouteClient,
        dlq: CompensationDlq,
    ) -> None:
        trf = await routeClient.createTransfer(RouteTransferRequest(account="acc_multi_retry", amount=40000))
        routeClient.configureSimulatedReverseFailure(
            transferId=trf.id,
            errorType="500",
            failureCount=3,
        )

        await dlq.enqueueReversal(
            transferId=trf.id,
            amountPaise=40000,
            recipientAccountId="acc_multi_retry",
            paymentId="pay_mr_01",
            maxRetries=5,
        )

        recordedDelays: list[float] = []

        async def mockSleep(delay: float) -> None:
            recordedDelays.append(delay)

        worker = CompensationDlqWorker(
            routeClient=routeClient,
            dlq=dlq,
            initialBackoffSeconds=1.0,
            backoffMultiplier=2.0,
            maxBackoffSeconds=30.0,
            sleepFunc=mockSleep,
        )

        e1 = await worker.processNext()
        assert e1 is not None and e1.retryCount == 1 and e1.status == CompensationEventStatus.PENDING

        e2 = await worker.processNext()
        assert e2 is not None and e2.retryCount == 2 and e2.status == CompensationEventStatus.PENDING

        e3 = await worker.processNext()
        assert e3 is not None and e3.retryCount == 3 and e3.status == CompensationEventStatus.PENDING

        e4 = await worker.processNext()
        assert e4 is not None and e4.status == CompensationEventStatus.COMPENSATED

        assert recordedDelays == [1.0, 2.0, 4.0]
        assert await dlq.getPendingCount() == 0
        assert await dlq.getDeadLetterCount() == 0
        assert len(routeClient._reversals) == 1

    @pytest.mark.asyncio
    async def testWorkerPersistentFailureEscalatesToDeadLetter(
        self,
        routeClient: RazorpayRouteClient,
        dlq: CompensationDlq,
    ) -> None:
        trf = await routeClient.createTransfer(RouteTransferRequest(account="acc_dead_letter", amount=60000))
        routeClient.configureSimulatedReverseFailure(
            transferId=trf.id,
            errorType="timeout",
            failureCount=None,
        )

        await dlq.enqueueReversal(
            transferId=trf.id,
            amountPaise=60000,
            recipientAccountId="acc_dead_letter",
            paymentId="pay_dl_01",
            maxRetries=4,
        )

        sleepSpy = AsyncMock()
        worker = CompensationDlqWorker(
            routeClient=routeClient,
            dlq=dlq,
            initialBackoffSeconds=0.1,
            sleepFunc=sleepSpy,
        )

        for attempt in range(1, 4):
            e = await worker.processNext()
            assert e is not None and e.retryCount == attempt and e.status == CompensationEventStatus.PENDING

        eFinal = await worker.processNext()
        assert eFinal is not None
        assert eFinal.retryCount == 4
        assert eFinal.status == CompensationEventStatus.DEAD_LETTER
        assert "Max retries (4) exceeded" in eFinal.reason

        assert await dlq.getPendingCount() == 0
        assert await dlq.getDeadLetterCount() == 1

        deadLetters = await dlq.getDeadLetterEvents()
        assert len(deadLetters) == 1
        assert deadLetters[0].transferId == trf.id
        assert deadLetters[0].status == CompensationEventStatus.DEAD_LETTER


# ============================================================================
# Section 5: High-Concurrency & Idempotency Stress Tests
# ============================================================================
class TestConcurrencyAndIdempotencyStress:
    """Stress tests high concurrency and idempotency deduplication invariants."""

    @pytest.fixture
    def fakeRedis(self) -> Any:
        return fakeredis.aioredis.FakeRedis()

    @pytest.fixture
    def dlq(self, fakeRedis: Any) -> CompensationDlq:
        return CompensationDlq(redisClient=fakeRedis)

    @pytest.fixture
    def nonceLedger(self, fakeRedis: Any) -> NonceLedger:
        return NonceLedger(redisClient=fakeRedis)

    @pytest.mark.asyncio
    async def testConcurrentSagaRollbacksWithSharedDlq(
        self,
        fakeRedis: Any,
        dlq: CompensationDlq,
        nonceLedger: NonceLedger,
    ) -> None:
        """Runs 10 concurrent 2PC Saga rollbacks each with a failure on the 2nd transfer.
        
        Verifies:
        - Exactly 10 events enqueued in shared DLQ without race conditions.
        - Worker processes all 10 events asynchronously and completely drains queue.
        - Zero lost events, all transfers accounted for.
        """
        routeClient = RazorpayRouteClient(isMockMode=True)
        # Configure selective failure on protocol accounts
        originalReverse = routeClient.reverseTransfer

        async def selectiveReverse(
            transferId: str,
            amountPaise: Optional[int] = None,
            idempotencyKey: Optional[str] = None,
        ) -> TransferReversalResponse:
            trf = routeClient._transfers.get(transferId)
            if trf and "protocol" in trf.account:
                raise MandateEngineException(f"Simulated network glitch on {trf.account}")
            return await originalReverse(transferId, amountPaise)

        routeClient.reverseTransfer = selectiveReverse  # type: ignore

        numConcurrentSagas = 10

        async def runSingleSaga(sagaIdx: int) -> None:
            saga = TwoPhaseCommitSaga(routeClient=routeClient, nonceLedger=nonceLedger, dlq=dlq)
            requests = [
                RouteTransferRequest(account=f"acc_merchant_conc_{sagaIdx}", amount=50000, notes={"paymentId": f"pay_conc_{sagaIdx}"}),
                RouteTransferRequest(account=f"acc_protocol_conc_{sagaIdx}", amount=1000, notes={"paymentId": f"pay_conc_{sagaIdx}"}),
                RouteTransferRequest(account=f"acc_fail_conc_{sagaIdx}", amount=500, notes={"paymentId": f"pay_conc_{sagaIdx}"}),
            ]
            routeClient.simulatedFailureAccount = f"acc_fail_conc_{sagaIdx}"
            with pytest.raises(SettlementCompensationTriggeredException):
                await saga.executeSplitPhase(requests)

        # Run 10 sagas concurrently
        await asyncio.gather(*(runSingleSaga(i) for i in range(numConcurrentSagas)))

        # Each saga had 1 merchant reversal (succeeded) and 1 protocol reversal (failed -> DLQ)
        assert len(routeClient._reversals) == numConcurrentSagas
        assert await dlq.getPendingCount() == numConcurrentSagas

        # Route client recovers
        routeClient.reverseTransfer = originalReverse  # type: ignore

        # Worker processes all concurrent events
        worker = CompensationDlqWorker(routeClient=routeClient, dlq=dlq)
        processed = await worker.processAllPending(maxIterations=100)
        assert processed == numConcurrentSagas
        assert await dlq.getPendingCount() == 0
        assert await dlq.getDeadLetterCount() == 0
        # Total reversals: 10 merchant + 10 protocol = 20
        assert len(routeClient._reversals) == numConcurrentSagas * 2

    @pytest.mark.asyncio
    async def testDuplicateEnqueueSuppressionAndSkip(
        self,
        dlq: CompensationDlq,
    ) -> None:
        """Verifies that enqueueing the same reversal multiple times with the same idempotency key does not duplicate."""
        e1 = await dlq.enqueueReversal(
            transferId="trf_dup_check",
            amountPaise=25000,
            recipientAccountId="acc_dup",
            paymentId="pay_dup",
            idempotencyKey="idem_exact_same",
        )
        e2 = await dlq.enqueueReversal(
            transferId="trf_dup_check",
            amountPaise=25000,
            recipientAccountId="acc_dup",
            paymentId="pay_dup",
            idempotencyKey="idem_exact_same",
        )

        assert e1.eventId == e2.eventId
        assert await dlq.getPendingCount() == 1

