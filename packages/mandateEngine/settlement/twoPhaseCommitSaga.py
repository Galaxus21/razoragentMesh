"""Two-Phase Commit (2PC) state machine logic with rollback compensation."""

from typing import TYPE_CHECKING, Optional

if TYPE_CHECKING:
    from .compensationDlq import CompensationDlq

from ..constants.settlementConstants import (
    purposeLogisticsSlaSettlement as logisticsPurpose,
    purposeMerchantNetSettlement as merchantPurpose,
    purposeProtocolFee as protocolPurpose,
)
from ..crypto.cryptoKeyUtils import extractPublicKeyFromDid
from ..crypto.ed25519Verifier import Ed25519Verifier
from ..mandates.cartMandateSchema import CartMandate
from ..mandates.executionMandateSchema import ExecutionMandate
from ..mandates.intentMandateSchema import IntentMandate
from ..nonce.nonceLedger import NonceLedger
from ..verification.budgetGate import validateBudgetGate
from ..verification.signatureChainVerifier import verifyMandateChain
from .razorpayRouteClient import (
    RazorpayRouteClient,
    RouteTransferRequest,
    RouteTransferResponse,
    TransferReversalResponse,
)
from .settlementExceptions import SettlementCompensationTriggeredException
from .splitManifestBuilder import SplitTransferManifest


