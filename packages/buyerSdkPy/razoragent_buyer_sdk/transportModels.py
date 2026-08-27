"""Pydantic v2 schemas for discovery quotes, PoW challenges, and settlements."""

from typing import Any, Optional
from pydantic import BaseModel, ConfigDict, Field

from .mandateModels import (
    CartMandate,
    ExecutionMandate,
    IntentMandate,
)


class QuoteTaxBreakdown(BaseModel):
    """Tax breakdown for SKU discovery quote payloads."""

    model_config = ConfigDict(frozen=True, extra="forbid")

    cgst_paise: int = Field(default=0, ge=0)
    sgst_paise: int = Field(default=0, ge=0)
    igst_paise: int = Field(default=0, ge=0)
    total_tax_paise: int = Field(default=0, ge=0)


class PoWChallenge(BaseModel):
    """Gateway HTTP 402 Proof of Work challenge."""

    model_config = ConfigDict(frozen=True, extra="forbid")

    statusCode: int = Field(default=402)
    wwwAuthenticate: str = Field(default="x402-INR")
    challengeToken: str = Field(min_length=1)
    tokenCostPaise: int = Field(default=50, ge=0)
    powDifficultyZeros: int = Field(default=4, ge=1)


Http402ChallengeResponse = PoWChallenge


class PoWSolution(BaseModel):
    """Proof of Work solution metrics and outcome."""

    model_config = ConfigDict(frozen=True, extra="forbid")

    nonce: int = Field(ge=0)
    computedDigest: str = Field(min_length=64, max_length=64)
    attemptsCount: int = Field(default=0, ge=0)
    elapsedTimeMs: float = Field(default=0.0, ge=0.0)
    isValid: bool = Field(default=True)


PowSolutionResult = PoWSolution


class AppliedDiscountItem(BaseModel):
    """Applied promotion or volume discount item."""

    model_config = ConfigDict(frozen=True, extra="forbid")

    type: str = Field(min_length=1)
    label: str = Field(min_length=1)
    discountBps: Optional[int] = Field(default=None, ge=0)
    discountPaise: Optional[int] = Field(default=None, ge=0)


class UpcomingPromotion(BaseModel):
    """Future scheduled promotion signaled in SKU quote."""

    model_config = ConfigDict(frozen=True, extra="forbid")

    campaign_id: str = Field(min_length=1)
    name: str = Field(min_length=1)
    starts_at_unix: int = Field(gt=0)
    ends_at_unix: int = Field(gt=0)
    expected_unit_price_paise: int = Field(ge=0)
    expected_savings_paise: int = Field(ge=0)
    limited_stock_allocated: Optional[int] = Field(default=None, ge=0)


class SkuQuoteRequest(BaseModel):
    """Request payload for fetching live product quote."""

    model_config = ConfigDict(frozen=True, extra="forbid")

    sku_id: str = Field(min_length=1)
    quantity: int = Field(default=1, gt=0)
    buyer_agent_id: str = Field(pattern=r"^did:agent:[0-9a-f]{64}$")
    delivery_pincode: str = Field(min_length=6, max_length=6)
    promo_code: Optional[str] = Field(default=None)


class SkuQuote(BaseModel):
    """Live product and price quote."""

    model_config = ConfigDict(frozen=True, extra="forbid")

    sku_id: str = Field(min_length=1)
    available_stock: int = Field(ge=0)
    base_unit_price_paise: int = Field(ge=0)
    offered_unit_price_paise: int = Field(ge=0)
    currency: str = Field(default="INR")
    hsn_code: str = Field(min_length=1)
    gst_rate_percent: int = Field(ge=0, le=28)
    tax_breakdown: QuoteTaxBreakdown
    quote_expiry_timestamp: int = Field(gt=0)
    quote_hash: str = Field(min_length=1)
    applied_discounts: list[AppliedDiscountItem] = Field(default_factory=list)
    total_savings_paise: int = Field(default=0, ge=0)
    upcoming_promotions: list[UpcomingPromotion] = Field(default_factory=list)


SkuQuoteResponse = SkuQuote


class InventoryLockRequest(BaseModel):
    """Request payload for reserving stock."""

    model_config = ConfigDict(frozen=True, extra="forbid")

    sku_id: str = Field(min_length=1)
    quantity: int = Field(gt=0)
    lock_ttl_seconds: int = Field(default=60, ge=10, le=300)
    buyer_agent_id: str = Field(pattern=r"^did:agent:[0-9a-f]{64}$")
    quote_hash: str = Field(min_length=1)


class InventoryLockResponse(BaseModel):
    """Confirmed stock reservation token."""

    model_config = ConfigDict(frozen=True, extra="forbid")

    lock_token: str = Field(min_length=1)
    fencing_token: int = Field(gt=0)
    sku_id: str = Field(min_length=1)
    quantity_locked: int = Field(gt=0)
    expires_at_unix_ms: int = Field(gt=0)
    signature: str = Field(min_length=1)


class RouteTransferResponse(BaseModel):
    """Razorpay Route transfer execution receipt."""

    model_config = ConfigDict(frozen=True, extra="forbid")

    id: str = Field(min_length=1)
    entity: str = Field(default="transfer")
    account: str = Field(min_length=1)
    amount: int = Field(gt=0)
    currency: str = Field(default="INR")
    status: str = Field(default="processed")
    createdAt: int = Field(gt=0)


TransferRecord = RouteTransferResponse


