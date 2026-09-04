"""Two-Phase Commit (2PC) Settlement Saga Coordinator with Rollback Compensation."""

import logging
import time
from typing import TYPE_CHECKING, Optional
from pydantic import BaseModel, ConfigDict, Field

logger = logging.getLogger(__name__)

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
from ..verification.settlementLedger import SettlementLedger
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
    razorpayOrderId: Optional[str] = Field(default=None)


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
        settlementLedger: Optional[SettlementLedger] = None,
    ) -> None:
        self._routeClient = routeClient
        self._nonceLedger = nonceLedger
        self.protocolFeeAccount = protocolFeeAccount
        self.protocolFeePaise = protocolFeePaise
        self.logisticsAccount = logisticsAccount
        self._dlq = dlq
        self._settlementLedger = settlementLedger
        self._saga = TwoPhaseCommitSaga(
            routeClient=self._routeClient,
            nonceLedger=self._nonceLedger,
            dlq=self._dlq,
            settlementLedger=self._settlementLedger,
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

    async def _releaseProvisionalSpend(
        self,
        intentMandate: IntentMandate,
        executionMandate: ExecutionMandate,
    ) -> None:
        """Returns budget booked for a settlement whose transfers were rolled back."""
        if self._settlementLedger is None:
            return
        await self._settlementLedger.releaseCumulativeSpend(
            mandateId=intentMandate.mandateId,
            amountPaise=executionMandate.settlementAmountPaise,
        )

    async def _createEvidenceOrder(
        self,
        executionMandate: ExecutionMandate,
        cartMandate: CartMandate,
    ) -> Optional[str]:
        """Creates an evidence order in Razorpay if live keys are present.

        This runs after _verifyAndCapturePhase (and thus after validateBudgetGate),
        preserving TC-03 invariant (0 calls on budget refusal). Failures are caught
        and logged without aborting the settlement saga.
        """
        try:
            # Read the buyer DID and the cart hash from the EXECUTION mandate, which is where
            # they live: CartMandate carries neither (it has cartId and merchantDid). Reading
            # them off the cart raised AttributeError on every settlement, and because this
            # helper degrades rather than raises, the only symptom was razorpayOrderId coming
            # back null -- a silent loss of the one real Razorpay call in the agent's path.
            #
            # Not truncated to 40 like the receipt: a DID is "did:agent:" plus 64 hex, so a
            # 40-char cut yields a prefix that identifies nobody and cannot be verified against
            # the mandate chain. Razorpay allows far more room in a notes value than in a
            # receipt, and an unverifiable note is worse than no note.
            notes = {
                "executionId": executionMandate.executionId,
                "buyerAgentDid": executionMandate.buyerAgentDid,
                "cartMandateHash": executionMandate.cartMandateHash,
                "cartId": cartMandate.cartId,
            }
            order = await self._routeClient.createOrder(
                amountPaise=executionMandate.settlementAmountPaise,
                receipt=executionMandate.executionId[:40],
                currency="INR",
                notes=notes,
            )
            return order.id
        except Exception as err:
            logger.warning(
                "Failed to create evidence order in Razorpay for execution %s: %s",
                executionMandate.executionId,
                err,
            )
            return None

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

        razorpayOrderId = await self._createEvidenceOrder(executionMandate, cartMandate)

        manifest = self.buildSplitManifest(cartMandate, merchantAccount)
        requests = self._buildTransferRequests(manifest, paymentId)
        try:
            transfers = await self._executeSplitPhase(requests, paymentId=paymentId)
        except Exception:
            # Capture succeeded and the split phase compensated it, so the buyer's budget must
            # not stay consumed. The cart claim is deliberately NOT released: reversals may
            # still be in flight or queued in the DLQ, and allowing an immediate retry could
            # pay the merchant twice. The claim expires on its own TTL.
            await self._releaseProvisionalSpend(intentMandate, executionMandate)
            raise

        # executionId is generated as a fixed "mandate_exec_" prefix followed by a random
        # suffix (see buyerSdkTs agentMandateBuilder.ts::createSignedExecutionMandate). Slicing
        # from the front captures only the constant prefix and collides across every
        # settlement, so the unique suffix must be taken from the tail instead.
        invoiceNumber = f"{invoicePrefix}{executionMandate.executionId[-8:].upper()}"
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
            razorpayOrderId=razorpayOrderId,
        )