class TwoPhaseCommitSaga:
    """Executes 2PC state machine: verification, capture, and compensating split transfers."""

    def __init__(
        self,
        routeClient: RazorpayRouteClient,
        nonceLedger: NonceLedger,
        dlq: Optional["CompensationDlq"] = None,
    ) -> None:
        self._routeClient = routeClient
        self._nonceLedger = nonceLedger
        self._dlq = dlq

    def verifyMandateSignatures(
        self,
        intentMandate: IntentMandate,
        cartMandate: CartMandate,
        executionMandate: ExecutionMandate,
    ) -> None:
        """Verifies Ed25519 signatures for all 3 mandates."""
        userKey = extractPublicKeyFromDid(intentMandate.userDid)
        Ed25519Verifier.verifyPayloadSignature(
            publicKeyHex=userKey,
            payload={k: v for k, v in intentMandate.model_dump().items() if k != "userSignature"},
            signatureHex=intentMandate.userSignature,
            raiseOnFailure=True,
        )

        merchantKey = extractPublicKeyFromDid(cartMandate.merchantDid)
        Ed25519Verifier.verifyPayloadSignature(
            publicKeyHex=merchantKey,
            payload={k: v for k, v in cartMandate.model_dump().items() if k != "merchantSignature"},
            signatureHex=cartMandate.merchantSignature,
            raiseOnFailure=True,
        )

        agentKey = extractPublicKeyFromDid(executionMandate.buyerAgentDid)
        Ed25519Verifier.verifyPayloadSignature(
            publicKeyHex=agentKey,
            payload={k: v for k, v in executionMandate.model_dump().items() if k != "agentSignature"},
            signatureHex=executionMandate.agentSignature,
            raiseOnFailure=True,
        )

    async def compensateTransfers(
        self,
        completedTransfers: list[RouteTransferResponse],
        failureReason: str = "2PC split transfer failed",
        paymentId: Optional[str] = None,
        dlq: Optional["CompensationDlq"] = None,
    ) -> list[Optional[TransferReversalResponse]]:
        """Rollback compensation: reverses all successful transfers in LIFO order.

        If a reversal fails (e.g. Route API timeout or 5xx):
        - If DLQ is configured, enqueues an immutable CompensationEvent to the DLQ.
        - Continues reversing remaining completed transfers without early abort.
        """
        effectiveDlq = dlq if dlq is not None else self._dlq
        reversals: list[Optional[TransferReversalResponse]] = []

        for completedTransfer in reversed(completedTransfers):
            if effectiveDlq is not None:
                try:
                    if await effectiveDlq.isAlreadyCompensated(completedTransfer.id):
                        continue
                except Exception:
                    pass

            try:
                reversalRes = await self._routeClient.reverseTransfer(
                    transferId=completedTransfer.id,
                    amountPaise=completedTransfer.amount,
                )
                if effectiveDlq is not None:
                    try:
                        await effectiveDlq.markCompensated(completedTransfer.id, reversalId=reversalRes.id)
                    except Exception:
                        pass
                reversals.append(reversalRes)
            except Exception as revErr:
                if effectiveDlq is not None:
                    try:
                        await effectiveDlq.enqueueReversal(
                            transferId=completedTransfer.id,
                            amountPaise=completedTransfer.amount,
                            recipientAccountId=completedTransfer.account,
                            paymentId=paymentId,
                            reason=f"2PC reversal failure: {str(revErr)} (trigger: {failureReason})",
                            metadata={
                                "currency": completedTransfer.currency,
                                "originalError": str(revErr),
                                "failureReason": failureReason,
                            },
                        )
                    except Exception:
                        pass
                reversals.append(None)

        return reversals

    def buildTransferRequests(
        self,
        manifest: SplitTransferManifest,
        paymentId: str,
    ) -> list[RouteTransferRequest]:
        """Creates split transfer request objects for the saga."""
        requests = [
            RouteTransferRequest(
                account=manifest.merchantAccount,
                amount=manifest.merchantAmountPaise,
                notes={"purpose": merchantPurpose, "paymentId": paymentId},
            )
        ]
        if manifest.protocolFeePaise > 0:
            requests.append(
                RouteTransferRequest(
                    account=manifest.protocolFeeAccount,
                    amount=manifest.protocolFeePaise,
                    notes={"purpose": protocolPurpose, "paymentId": paymentId},
                )
            )
        if manifest.logisticsAmountPaise > 0:
            requests.append(
                RouteTransferRequest(
                    account=manifest.logisticsAccount,
                    amount=manifest.logisticsAmountPaise,
                    notes={"purpose": logisticsPurpose, "paymentId": paymentId},
                )
            )
        return requests

    async def executeSplitPhase(
        self,
        transferRequests: list[RouteTransferRequest],
        paymentId: Optional[str] = None,
        dlq: Optional["CompensationDlq"] = None,
    ) -> list[RouteTransferResponse]:
        """Executes transfers sequentially with rollback on any failure."""
        completed: list[RouteTransferResponse] = []
        try:
            for transferRequest in transferRequests:
                transferResponse = await self._routeClient.createTransfer(transferRequest)
                completed.append(transferResponse)
            return completed
        except Exception as err:
            if paymentId is None and transferRequests and transferRequests[0].notes:
                paymentId = transferRequests[0].notes.get("paymentId")

            await self.compensateTransfers(
                completedTransfers=completed,
                failureReason=str(err),
                paymentId=paymentId,
                dlq=dlq,
            )
            raise SettlementCompensationTriggeredException(
                f"2PC Transfer failed: triggered rollback of {len(completed)} transfers: {str(err)}"
            ) from err

    async def verifyAndCapturePhase(
        self,
        intentMandate: IntentMandate,
        cartMandate: CartMandate,
        executionMandate: ExecutionMandate,
        paymentId: str,
        serverTime: Optional[int] = None,
    ) -> None:
        """Performs Phase 1 nonce, signature, hash chain, budget gate checks and capture."""
        await self._nonceLedger.validateAndRecordNonce(
            nonce=executionMandate.nonce,
            timestamp=executionMandate.timestamp,
            serverTime=serverTime,
        )
        self.verifyMandateSignatures(intentMandate, cartMandate, executionMandate)
        verifyMandateChain(intentMandate, cartMandate, executionMandate)
        validateBudgetGate(intentMandate, cartMandate, executionMandate, serverTime)
        await self._routeClient.capturePayment(
            paymentId=paymentId,
            amountPaise=executionMandate.settlementAmountPaise,
        )
