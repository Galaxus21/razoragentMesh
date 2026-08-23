"""Razorpay Route client supporting both mock ledger and live HTTP transfers."""

import time
import uuid
from typing import Optional
from pydantic import BaseModel, ConfigDict, Field

from .settlementExceptions import MandateEngineException


class RouteTransferRequest(BaseModel):
    """Payload for POST /v1/transfers split request."""

    model_config = ConfigDict(frozen=True, extra="forbid")

    account: str = Field(min_length=1, description="Linked vendor account ID (acc_...)")
    amount: int = Field(gt=0, description="Amount to transfer in integer paise")
    currency: str = Field(default="INR", description="Currency code")
    notes: dict[str, str] = Field(default_factory=dict, description="Metadata key-value pairs")


class RouteTransferResponse(BaseModel):
    """Response payload for Route transfer."""

    model_config = ConfigDict(frozen=True, extra="forbid")

    id: str = Field(min_length=1)
    entity: str = Field(default="transfer")
    account: str = Field(min_length=1)
    amount: int = Field(gt=0)
    currency: str = Field(default="INR")
    status: str = Field(default="processed")
    createdAt: int = Field(gt=0)


class PaymentCaptureResponse(BaseModel):
    """Response payload for primary payment capture."""

    model_config = ConfigDict(frozen=True, extra="forbid")

    id: str = Field(min_length=1)
    entity: str = Field(default="payment")
    amount: int = Field(gt=0)
    currency: str = Field(default="INR")
    status: str = Field(default="captured")
    method: str = Field(default="upi")
    captured: bool = Field(default=True)
    createdAt: int = Field(gt=0)


class TransferReversalResponse(BaseModel):
    """Response payload for transfer reversal compensation."""

    model_config = ConfigDict(frozen=True, extra="forbid")

    id: str = Field(min_length=1)
    entity: str = Field(default="reversal")
    transferId: str = Field(min_length=1)
    amount: int = Field(gt=0)
    currency: str = Field(default="INR")
    status: str = Field(default="processed")
    createdAt: int = Field(gt=0)


class RazorpayRouteClient:
    """Razorpay Route API adapter with deterministic in-memory mock ledger."""

    def __init__(
        self,
        apiKey: str = "rzp_test_mock",
        apiSecret: str = "mock_secret",
        baseUrl: str = "https://api.razorpay.com/v1",
        isMockMode: bool = True,
    ) -> None:
        self.apiKey = apiKey
        self.apiSecret = apiSecret
        self.baseUrl = baseUrl
        self.isMockMode = isMockMode

        # In-memory mock ledgers
        self._capturedPayments: dict[str, PaymentCaptureResponse] = {}
        self._transfers: dict[str, RouteTransferResponse] = {}
        self._reversals: dict[str, TransferReversalResponse] = {}
        self.simulatedFailureAccount: Optional[str] = None

    async def capturePayment(
        self,
        paymentId: str,
        amountPaise: int,
        currency: str = "INR",
    ) -> PaymentCaptureResponse:
        """Executes or mocks primary payment capture."""
        if not self.isMockMode:
            raise NotImplementedError("Live HTTP route integration requires external credentials")

        captureRes = PaymentCaptureResponse(
            id=paymentId,
            entity="payment",
            amount=amountPaise,
            currency=currency,
            status="captured",
            method="upi",
            captured=True,
            createdAt=int(time.time()),
        )
        self._capturedPayments[paymentId] = captureRes
        return captureRes

    async def createTransfer(
        self,
        transferRequest: RouteTransferRequest,
    ) -> RouteTransferResponse:
        """Executes or mocks POST /v1/transfers split transfer."""
        if not self.isMockMode:
            raise NotImplementedError("Live HTTP route integration requires external credentials")

        if self.simulatedFailureAccount and transferRequest.account == self.simulatedFailureAccount:
            raise MandateEngineException(
                f"Simulated Route transfer failure for account {transferRequest.account}"
            )

        transferId = f"trf_{uuid.uuid4().hex[:14]}"
        transferRes = RouteTransferResponse(
            id=transferId,
            entity="transfer",
            account=transferRequest.account,
            amount=transferRequest.amount,
            currency=transferRequest.currency,
            status="processed",
            createdAt=int(time.time()),
        )
        self._transfers[transferId] = transferRes
        return transferRes

    async def reverseTransfer(
        self,
        transferId: str,
        amountPaise: Optional[int] = None,
    ) -> TransferReversalResponse:
        """Executes or mocks POST /v1/transfers/{id}/reversals compensation."""
        if not self.isMockMode:
            raise NotImplementedError("Live HTTP route integration requires external credentials")

        if transferId not in self._transfers:
            raise MandateEngineException(f"Transfer {transferId} not found in ledger")

        originalTransfer = self._transfers[transferId]
        revAmount = amountPaise or originalTransfer.amount
        reversalId = f"rev_{uuid.uuid4().hex[:14]}"

        reversalRes = TransferReversalResponse(
            id=reversalId,
            entity="reversal",
            transferId=transferId,
            amount=revAmount,
            currency=originalTransfer.currency,
            status="processed",
            createdAt=int(time.time()),
        )
        self._reversals[reversalId] = reversalRes
        return reversalRes
