"""Pydantic v2 AP2 Mandate schemas and cryptographic identity models."""

from typing import Literal
from pydantic import BaseModel, ConfigDict, Field


class AgentKeypair(BaseModel):
    """Cryptographic Ed25519 keypair and derived agent DID."""

    model_config = ConfigDict(frozen=True, extra="forbid")

    privateKeyHex: str = Field(min_length=64, max_length=64)
    publicKeyHex: str = Field(min_length=64, max_length=64)
    agentDid: str = Field(pattern=r"^did:agent:[0-9a-f]{64}$")


class CartItemSchema(BaseModel):
    """Line item within a cart mandate."""

    model_config = ConfigDict(frozen=True, extra="forbid")

    skuId: str = Field(min_length=1)
    quantity: int = Field(gt=0)
    unitPricePaise: int = Field(gt=0)
    hsnCode: str = Field(pattern=r"^[0-9]{4,8}$")
    gstRatePercent: int = Field(ge=0, le=28)
    lineTotalPaise: int = Field(gt=0)


class TaxBreakdownSchema(BaseModel):
    """GST tax calculation breakdown in integer paise."""

    model_config = ConfigDict(frozen=True, extra="forbid")

    cgstPaise: int = Field(ge=0)
    sgstPaise: int = Field(ge=0)
    igstPaise: int = Field(ge=0)
    totalTaxPaise: int = Field(ge=0)


class IntentMandate(BaseModel):
    """Principal spending authorization mandate (M_I)."""

    model_config = ConfigDict(frozen=True, extra="forbid")

    mandateId: str = Field(min_length=1)
    userDid: str = Field(pattern=r"^did:agent:[0-9a-f]{64}$")
    delegatedAgentDid: str = Field(pattern=r"^did:agent:[0-9a-f]{64}$")
    maxBudgetPaise: int = Field(gt=0)
    currency: Literal["INR"] = Field(default="INR")
    authorizedCategories: list[str] = Field(default_factory=list)
    validUntilTimestamp: int = Field(gt=0)
    upiCircleDelegationToken: str = Field(min_length=1)
    singleTransactionLimitPaise: int = Field(gt=0)
    nonce: str = Field(min_length=1)
    timestamp: int = Field(gt=0)
    userSignature: str = Field(min_length=128, max_length=128)


class CartMandate(BaseModel):
    """Merchant quote and inventory reservation mandate (M_C)."""

    model_config = ConfigDict(frozen=True, extra="forbid")

    cartId: str = Field(min_length=1)
    merchantDid: str = Field(pattern=r"^did:agent:[0-9a-f]{64}$")
    merchantGstin: str = Field(min_length=15, max_length=15)
    merchantStateCode: str = Field(min_length=2, max_length=2)
    buyerDeliveryPincode: str = Field(min_length=6, max_length=6)
    buyerDeliveryStateCode: str = Field(min_length=2, max_length=2)
    items: list[CartItemSchema] = Field(min_length=1)
    taxableSubtotalPaise: int = Field(gt=0)
    taxBreakdown: TaxBreakdownSchema
    shippingPaise: int = Field(ge=0, default=0)
    discountPaise: int = Field(ge=0, default=0)
    totalPaise: int = Field(gt=0)
    inventoryLockToken: str = Field(min_length=1)
    inventoryLockExpiresAt: int = Field(gt=0)
    nonce: str = Field(min_length=1)
    timestamp: int = Field(gt=0)
    merchantSignature: str = Field(min_length=128, max_length=128)


class ExecutionMandate(BaseModel):
    """Buyer agent execution commitment (M_E)."""

    model_config = ConfigDict(frozen=True, extra="forbid")

    executionId: str = Field(min_length=1)
    buyerAgentDid: str = Field(pattern=r"^did:agent:[0-9a-f]{64}$")
    intentMandateHash: str = Field(min_length=64, max_length=64)
    cartMandateHash: str = Field(min_length=64, max_length=64)
    settlementAmountPaise: int = Field(gt=0)
    currency: Literal["INR"] = Field(default="INR")
    upiCircleToken: str = Field(min_length=1)
    nonce: str = Field(min_length=1)
    timestamp: int = Field(gt=0)
    agentSignature: str = Field(min_length=128, max_length=128)


class AmendmentMandate(BaseModel):
    """Dual-signed amendment mandate (M_A) for dynamic cart modifications."""

    model_config = ConfigDict(frozen=True, extra="forbid")

    amendmentId: str = Field(min_length=1)
    previousCartMandateHash: str = Field(min_length=64, max_length=64)
    newCartMandateHash: str = Field(min_length=64, max_length=64)
    substitutedSkuMapping: dict[str, str] = Field(default_factory=dict)
    priceDeltaPaise: int
    amendmentReason: str = Field(min_length=1, max_length=200)
    nonce: str = Field(min_length=1)
    timestamp: int = Field(gt=0)
    agentSignature: str = Field(min_length=128, max_length=128)
    merchantSignature: str = Field(min_length=128, max_length=128)


__all__ = [
    "AgentKeypair",
    "AmendmentMandate",
    "CartItemSchema",
    "CartMandate",
    "ExecutionMandate",
    "IntentMandate",
    "TaxBreakdownSchema",
]
