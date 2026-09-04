"""FastAPI route endpoints for Razorpay Standard Web Checkout (Human Path).

Provides the human buyer counterpart to the agentic mandate flow:
- POST /api/v1/checkout/order: creates a real Razorpay test-mode order using the same
  createOrder method on RazorpayRouteClient that the settlement saga uses.
- POST /api/v1/checkout/verify: validates payment signatures using HMAC-SHA256 with
  timing-safe compare_digest comparison.
"""

import hashlib
import hmac
from typing import Any, Dict, Optional

from fastapi import Depends, FastAPI, HTTPException, Request, status
from fastapi.responses import JSONResponse
from pydantic import BaseModel, ConfigDict, Field

from ..config import getMandateEngineSettings
from ..dependencies import getRouteClient

minOrderAmountPaise: int = 100
endpointCheckoutOrder: str = "/api/v1/checkout/order"
endpointCheckoutVerify: str = "/api/v1/checkout/verify"
endpointCheckoutConfig: str = "/api/v1/checkout/config"
sha256DigestName: str = "sha256"


class CheckoutOrderRequestSchema(BaseModel):
    """Payload for creating a Razorpay checkout order."""

    model_config = ConfigDict(frozen=True, extra="forbid")

    amountPaise: int = Field(description="Order amount in integer paise (minimum 100)")
    receipt: str = Field(min_length=1, max_length=40, description="Receipt reference identifier")
    notes: Optional[Dict[str, str]] = Field(default=None, description="Optional key-value metadata")


class CheckoutOrderResponseSchema(BaseModel):
    """Response returned upon successful order creation."""

    model_config = ConfigDict(frozen=True, extra="forbid")

    orderId: str = Field(description="Razorpay order identifier")
    amountPaise: int = Field(description="Order amount in integer paise")
    currency: str = Field(default="INR", description="Currency code")
    keyId: str = Field(description="Razorpay Key ID for client checkout initialization")


class CheckoutConfigResponseSchema(BaseModel):
    """Publishable checkout configuration, safe to hand to a browser.

    Only the key ID travels: it is the half of the pair Razorpay's own checkout.js expects in
    page source, whereas the secret stays in the engine and is used solely to sign and to verify.
    This exists so the dashboard can open the modal on an order the settlement saga ALREADY
    created -- an agent's evidence order -- without creating a second, duplicate order just to
    learn the key id.
    """

    model_config = ConfigDict(frozen=True, extra="forbid")

    keyId: str = Field(description="Razorpay Key ID for client checkout initialization")
    credentialsPresent: bool = Field(description="False when the engine is running in mock mode")


def registerCheckoutRoutes(app: FastAPI) -> None:
    """Binds the human checkout order creation and verification routes onto the FastAPI app."""

    @app.get(
        endpointCheckoutConfig,
        summary="Publishable Razorpay key id for opening checkout on an existing order",
        response_model=CheckoutConfigResponseSchema,
        status_code=status.HTTP_200_OK,
    )
    async def readCheckoutConfig() -> CheckoutConfigResponseSchema:
        """Returns the publishable key id without creating an order.

        Deliberately 200-with-a-flag rather than 503 when credentials are absent: the caller is a
        page that wants to explain why checkout is unavailable, and an error status would render
        as a network failure instead of the honest "engine is in mock mode" message.
        """
        settings = getMandateEngineSettings()
        return CheckoutConfigResponseSchema(
            keyId=settings.razorpayKeyId if settings.hasRazorpayCredentials else "",
            credentialsPresent=settings.hasRazorpayCredentials,
        )

    @app.post(
        endpointCheckoutOrder,
        summary="Create Razorpay test-mode order for Standard Web Checkout",
        response_model=CheckoutOrderResponseSchema,
        status_code=status.HTTP_200_OK,
    )
    async def createCheckoutOrder(
        payload: CheckoutOrderRequestSchema,
        routeClient: Any = Depends(getRouteClient),
    ) -> CheckoutOrderResponseSchema:
        """Creates a real Razorpay test-mode order for standard web checkout modal."""
        if payload.amountPaise < minOrderAmountPaise:
            raise HTTPException(
                status_code=status.HTTP_400_BAD_REQUEST,
                detail=f"amountPaise must be at least {minOrderAmountPaise} paise (Razorpay minimum)",
            )

        settings = getMandateEngineSettings()
        if not settings.hasRazorpayCredentials:
            raise HTTPException(
                status_code=status.HTTP_503_SERVICE_UNAVAILABLE,
                detail="Checkout requires Razorpay test-mode credentials (RAZORPAY_KEY_ID, RAZORPAY_KEY_SECRET)",
            )

        orderResponse = await routeClient.createOrder(
            amountPaise=payload.amountPaise,
            receipt=payload.receipt,
            notes=payload.notes,
        )

        return CheckoutOrderResponseSchema(
            orderId=orderResponse.id,
            amountPaise=orderResponse.amount,
            currency=orderResponse.currency,
            keyId=settings.razorpayKeyId,
        )

    @app.post(
        endpointCheckoutVerify,
        summary="Verify Razorpay payment signature via HMAC-SHA256",
        status_code=status.HTTP_200_OK,
    )
    async def verifyCheckoutPayment(request: Request) -> JSONResponse:
        """Verifies payment signature using timing-safe hmac.compare_digest."""
        settings = getMandateEngineSettings()
        if not settings.hasRazorpayCredentials:
            raise HTTPException(
                status_code=status.HTTP_503_SERVICE_UNAVAILABLE,
                detail="Verification requires Razorpay test-mode credentials (RAZORPAY_KEY_SECRET)",
            )

        try:
            body = await request.json()
        except Exception:
            raise HTTPException(
                status_code=status.HTTP_400_BAD_REQUEST,
                detail="Invalid JSON payload in request body",
            )

        if not isinstance(body, dict):
            raise HTTPException(
                status_code=status.HTTP_400_BAD_REQUEST,
                detail="Payload must be a JSON object",
            )

        orderId = body.get("razorpayOrderId")
        paymentId = body.get("razorpayPaymentId")
        signature = body.get("razorpaySignature")

        if (
            not orderId
            or not paymentId
            or not signature
            or not isinstance(orderId, str)
            or not isinstance(paymentId, str)
            or not isinstance(signature, str)
        ):
            raise HTTPException(
                status_code=status.HTTP_400_BAD_REQUEST,
                detail="Missing required fields: razorpayOrderId, razorpayPaymentId, and razorpaySignature",
            )

        messageToSign = f"{orderId}|{paymentId}".encode("utf-8")
        expectedSignature = hmac.new(
            settings.razorpayKeySecret.encode("utf-8"),
            messageToSign,
            hashlib.sha256,
        ).hexdigest()

        if not hmac.compare_digest(expectedSignature, signature):
            return JSONResponse(
                status_code=status.HTTP_400_BAD_REQUEST,
                content={"verified": False, "detail": "Payment signature verification failed"},
            )

        return JSONResponse(
            status_code=status.HTTP_200_OK,
            content={"verified": True, "orderId": orderId, "paymentId": paymentId},
        )


__all__ = [
    "CheckoutOrderRequestSchema",
    "CheckoutOrderResponseSchema",
    "endpointCheckoutOrder",
    "endpointCheckoutVerify",
    "minOrderAmountPaise",
    "registerCheckoutRoutes",
]
