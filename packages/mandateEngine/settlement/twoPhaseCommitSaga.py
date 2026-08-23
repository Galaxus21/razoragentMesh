"""Two-Phase Commit (2PC) state machine logic with rollback compensation."""

from typing import Optional

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
)
from .settlementExceptions import SettlementCompensationTriggeredException
from .splitManifestBuilder import SplitTransferManifest

merchantPurpose: str = "merchant_net_settlement"
protocolPurpose: str = "protocol_fee"
logisticsPurpose: str = "logistics_sla_settlement"


class TwoPhaseCommitSaga:
    """Executes 2PC state machine: verification, capture, and compensating split transfers."""

    def __init__(
        self,
        routeClient: RazorpayRouteClient,
        nonceLedger: NonceLedger,
    ) -> None:
        self._routeClient = routeClient
        self._nonceLedger = nonceLedger

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

    async def compensateTransfers(self, completedTransfers: list[RouteTransferResponse]) -> None:
        """Rollback compensation: reverses all successful transfers in LIFO order."""
        for trf in reversed(completedTransfers):
            await self._routeClient.reverseTransfer(trf.id, trf.amount)

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
    ) -> list[RouteTransferResponse]:
        """Executes transfers sequentially with rollback on any failure."""
        completed: list[RouteTransferResponse] = []
        try:
            for req in transferRequests:
                res = await self._routeClient.createTransfer(req)
                completed.append(res)
            return completed
        except Exception as err:
            await self.compensateTransfers(completed)
            raise SettlementCompensationTriggeredException(
                f"2PC Transfer failed: triggered rollback of {len(completed)} transfers: {str(err)}"
            ) from err

    async def verifyAndCapturePhase(
        self,
        intentM: IntentMandate,
        cartM: CartMandate,
        execM: ExecutionMandate,
        paymentId: str,
        serverTime: Optional[int] = None,
    ) -> None:
        """Performs Phase 1 nonce, signature, hash chain, budget gate checks and capture."""
        await self._nonceLedger.validateAndRecordNonce(
            nonce=execM.nonce,
            timestamp=execM.timestamp,
            serverTime=serverTime,
        )
        self.verifyMandateSignatures(intentM, cartM, execM)
        verifyMandateChain(intentM, cartM, execM)
        validateBudgetGate(intentM, cartM, execM, serverTime)
        await self._routeClient.capturePayment(
            paymentId=paymentId,
            amountPaise=execM.settlementAmountPaise,
        )
