"""Two-Phase Commit (2PC) state machine logic with rollback compensation."""

import logging
import time
from typing import TYPE_CHECKING, Optional

if TYPE_CHECKING:
    from .compensationDlq import CompensationDlq

from ..constants.settlementConstants import (
    purposeLogisticsSlaSettlement as logisticsPurpose,
    purposeMerchantNetSettlement as merchantPurpose,
    purposeProtocolFee as protocolPurpose,
    purposeTcsWithholding as tcsPurpose,
)
from ..crypto.cryptoKeyUtils import extractPublicKeyFromDid
from ..crypto.ed25519Verifier import Ed25519Verifier
from ..mandates.cartMandateSchema import CartMandate
from ..mandates.executionMandateSchema import ExecutionMandate
from ..mandates.intentMandateSchema import IntentMandate
from ..nonce.nonceLedger import NonceLedger
from ..verification.budgetGate import validateBudgetGate
from ..verification.settlementLedger import SettlementLedger
from ..verification.signatureChainVerifier import verifyMandateChain
from .razorpayRouteClient import (
    RazorpayRouteClient,
    RouteTransferRequest,
    RouteTransferResponse,
    TransferReversalResponse,
)
from .settlementExceptions import (
    InventoryLockExpiredException,
    SettlementCompensationTriggeredException,
)
from .splitManifestBuilder import SplitTransferManifest

logger = logging.getLogger(__name__)

# Must stay in sync with CompensationDlq's key format (compensationDlq.py) -- see
# _buildReversalIdempotencyKey for why the two paths must agree.
reversalIdempotencyPrefix: str = "cmp_"


