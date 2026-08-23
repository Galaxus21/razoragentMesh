"""Two-Phase Commit (2PC) Settlement Saga Coordinator with Rollback Compensation."""

import time
from typing import Optional
from pydantic import BaseModel, ConfigDict, Field

from razoragentMesh.packages.mandateEngine.budgetGate import validateBudgetGate
from razoragentMesh.packages.mandateEngine.cartMandateSchema import CartMandate
from razoragentMesh.packages.mandateEngine.cryptoKeyUtils import extractPublicKeyFromDid
from razoragentMesh.packages.mandateEngine.ed25519Verifier import Ed25519Verifier
from razoragentMesh.packages.mandateEngine.executionMandateSchema import ExecutionMandate
from razoragentMesh.packages.mandateEngine.gstrInvoiceEngine import (
    GstrInvoicePayload,
    generateGstrInvoice,
)
from razoragentMesh.packages.mandateEngine.intentMandateSchema import IntentMandate
from razoragentMesh.packages.mandateEngine.mandateFactory import verifyMandateHashChain
from razoragentMesh.packages.mandateEngine.nonceLedger import NonceLedger
from razoragentMesh.packages.mandateEngine.razorpayRouteClient import (
    RazorpayRouteClient,
    RouteTransferRequest,
    RouteTransferResponse,
)
from razoragentMesh.packages.mandateEngine.settlementExceptions import (
    SettlementCompensationTriggeredException,
)


class SplitTransferManifest(BaseModel):
    """Calculated split manifest for merchant, protocol, and logistics accounts."""

    model_config = ConfigDict(frozen=True, extra="forbid")

    merchantAccount: str = Field(min_length=1)
    merchantAmountPaise: int = Field(gt=0)
    protocolFeeAccount: str = Field(min_length=1)
    protocolFeePaise: int = Field(ge=0)
    logisticsAccount: str = Field(min_length=1)
    logisticsAmountPaise: int = Field(ge=0)
    totalPaise: int = Field(gt=0)


class SettlementResult(BaseModel):
    """Immutable result of a completed 2PC settlement saga."""

    model_config = ConfigDict(frozen=True, extra="forbid")

    status: str = Field(default="captured")
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
        protocolFeeAccount: str = "acc_protocol_fee",
        protocolFeePaise: int = 50,
        logisticsAccount: str = "acc_logistics_delhivery",
    ) -> None:
        self._routeClient = routeClient
        self._nonceLedger = nonceLedger
        self.protocolFeeAccount = protocolFeeAccount
        self.protocolFeePaise = protocolFeePaise
        self.logisticsAccount = logisticsAccount

    def buildSplitManifest(
        self,
        cartMandate: CartMandate,
        merchantAccount: str,
        customProtocolFeePaise: Optional[int] = None,
    ) -> SplitTransferManifest:
        """Computes split amounts for merchant, logistics partner, and protocol fee."""
        protoFee = customProtocolFeePaise if customProtocolFeePaise is not None else self.protocolFeePaise
        shipping = cartMandate.shippingPaise
        grossTotal = cartMandate.totalPaise

        merchantNet = grossTotal - protoFee - shipping
        if merchantNet <= 0:
            merchantNet = grossTotal

        return SplitTransferManifest(
            merchantAccount=merchantAccount,
            merchantAmountPaise=merchantNet,
            protocolFeeAccount=self.protocolFeeAccount,
            protocolFeePaise=protoFee,
            logisticsAccount=self.logisticsAccount,
            logisticsAmountPaise=shipping,
            totalPaise=grossTotal,
        )

    def _verifyMandateSignatures(
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

    async def _compensateTransfers(self, completedTransfers: list[RouteTransferResponse]) -> None:
        """Rollback compensation: reverses all successful transfers in LIFO order."""
        for trf in reversed(completedTransfers):
            await self._routeClient.reverseTransfer(trf.id, trf.amount)

    def _buildTransferRequests(
        self,
        manifest: SplitTransferManifest,
        paymentId: str,
    ) -> list[RouteTransferRequest]:
        """Creates split transfer request objects for the saga."""
        requests = [
            RouteTransferRequest(
                account=manifest.merchantAccount,
                amount=manifest.merchantAmountPaise,
                notes={"purpose": "merchant_net_settlement", "paymentId": paymentId},
            )
        ]
        if manifest.protocolFeePaise > 0:
            requests.append(
                RouteTransferRequest(
                    account=manifest.protocolFeeAccount,
                    amount=manifest.protocolFeePaise,
                    notes={"purpose": "protocol_fee", "paymentId": paymentId},
                )
            )
        if manifest.logisticsAmountPaise > 0:
            requests.append(
                RouteTransferRequest(
                    account=manifest.logisticsAccount,
                    amount=manifest.logisticsAmountPaise,
                    notes={"purpose": "logistics_sla_settlement", "paymentId": paymentId},
                )
            )
        return requests

    async def _executeSplitPhase(
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
            await self._compensateTransfers(completed)
            raise SettlementCompensationTriggeredException(
                f"2PC Transfer failed: triggered rollback of {len(completed)} transfers: {str(err)}"
            ) from err

    async def _verifyAndCapturePhase(
        self,
        intentM: IntentMandate,
        cartM: CartMandate,
        execM: ExecutionMandate,
        paymentId: str,
        serverTime: Optional[int],
    ) -> None:
        """Performs Phase 1 nonce, signature, hash chain, budget gate checks and capture."""
        await self._nonceLedger.validateAndRecordNonce(
            nonce=execM.nonce,
            timestamp=execM.timestamp,
            serverTime=serverTime,
        )
        self._verifyMandateSignatures(intentM, cartM, execM)
        verifyMandateHashChain(intentM, cartM, execM)
        validateBudgetGate(intentM, cartM, execM, serverTime)
        await self._routeClient.capturePayment(
            paymentId=paymentId,
            amountPaise=execM.settlementAmountPaise,
        )

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
        transfers = await self._executeSplitPhase(requests)

        invoice = generateGstrInvoice(
            cartMandate=cartMandate,
            executionMandate=executionMandate,
            invoiceNumber=f"INV-{executionMandate.executionId[:8].upper()}",
            invoiceTimestamp=serverTime,
        )

        return SettlementResult(
            status="captured",
            paymentId=paymentId,
            amountPaise=executionMandate.settlementAmountPaise,
            transfers=transfers,
            invoice=invoice,
            settledAt=int(time.time()),
        )
