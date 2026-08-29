"""Razorpay Route client supporting both mock ledger and live HTTP transfers."""

import time
from typing import Any, Optional
import uuid
import httpx
from pydantic import BaseModel, ConfigDict, Field

from ..constants.settlementConstants import transferIdPrefix
from .settlementExceptions import MandateEngineException

defaultMockApiKey: str = "rzp_test_mock"
defaultMockApiSecret: str = "mock_secret"
defaultRazorpayBaseUrl: str = "https://api.razorpay.com/v1"
defaultRequestTimeoutSeconds: float = 30.0
httpStatusOkMin: int = 200
httpStatusOkMax: int = 300
headerContentTypeJson: str = "application/json"
headerAcceptJson: str = "application/json"
# Idempotency header name. VERIFY against the current Razorpay API reference before going
# live: Razorpay documents "X-Payout-Idempotency" for RazorpayX Payouts, and the header for
# Route transfers/reversals must be confirmed rather than assumed. The mechanism below is
# correct regardless; only this string is provider-specific.
headerIdempotencyKey: str = "X-Razorpay-Idempotency-Key"


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
    """Razorpay Route API adapter with deterministic mock ledger and live HTTP transport."""

    def __init__(
        self,
        apiKey: str = defaultMockApiKey,
        apiSecret: str = defaultMockApiSecret,
        baseUrl: str = defaultRazorpayBaseUrl,
        isMockMode: bool = True,
        httpClient: Optional[httpx.AsyncClient] = None,
        timeoutSeconds: float = defaultRequestTimeoutSeconds,
    ) -> None:
        self.apiKey = apiKey
        self.apiSecret = apiSecret
        self.baseUrl = baseUrl.rstrip("/")
        self.isMockMode = isMockMode
        self.timeoutSeconds = timeoutSeconds
        self._httpClient = httpClient
        self._ownsHttpClient = httpClient is None
        self._capturedPayments: dict[str, PaymentCaptureResponse] = {}
        self._transfers: dict[str, RouteTransferResponse] = {}
        self._reversals: dict[str, TransferReversalResponse] = {}
        self._idempotentTransfers: dict[str, RouteTransferResponse] = {}
        self.simulatedFailureAccount: Optional[str] = None
        self.simulatedReverseFailure: bool = False
        self.simulatedReverseFailureTransferId: Optional[str] = None
        self.simulatedReverseFailureAccount: Optional[str] = None
        self.simulatedReverseErrorType: str = "500"
        self.simulatedReverseFailureCount: Optional[int] = None

    def configureSimulatedReverseFailure(
        self,
        transferId: Optional[str] = None,
        account: Optional[str] = None,
        errorType: str = "500",
        failureCount: Optional[int] = None,
    ) -> None:
        """Configures simulated reversal failure for deterministic testing in mock mode."""
        self.simulatedReverseFailure = True
        self.simulatedReverseFailureTransferId = transferId
        self.simulatedReverseFailureAccount = account
        self.simulatedReverseErrorType = errorType
        self.simulatedReverseFailureCount = failureCount

    def resetSimulatedFailures(self) -> None:
        """Resets all simulated failure configurations to default state."""
        self.simulatedFailureAccount = None
        self.simulatedReverseFailure = False
        self.simulatedReverseFailureTransferId = None
        self.simulatedReverseFailureAccount = None
        self.simulatedReverseErrorType = "500"
        self.simulatedReverseFailureCount = None

    def _parseRazorpayErrorMessage(self, resp: httpx.Response) -> str:
        """Extracts human-readable error description from Razorpay JSON response."""
        try:
            body = resp.json()
            if isinstance(body, dict) and "error" in body:
                errorInfo = body["error"]
                if isinstance(errorInfo, dict):
                    return str(errorInfo.get("description") or errorInfo.get("code") or resp.text)
                return str(errorInfo)
        except Exception:
            pass
        return resp.text or f"HTTP {resp.status_code}"

    async def _sendHttpRequest(
        self,
        method: str,
        path: str,
        jsonPayload: Optional[dict[str, Any]] = None,
        idempotencyKey: Optional[str] = None,
    ) -> dict[str, Any]:
        """Executes authenticated HTTP request against Razorpay Route API.

        When idempotencyKey is supplied it is sent as a request header so that a retry of a
        timed-out money movement is collapsed by the provider instead of paying twice.
        """
        url = f"{self.baseUrl}{path}"
        auth = (self.apiKey, self.apiSecret)
        headers = {"Content-Type": headerContentTypeJson, "Accept": headerAcceptJson}
        if idempotencyKey:
            headers[headerIdempotencyKey] = idempotencyKey
        try:
            if self._httpClient is not None:
                resp = await self._httpClient.request(
                    method=method, url=url, json=jsonPayload, headers=headers,
                    auth=auth, timeout=self.timeoutSeconds,
                )
            else:
                async with httpx.AsyncClient(timeout=self.timeoutSeconds) as client:
                    resp = await client.request(
                        method=method, url=url, json=jsonPayload, headers=headers, auth=auth,
                    )
        except httpx.TimeoutException as err:
            raise MandateEngineException(f"Razorpay API request timed out: {url}") from err
        except httpx.RequestError as err:
            raise MandateEngineException(f"Razorpay API connection error: {str(err)}") from err

        if not (httpStatusOkMin <= resp.status_code < httpStatusOkMax):
            errorMessage = self._parseRazorpayErrorMessage(resp)
            raise MandateEngineException(f"Razorpay API error ({resp.status_code}): {errorMessage}")

        try:
            return resp.json()
        except Exception as err:
            raise MandateEngineException(f"Invalid JSON response from Razorpay API: {resp.text}") from err

    async def capturePayment(
        self,
        paymentId: str,
        amountPaise: int,
        currency: str = "INR",
    ) -> PaymentCaptureResponse:
        """Executes or mocks primary payment capture."""
        if self.isMockMode:
            captureRes = PaymentCaptureResponse(
                id=paymentId, entity="payment", amount=amountPaise, currency=currency,
                status="captured", method="upi", captured=True, createdAt=int(time.time()),
            )
            self._capturedPayments[paymentId] = captureRes
            return captureRes

        payload = {"amount": amountPaise, "currency": currency}
        data = await self._sendHttpRequest(method="POST", path=f"/payments/{paymentId}/capture", jsonPayload=payload)
        captureRes = PaymentCaptureResponse(
            id=str(data.get("id") or paymentId),
            entity=str(data.get("entity") or "payment"),
            amount=int(data.get("amount") or amountPaise),
            currency=str(data.get("currency") or currency),
            status=str(data.get("status") or "captured"),
            method=str(data.get("method") or "upi"),
            captured=bool(data.get("captured", True)),
            createdAt=int(data.get("created_at") or data.get("createdAt") or time.time()),
        )
        self._capturedPayments[captureRes.id] = captureRes
        return captureRes

    async def createTransfer(
        self,
        transferRequest: RouteTransferRequest,
        idempotencyKey: Optional[str] = None,
    ) -> RouteTransferResponse:
        """Executes or mocks POST /v1/transfers split transfer.

        A repeated idempotencyKey returns the original transfer instead of creating a second
        one, so retrying a request that timed out after the provider had already accepted it
        cannot pay the recipient twice.
        """
        if self.isMockMode:
            if idempotencyKey and idempotencyKey in self._idempotentTransfers:
                return self._idempotentTransfers[idempotencyKey]
            if self.simulatedFailureAccount and transferRequest.account == self.simulatedFailureAccount:
                raise MandateEngineException(f"Simulated Route transfer failure for account {transferRequest.account}")

            transferId = f"{transferIdPrefix}{uuid.uuid4().hex[:14]}"
            transferRes = RouteTransferResponse(
                id=transferId, entity="transfer", account=transferRequest.account,
                amount=transferRequest.amount, currency=transferRequest.currency,
                status="processed", createdAt=int(time.time()),
            )
            self._transfers[transferId] = transferRes
            if idempotencyKey:
                self._idempotentTransfers[idempotencyKey] = transferRes
            return transferRes

        payload = {
            "account": transferRequest.account,
            "amount": transferRequest.amount,
            "currency": transferRequest.currency,
            "notes": transferRequest.notes,
        }
        data = await self._sendHttpRequest(
            method="POST", path="/transfers", jsonPayload=payload, idempotencyKey=idempotencyKey,
        )
        transferRes = RouteTransferResponse(
            id=str(data["id"]),
            entity=str(data.get("entity") or "transfer"),
            account=str(data.get("account") or data.get("recipient") or transferRequest.account),
            amount=int(data.get("amount") or transferRequest.amount),
            currency=str(data.get("currency") or transferRequest.currency),
            status=str(data.get("status") or "processed"),
            createdAt=int(data.get("created_at") or data.get("createdAt") or time.time()),
        )
        self._transfers[transferRes.id] = transferRes
        return transferRes

    async def reverseTransfer(
        self,
        transferId: str,
        amountPaise: Optional[int] = None,
        idempotencyKey: Optional[str] = None,
    ) -> TransferReversalResponse:
        """Executes or mocks POST /v1/transfers/{id}/reversals compensation."""
        if self.isMockMode:
            if transferId not in self._transfers:
                raise MandateEngineException(f"Transfer {transferId} not found in ledger")

            originalTransfer = self._transfers[transferId]

            # Check simulated reversal failure conditions
            shouldFail = False
            if self.simulatedReverseFailure:
                if self.simulatedReverseFailureTransferId is None or self.simulatedReverseFailureTransferId == transferId:
                    if self.simulatedReverseFailureAccount is None or self.simulatedReverseFailureAccount == originalTransfer.account:
                        if self.simulatedReverseFailureCount is None:
                            shouldFail = True
                        elif self.simulatedReverseFailureCount > 0:
                            shouldFail = True
                            self.simulatedReverseFailureCount -= 1
                        else:
                            shouldFail = False

            if shouldFail:
                errType = self.simulatedReverseErrorType.lower()
                if errType == "timeout":
                    raise MandateEngineException(f"Razorpay API request timed out: /v1/transfers/{transferId}/reversals")
                elif errType in ("500", "502", "503", "504"):
                    raise MandateEngineException(f"Razorpay API error ({self.simulatedReverseErrorType}): Internal Server Error during transfer reversal")
                elif errType == "network":
                    raise MandateEngineException(f"Razorpay API connection error: Connection reset by peer for transfer {transferId}")
                else:
                    raise MandateEngineException(f"Simulated reversal failure for transfer {transferId}")

            reversalId = f"rev_{uuid.uuid4().hex[:14]}"
            reversalRes = TransferReversalResponse(
                id=reversalId, entity="reversal", transferId=transferId,
                amount=amountPaise or originalTransfer.amount,
                currency=originalTransfer.currency, status="processed",
                createdAt=int(time.time()),
            )
            self._reversals[reversalId] = reversalRes
            return reversalRes

        payload = {"amount": amountPaise, "currency": "INR"} if amountPaise is not None else None
        data = await self._sendHttpRequest(
            method="POST", path=f"/transfers/{transferId}/reversals",
            jsonPayload=payload, idempotencyKey=idempotencyKey,
        )
        reversalRes = TransferReversalResponse(
            id=str(data["id"]),
            entity=str(data.get("entity") or "reversal"),
            transferId=str(data.get("transfer_id") or data.get("transferId") or transferId),
            amount=int(data.get("amount") or amountPaise or 0),
            currency=str(data.get("currency") or "INR"),
            status=str(data.get("status") or "processed"),
            createdAt=int(data.get("created_at") or data.get("createdAt") or time.time()),
        )
        self._reversals[reversalRes.id] = reversalRes
        return reversalRes

    async def close(self) -> None:
        """Closes the underlying HTTP client if initialized."""
        if self._httpClient is not None:
            await self._httpClient.aclose()

    async def __aenter__(self) -> "RazorpayRouteClient":
        return self

    async def __aexit__(self, excType: Any, excVal: Any, excTb: Any) -> None:
        await self.close()