class TwoPhaseCommitSaga:
    """Executes 2PC state machine: verification, capture, and compensating split transfers."""

    def __init__(
        self,
        routeClient: RazorpayRouteClient,
        nonceLedger: NonceLedger,
        dlq: Optional["CompensationDlq"] = None,
        settlementLedger: Optional[SettlementLedger] = None,
    ) -> None:
        self._routeClient = routeClient
        self._nonceLedger = nonceLedger
        self._dlq = dlq
        self._settlementLedger = settlementLedger

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
                except Exception as lookupErr:
                    logger.warning(
                        "DLQ compensated-check unavailable for %s (%s); proceeding with reversal",
                        completedTransfer.id, lookupErr,
                    )

            try:
                reversalRes = await self._routeClient.reverseTransfer(
                    transferId=completedTransfer.id,
                    amountPaise=completedTransfer.amount,
                    # Must match the key CompensationDlq assigns for this transfer. An inline
                    # reversal that times out is enqueued and retried by the DLQ worker; if the
                    # two paths used different keys the provider could reverse the same
                    # transfer twice, refunding more than was taken.
                    idempotencyKey=_buildReversalIdempotencyKey(completedTransfer.id),
                )
                if effectiveDlq is not None:
                    try:
                        await effectiveDlq.markCompensated(completedTransfer.id, reversalId=reversalRes.id)
                    except Exception as markErr:
                        logger.warning(
                            "Reversal %s succeeded but could not be marked compensated (%s); "
                            "a later retry will be deduplicated by idempotency key",
                            completedTransfer.id, markErr,
                        )
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
                    except Exception as dlqErr:
                        # Last line of defence: the DLQ is what guarantees a failed reversal is
                        # eventually retried. If its enqueue also fails, the reversal is lost
                        # entirely -- money stayed moved with no record. Never swallow this.
                        logger.error(
                            "2PC compensation LOST: transfer %s (%s paise to %s) failed reversal "
                            "(%s) AND could not be enqueued to the DLQ (%s). Manual reconciliation "
                            "required.",
                            completedTransfer.id, completedTransfer.amount,
                            completedTransfer.account, revErr, dlqErr,
                        )
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
        if manifest.tcsWithheldPaise > 0:
            requests.append(
                RouteTransferRequest(
                    account=manifest.tcsHoldingAccount,
                    amount=manifest.tcsWithheldPaise,
                    notes={"purpose": tcsPurpose, "paymentId": paymentId},
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
                transferResponse = await self._routeClient.createTransfer(
                    transferRequest,
                    idempotencyKey=_buildTransferIdempotencyKey(transferRequest, paymentId),
                )
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
        """Performs Phase 1 authentication, authorization, replay defence, and capture.

        Ordering is deliberate: authenticate (signatures, hash chain), then authorize (budget
        gate, delegated agent), and only then consume single-use state (nonce, cart claim,
        spend counter). Consuming the nonce first would let an unauthenticated caller who
        learns a nonce burn it and fail the legitimate settlement.
        """
        self.verifyMandateSignatures(intentMandate, cartMandate, executionMandate)
        verifyMandateChain(intentMandate, cartMandate, executionMandate)
        validateBudgetGate(intentMandate, cartMandate, executionMandate, serverTime)
        _verifyInventoryLockActive(cartMandate, serverTime)

        await self._nonceLedger.validateAndRecordNonce(
            nonce=executionMandate.nonce,
            timestamp=executionMandate.timestamp,
            serverTime=serverTime,
        )
        await self._claimSettlementSlot(intentMandate, executionMandate, serverTime)

        try:
            await self._routeClient.capturePayment(
                paymentId=paymentId,
                amountPaise=executionMandate.settlementAmountPaise,
            )
        except Exception:
            # The claim and the spend are reservations taken before capture so that two
            # concurrent settlements cannot both proceed. No money moved, so releasing them
            # is required -- otherwise a transient capture failure would permanently bar the
            # buyer from retrying their own cart and would silently consume their budget.
            await self.releaseSettlementSlot(intentMandate, executionMandate)
            raise

    async def releaseSettlementSlot(
        self,
        intentMandate: IntentMandate,
        executionMandate: ExecutionMandate,
    ) -> None:
        """Returns the cart claim and provisional spend after a settlement that did not complete."""
        if self._settlementLedger is None:
            return
        await self._settlementLedger.releaseCartClaim(executionMandate.cartMandateHash)
        await self._settlementLedger.releaseCumulativeSpend(
            mandateId=intentMandate.mandateId,
            amountPaise=executionMandate.settlementAmountPaise,
        )

    async def _claimSettlementSlot(
        self,
        intentMandate: IntentMandate,
        executionMandate: ExecutionMandate,
        serverTime: Optional[int] = None,
    ) -> None:
        """Claims the cart exactly once and books the spend against the mandate's cumulative cap."""
        if self._settlementLedger is None:
            return
        await self._settlementLedger.claimCartSettlement(executionMandate.cartMandateHash)
        await self._settlementLedger.recordCumulativeSpend(
            mandateId=intentMandate.mandateId,
            amountPaise=executionMandate.settlementAmountPaise,
            maxBudgetPaise=intentMandate.maxBudgetPaise,
            expiresAtUnix=intentMandate.validUntilTimestamp,
            serverTime=serverTime,
        )


def _verifyInventoryLockActive(
    cartMandate: CartMandate,
    serverTime: Optional[int] = None,
) -> None:
    """Rejects settlement once the cart's inventory reservation has lapsed.

    Without this the lock is advisory only: an expired reservation still settles, so stock
    released back to other buyers can be sold twice.
    """
    evaluatedAt = serverTime if serverTime is not None else int(time.time())
    if evaluatedAt > cartMandate.inventoryLockExpiresAt:
        raise InventoryLockExpiredException(
            f"Inventory lock {cartMandate.inventoryLockToken} expired at "
            f"{cartMandate.inventoryLockExpiresAt} (now {evaluatedAt}): ₹0 charged"
        )


def _buildTransferIdempotencyKey(
    transferRequest: RouteTransferRequest,
    paymentId: Optional[str],
) -> str:
    """Derives a stable idempotency key for one leg of a split.

    Keyed on (payment, recipient, purpose) so that re-issuing the same leg -- after a timeout
    where the provider may already have accepted it -- is collapsed rather than paid twice,
    while genuinely distinct legs of the same payment stay independent.
    """
    purpose = (transferRequest.notes or {}).get("purpose", "split")
    effectivePaymentId = paymentId or (transferRequest.notes or {}).get("paymentId", "unknown")
    return f"trf_{effectivePaymentId}_{transferRequest.account}_{purpose}"


def _buildReversalIdempotencyKey(transferId: str) -> str:
    """Derives the reversal idempotency key for a transfer.

    Deliberately identical to the key CompensationDlq assigns (`cmp_{transferId}`), so an
    inline reversal and a later DLQ retry of the same transfer collapse into one reversal
    at the provider rather than refunding twice.
    """
    return f"{reversalIdempotencyPrefix}{transferId}"
