"""Pydantic v2 schemas for sanitized merchant catalog quotes."""

from typing import Literal
from pydantic import BaseModel, ConfigDict, Field

from .sanitizerConstants import (
    defaultCurrency,
    hsnCodeRegexPattern,
    maxAllowedGstRate,
    maxDescriptionLength,
    maxTitleLength,
    minAllowedGstRate,
    minTitleLength,
    quoteHashLength,
    skuIdRegexPattern,
)



class TaxBreakdownSchema(BaseModel):
    """Immutable GST tax component breakdown in integer paise."""

    model_config = ConfigDict(frozen=True, extra="forbid")

    cgstPaise: int = Field(ge=0, description="Central GST in paise")
    sgstPaise: int = Field(ge=0, description="State GST in paise")
    igstPaise: int = Field(ge=0, description="Integrated GST in paise")
    totalTaxPaise: int = Field(ge=0, description="Total tax in paise")


class SanitizedSkuQuote(BaseModel):
    """Sanitized and validated merchant SKU quote model."""

    model_config = ConfigDict(frozen=True, extra="forbid")

    skuId: str = Field(
        pattern=skuIdRegexPattern,
        description="Standardized SKU identifier",
    )
    title: str = Field(
        min_length=minTitleLength,
        max_length=maxTitleLength,
        description="Sanitized product title",
    )
    description: str = Field(
        max_length=maxDescriptionLength,
        description="Sanitized description capped at 150 chars",
    )
    availableStock: int = Field(
        ge=0,
        description="Available inventory units",
    )
    baseUnitPricePaise: int = Field(
        gt=0,
        description="Base unit price in integer paise",
    )
    offeredUnitPricePaise: int = Field(
        gt=0,
        description="Offered unit price after tier discounts in integer paise",
    )
    currency: Literal[defaultCurrency] = Field(
        default=defaultCurrency,
        description=f"ISO currency code (strictly {defaultCurrency})",
    )
    hsnCode: str = Field(
        pattern=hsnCodeRegexPattern,
        description="Harmonized System of Nomenclature code",
    )
    gstRatePercent: int = Field(
        ge=minAllowedGstRate,
        le=maxAllowedGstRate,
        description="GST rate percentage",
    )
    taxBreakdown: TaxBreakdownSchema = Field(
        description="Itemized tax breakdown",
    )
    quoteExpiryTimestamp: int = Field(
        gt=0,
        description="Unix timestamp when quote expires",
    )
    quoteHash: str = Field(
        min_length=quoteHashLength,
        max_length=quoteHashLength,
        description="Hexadecimal SHA-256 or HMAC-SHA256 digest",
    )