class GstrLineItem(BaseModel):
    """Itemized invoice line item compliant with GST Rule 46."""

    model_config = ConfigDict(frozen=True, extra="forbid")

    skuId: str = Field(min_length=1)
    hsnCode: str = Field(pattern=r"^[0-9]{4,8}$")
    quantity: int = Field(gt=0)
    unitPricePaise: int = Field(gt=0)
    taxableAmountPaise: int = Field(gt=0)
    gstRatePercent: int = Field(ge=0, le=28)
    cgstPaise: int = Field(ge=0)
    sgstPaise: int = Field(ge=0)
    igstPaise: int = Field(ge=0)
    totalLinePaise: int = Field(gt=0)


class GstrInvoicePayload(BaseModel):
    """GSTR-1 compliant invoice with cryptographic audit hash."""

    model_config = ConfigDict(frozen=True, extra="forbid")

    invoiceNumber: str = Field(min_length=1)
    invoiceDate: str = Field(min_length=1)
    sellerGstin: str = Field(min_length=15, max_length=15)
    merchantStateCode: str = Field(min_length=2, max_length=2)
    placeOfSupplyStateCode: str = Field(min_length=2, max_length=2)
    isIntraState: bool
    lineItems: list[GstrLineItem] = Field(min_length=1)
    taxableAmountPaise: int = Field(gt=0)
    totalCgstPaise: int = Field(ge=0)
    totalSgstPaise: int = Field(ge=0)
    totalIgstPaise: int = Field(ge=0)
    totalTaxPaise: int = Field(ge=0)
    totalTcsPaise: int = Field(ge=0)
    shippingPaise: int = Field(ge=0, default=0)
    discountPaise: int = Field(ge=0, default=0)
    grandTotalPaise: int = Field(gt=0)
    cryptographicAuditHash: str = Field(min_length=64, max_length=64)


class ExecuteSettlementRequestSchema(BaseModel):
    """Payload for executing 2PC settlement saga."""

    model_config = ConfigDict(frozen=True, extra="forbid")

    intentMandate: IntentMandate
    cartMandate: CartMandate
    executionMandate: ExecutionMandate
    merchantAccount: str = Field(min_length=1)
    paymentId: str = Field(min_length=1)
    serverTime: Optional[int] = Field(default=None)
    metadata: dict[str, Any] = Field(default_factory=dict)


SettlementRequest = ExecuteSettlementRequestSchema


class SettlementResult(BaseModel):
    """Result of completed settlement saga."""

    model_config = ConfigDict(frozen=True, extra="forbid")

    status: str = Field(default="captured")
    paymentId: str = Field(min_length=1)
    amountPaise: int = Field(gt=0)
    transfers: list[RouteTransferResponse] = Field(min_length=1)
    invoice: GstrInvoicePayload
    settledAt: int = Field(gt=0)


class PriceDropAlertRegisterRequest(BaseModel):
    """Request to register a price-drop alert subscription."""

    model_config = ConfigDict(frozen=True, extra="forbid")

    skuId: str = Field(min_length=1)
    targetPricePaise: int = Field(gt=0)
    callbackUrl: str = Field(min_length=1)
    buyerAgentId: str = Field(pattern=r"^did:agent:[0-9a-f]{64}$")
    expiresAtUnix: int = Field(gt=0)


class PriceDropAlertResponse(BaseModel):
    """Response returned upon alert registration."""

    model_config = ConfigDict(frozen=True, extra="forbid")

    alertId: str = Field(min_length=1)
    skuId: str = Field(min_length=1)
    targetPricePaise: int = Field(gt=0)
    status: str = Field(default="active")
    expiresAtUnix: int = Field(gt=0)


class PriceDropAlertCancelResponse(BaseModel):
    """Response returned upon cancelling an alert."""

    model_config = ConfigDict(frozen=True, extra="forbid")

    alertId: str = Field(min_length=1)
    status: str = Field(default="cancelled")


class EscrowSession(BaseModel):
    """Active micro-escrow session on Layer 2 Gateway."""

    model_config = ConfigDict(frozen=True, extra="forbid")

    sessionToken: str = Field(min_length=1)
    buyerAgentDid: str = Field(pattern=r"^did:agent:[0-9a-f]{64}$")
    balancePaise: int = Field(ge=0)
    expiresAtUnix: int = Field(gt=0)


class EscrowRefundReceipt(BaseModel):
    """Receipt for released escrow funds."""

    model_config = ConfigDict(frozen=True, extra="forbid")

    sessionToken: str = Field(min_length=1)
    refundAmountPaise: int = Field(ge=0)
    status: str = Field(default="refunded")


class MeshSlaConfig(BaseModel):
    """Configuration for buyer client SLAs and gateway connections."""

    model_config = ConfigDict(frozen=True, extra="forbid")

    gatewayBaseUrl: str = Field(default="http://127.0.0.1:8000")
    mcpBaseUrl: Optional[str] = Field(default="http://127.0.0.1:8001")
    merchantApiBaseUrl: Optional[str] = Field(default="http://127.0.0.1:8002")
    timeoutSeconds: float = Field(default=30.0, gt=0)
    maxRetries: int = Field(default=3, ge=0)
    autoSolvePow: bool = Field(default=True)
    defaultPowDifficulty: int = Field(default=4, ge=1)
    maxDeliveryHoursSla: int = Field(default=24, gt=0)
    minSavingsThresholdPaise: int = Field(default=1000, ge=0)


RazorAgentClientConfig = MeshSlaConfig
