"""Pydantic v2 schema for CartMandate (M_C) signed by merchant."""

from pydantic import BaseModel, ConfigDict, Field


class CartItemSchema(BaseModel):
    """Line item within a cart mandate."""

    model_config = ConfigDict(frozen=True, extra="forbid")

    skuId: str = Field(min_length=1, description="Standard SKU identifier")
    quantity: int = Field(gt=0, description="Quantity ordered")
    unitPricePaise: int = Field(gt=0, description="Unit price in integer paise")
    hsnCode: str = Field(pattern=r"^[0-9]{4,8}$", description="HSN tax classification code")
    gstRatePercent: int = Field(ge=0, le=28, description="GST rate percentage")
    lineTotalPaise: int = Field(gt=0, description="Total line amount before tax in paise")


class TaxBreakdownSchema(BaseModel):
    """GST component breakdown in integer paise."""

    model_config = ConfigDict(frozen=True, extra="forbid")

    cgstPaise: int = Field(ge=0, description="Central GST in paise")
    sgstPaise: int = Field(ge=0, description="State GST in paise")
    igstPaise: int = Field(ge=0, description="Integrated GST in paise")
    totalTaxPaise: int = Field(ge=0, description="Total tax in paise")


class CartMandate(BaseModel):
    """Merchant-signed cart quote and inventory reservation."""

    model_config = ConfigDict(frozen=True, extra="forbid")

    cartId: str = Field(min_length=1, description="Unique cart identifier")
    merchantDid: str = Field(pattern=r"^did:agent:[0-9a-f]{64}$", description="DID of merchant")
    merchantGstin: str = Field(min_length=15, max_length=15, description="15-char GSTIN")
    merchantStateCode: str = Field(min_length=2, max_length=2, description="2-digit GST state code")
    buyerDeliveryPincode: str = Field(min_length=6, max_length=6, description="6-digit Indian PIN")
    buyerDeliveryStateCode: str = Field(min_length=2, max_length=2, description="2-digit delivery state code")
    items: list[CartItemSchema] = Field(min_length=1, description="List of cart line items")
    taxableSubtotalPaise: int = Field(gt=0, description="Taxable sum of items in paise")
    taxBreakdown: TaxBreakdownSchema = Field(description="Itemized tax calculations")
    shippingPaise: int = Field(ge=0, default=0, description="Shipping cost in paise")
    discountPaise: int = Field(ge=0, default=0, description="Promotional discount in paise")
    totalPaise: int = Field(gt=0, description="Gross total settlement amount in paise")
    inventoryLockToken: str = Field(min_length=1, description="Cryptographic lock token from MCP L1")
    inventoryLockExpiresAt: int = Field(gt=0, description="Unix timestamp of lock expiration")
    nonce: str = Field(min_length=1, description="Single-use cryptographic nonce")
    timestamp: int = Field(gt=0, description="Unix creation timestamp")
    merchantSignature: str = Field(min_length=128, max_length=128, description="Ed25519 signature by merchant")
