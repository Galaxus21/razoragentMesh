"""Two-Phase Commit (2PC) Settlement Saga Coordinator with Rollback Compensation."""

import time
from typing import TYPE_CHECKING, Optional
from pydantic import BaseModel, ConfigDict, Field

if TYPE_CHECKING:
    from .compensationDlq import CompensationDlq

from ..mandates.cartMandateSchema import CartMandate
from ..mandates.executionMandateSchema import ExecutionMandate
from ..mandates.intentMandateSchema import IntentMandate
from ..nonce.nonceLedger import NonceLedger
from ..tax.gstrInvoiceEngine import (
    GstrInvoicePayload,
    generateGstrInvoice,
)
from .razorpayRouteClient import (
    RazorpayRouteClient,
    RouteTransferRequest,
    RouteTransferResponse,
    TransferReversalResponse,
)
from .splitManifestBuilder import (
    SplitTransferManifest,
    buildSplitManifest,
    defaultLogisticsAccount,
    defaultProtocolFeeAccount,
    defaultProtocolFeePaise,
)
from .twoPhaseCommitSaga import TwoPhaseCommitSaga

capturedStatus: str = "captured"
invoicePrefix: str = "INV-"


class SettlementResult(BaseModel):
    """Immutable result of a completed 2PC settlement saga."""

    model_config = ConfigDict(frozen=True, extra="forbid")

    status: str = Field(default=capturedStatus)
    paymentId: str = Field(min_length=1)
    amountPaise: int = Field(gt=0)
    transfers: list[RouteTransferResponse] = Field(min_length=1)
    invoice: GstrInvoicePayload
    settledAt: int = Field(gt=0)


class SettlementOrchestrator:
    """Coordinates AP2 mandate verification and 2PC Razorpay Route split settlement."""

    def __init__(
        self,
        routeClient: RazorpayRouteClient,
        nonceLedger: NonceLedger,
        protocolFeeAccount: str = defaultProtocolFeeAccount,
        protocolFeePaise: int = defaultProtocolFeePaise,
        logisticsAccount: str = defaultLogisticsAccount,
        dlq: Optional["CompensationDlq"] = None,
    ) -> None:
        self._routeClient = routeClient
        self._nonceLedger = nonceLedger
        self.protocolFeeAccount = protocolFeeAccount
        self.protocolFeePaise = protocolFeePaise
        self.logisticsAccount = logisticsAccount
        self._dlq = dlq
        self._saga = TwoPhaseCommitSaga(
            routeClient=self._routeClient,
            nonceLedger=self._nonceLedger,
            dlq=self._dlq,
        )

    def buildSplitManifest(
        self,
        cartMandate: CartMandate,
        merchantAccount: str,
        customProtocolFeePaise: Optional[int] = None,
    ) -> SplitTransferManifest:
        """Computes split amounts for merchant, logistics partner, and protocol fee."""
        return buildSplitManifest(
            cartMandate=cartMandate,
            merchantAccount=merchantAccount,
            protocolFeeAccount=self.protocolFeeAccount,
            protocolFeePaise=self.protocolFeePaise,
            logisticsAccount=self.logisticsAccount,
            customProtocolFeePaise=customProtocolFeePaise,
        )

    def _verifyMandateSignatures(
        self,
        intentMandate: IntentMandate,
        cartMandate: CartMandate,
        executionMandate: ExecutionMandate,
    ) -> None:
        """Verifies Ed25519 signatures for all 3 mandates."""
        self._saga.verifyMandateSignatures(intentMandate, cartMandate, executionMandate)

    async def _compensateTransfers(
        self,
        completedTransfers: list[RouteTransferResponse],
        failureReason: str = "2PC split transfer rollback",
        paymentId: Optional[str] = None,
    ) -> list[Optional[TransferReversalResponse]]:
        """Rollback compensation: reverses all successful transfers in LIFO order."""
        return await self._saga.compensateTransfers(
            completedTransfers=completedTransfers,
            failureReason=failureReason,
            paymentId=paymentId,
        )

    def _buildTransferRequests(
        self,
        manifest: SplitTransferManifest,
        paymentId: str,
    ) -> list[RouteTransferRequest]:
        """Creates split transfer request objects for the saga."""
        return self._saga.buildTransferRequests(manifest, paymentId)

    async def _executeSplitPhase(
        self,
        transferRequests: list[RouteTransferRequest],
        paymentId: Optional[str] = None,
    ) -> list[RouteTransferResponse]:
        """Executes transfers sequentially with rollback on any failure."""
        return await self._saga.executeSplitPhase(transferRequests, paymentId=paymentId)

    async def _verifyAndCapturePhase(
        self,
        intentM: IntentMandate,
        cartM: CartMandate,
        execM: ExecutionMandate,
        paymentId: str,
        serverTime: Optional[int] = None,
    ) -> None:
        """Performs Phase 1 nonce, signature, hash chain, budget gate checks and capture."""
        await self._saga.verifyAndCapturePhase(intentM, cartM, execM, paymentId, serverTime)

    async def executeSettlementSaga(
        self,
        intentMandate: IntentMandate,
        cartMandate: CartMandate,
        executionMandate: ExecutionMandate,
        merchantAccount: str,
        paymentId: str,
        serverTime: Optional[int] = None,
    ) -> SettlementResult:
        """Executes 2PC saga with full validation, primary capture, and split transfers."""
        await self._verifyAndCapturePhase(intentMandate, cartMandate, executionMandate, paymentId, serverTime)

        manifest = self.buildSplitManifest(cartMandate, merchantAccount)
        requests = self._buildTransferRequests(manifest, paymentId)
        transfers = await self._executeSplitPhase(requests, paymentId=paymentId)

        invoiceNumber = f"{invoicePrefix}{executionMandate.executionId[:8].upper()}"
        invoice = generateGstrInvoice(
            cartMandate=cartMandate,
            executionMandate=executionMandate,
            invoiceNumber=invoiceNumber,
            invoiceTimestamp=serverTime,
        )

        return SettlementResult(
            status=capturedStatus,
            paymentId=paymentId,
            amountPaise=executionMandate.settlementAmountPaise,
            transfers=transfers,
            invoice=invoice,
            settledAt=int(time.time()),
        )
