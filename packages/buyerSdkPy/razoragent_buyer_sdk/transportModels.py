"""Pydantic v2 schemas for discovery quotes, PoW challenges, and settlements."""

from typing import Any, Optional
from pydantic import BaseModel, ConfigDict, Field
from pydantic.alias_generators import to_camel

from .mandateModels import (
    CartMandate,
    ExecutionMandate,
    IntentMandate,
)


class QuoteTaxBreakdown(BaseModel):
    """Tax breakdown for SKU discovery quote payloads."""

    model_config = ConfigDict(
        frozen=True, extra="forbid", alias_generator=to_camel, populate_by_name=True
    )

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

    model_config = ConfigDict(
        frozen=True, extra="forbid", alias_generator=to_camel, populate_by_name=True
    )

    type: str = Field(min_length=1)
    # The HTTP face sends this as "name", alongside a "code" that echoes the type.
    label: str = Field(min_length=1, alias="name")
    code: Optional[str] = Field(default=None)
    discountBps: Optional[int] = Field(default=None, ge=0)
    discountPaise: Optional[int] = Field(default=None, ge=0)


class UpcomingPromotion(BaseModel):
    """Future scheduled promotion signaled in SKU quote."""

    model_config = ConfigDict(
        frozen=True, extra="forbid", alias_generator=to_camel, populate_by_name=True
    )

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

    model_config = ConfigDict(
        frozen=True, extra="forbid", alias_generator=to_camel, populate_by_name=True
    )

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
    # Present only on the HTTP face: the post-discount unit price under its SDK name, the
    # quantity the quote was priced for, and their product.
    final_unit_price_paise: Optional[int] = Field(default=None, ge=0)
    quantity: Optional[int] = Field(default=None, gt=0)
    taxable_subtotal_paise: Optional[int] = Field(default=None, ge=0)


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

    model_config = ConfigDict(
        frozen=True, extra="forbid", alias_generator=to_camel, populate_by_name=True
    )

    lock_token: str = Field(min_length=1)
    fencing_token: int = Field(gt=0)
    sku_id: str = Field(min_length=1)
    quantity_locked: int = Field(gt=0)
    expires_at_unix_ms: int = Field(gt=0)
    # The HTTP face renames this to lockSignature on the way out.
    signature: str = Field(min_length=1, alias="lockSignature")


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
    razorpayOrderId: Optional[str] = Field(default=None)


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
    """Active micro-escrow session, mirroring what POST /api/v1/mesh/escrow returns.

    Field-for-field with `x402Gateway/src/escrow/escrowSessionManager.EscrowSession`, because
    both models are extra="forbid" and this one parses that one's output. It previously declared
    `balancePaise` and `expiresAtUnix` alone, a shape the gateway has never emitted -- so every
    real response failed validation on six unexpected keys and one missing one. Nothing caught it:
    the only test of this path mocked the transport and fed back the invented shape.
    """

    model_config = ConfigDict(frozen=True, extra="forbid")

    sessionToken: str = Field(min_length=1)
    buyerAgentDid: str = Field(min_length=1)
    initialHoldPaise: int = Field(gt=0)
    remainingBalancePaise: int = Field(ge=0)
    debitedTotalPaise: int = Field(ge=0)
    totalTurnsDebited: int = Field(ge=0)
    createdAtUnix: int = Field(gt=0)
    expiresAtUnix: int = Field(gt=0)
    isReleased: bool = False


class EscrowRefundReceipt(BaseModel):
    """Receipt for released escrow funds, mirroring POST /api/v1/mesh/escrow/release.

    Same correction as EscrowSession above: `refundAmountPaise`/`status` were never the wire
    shape. The gateway reports the debited and refunded halves separately, which is what lets a
    caller check that they still sum to the original hold.
    """

    model_config = ConfigDict(frozen=True, extra="forbid")

    sessionToken: str = Field(min_length=1)
    totalDebitedPaise: int = Field(ge=0)
    refundedBalancePaise: int = Field(ge=0)
    timestamp: int = Field(gt=0)


class MeshSlaConfig(BaseModel):
    """Configuration for buyer client SLAs and gateway connections."""

    model_config = ConfigDict(frozen=True, extra="forbid")

    # Ports must match docker-compose.yml: mandate-engine 8000, mcp-server 4001,
    # merchant-api 4002, x402-gateway 4003. `packages/buyerSdkTs/src/sdkConstants.ts`
    # carries the same map for the TypeScript SDK; the two are asserted equal in tests.
    gatewayBaseUrl: str = Field(default="http://127.0.0.1:8000")
    mcpBaseUrl: Optional[str] = Field(default="http://127.0.0.1:4001")
    merchantApiBaseUrl: Optional[str] = Field(default="http://127.0.0.1:4002")
    x402GatewayBaseUrl: Optional[str] = Field(default="http://127.0.0.1:4003")
    timeoutSeconds: float = Field(default=30.0, gt=0)
    maxRetries: int = Field(default=3, ge=0)
    autoSolvePow: bool = Field(default=True)
    defaultPowDifficulty: int = Field(default=4, ge=1)
    maxDeliveryHoursSla: int = Field(default=24, gt=0)
    minSavingsThresholdPaise: int = Field(default=1000, ge=0)


RazorAgentClientConfig = MeshSlaConfig
