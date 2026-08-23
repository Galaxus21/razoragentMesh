"""Universal product catalog schemas with multi-industry faceted extensions."""

from decimal import Decimal
from typing import Literal, Optional
from pydantic import BaseModel, ConfigDict, Field

from ..constants.merchantConstants import (
    hsnCodeMaxLength,
    hsnCodeMinLength,
    maxSkuDescriptionLength,
    maxSkuTitleLength,
)
from .dynamicPricingSchema import DynamicPricingRule

# Domain Boundary Constants
minVolumeQuantity: int = 1
minDiscountBps: int = 0
maxDiscountBps: int = 10000
minGrossWeightGrams: Decimal = Decimal("0.01")
minDosageMg: int = 0
minShelfLifeDays: int = 1
minGstRatePercent: int = 0
maxGstRatePercent: int = 28
minBaseUnitPricePaise: int = 0
minAvailableStock: int = 0
defaultMinimumOrderQuantity: int = 1
minOrderQuantityLimit: int = 1
defaultCurrencyInr: Literal["INR"] = "INR"


class VolumeTier(BaseModel):
    """Volume-based tier discount in basis points."""

    model_config = ConfigDict(frozen=True, extra="forbid")

    minQuantity: int = Field(ge=minVolumeQuantity)
    discountBps: int = Field(ge=minDiscountBps, le=maxDiscountBps)


class JewelryFacet(BaseModel):
    """Precious jewelry metadata and dynamic bullion pricing attachment."""

    model_config = ConfigDict(frozen=True, extra="forbid")

    purityCarat: Literal[18, 22, 24]
    grossWeightGrams: Decimal = Field(ge=minGrossWeightGrams)
    hallmarkNumber: Optional[str] = None
    dynamicPricingRule: Optional[DynamicPricingRule] = None


class ApparelFacet(BaseModel):
    """Apparel, fashion, and footwear size/color/fabric metadata."""

    model_config = ConfigDict(frozen=True, extra="forbid")

    size: Optional[str] = None
    color: Optional[str] = None
    fabric: list[str] = Field(default_factory=list)
    fitType: Optional[str] = None
    gender: Optional[Literal["M", "F", "UNISEX"]] = None


class PharmaFacet(BaseModel):
    """Pharmaceutical active ingredient and prescription regulatory metadata."""

    model_config = ConfigDict(frozen=True, extra="forbid")

    activeSalt: str
    dosageMg: int = Field(ge=minDosageMg)
    schedule: Optional[str] = None
    prescriptionRequired: bool = False


class FmcgFacet(BaseModel):
    """Fast-moving consumer goods food safety and allergen metadata."""

    model_config = ConfigDict(frozen=True, extra="forbid")

    allergens: list[str] = Field(default_factory=list)
    shelfLifeDays: Optional[int] = Field(default=None, ge=minShelfLifeDays)
    isVeg: bool = True
    fssaiNumber: Optional[str] = None


class ProductAttributes(BaseModel):
    """Unified container for multi-industry product attributes and facets."""

    model_config = ConfigDict(frozen=True, extra="forbid")

    allergens: list[str] = Field(default_factory=list)
    apparel: Optional[ApparelFacet] = None
    fmcg: Optional[FmcgFacet] = None
    jewelry: Optional[JewelryFacet] = None
    pharma: Optional[PharmaFacet] = None


class UniversalProductListing(BaseModel):
    """Universal product listing across all commercial verticals in RazorAgent Mesh."""

    model_config = ConfigDict(frozen=True, extra="forbid")

    skuId: str
    merchantDid: str
    title: str = Field(max_length=maxSkuTitleLength)
    description: str = Field(max_length=maxSkuDescriptionLength)
    category: str
    hsnCode: str = Field(min_length=hsnCodeMinLength, max_length=hsnCodeMaxLength)
    gstRatePercent: int = Field(ge=minGstRatePercent, le=maxGstRatePercent)
    baseUnitPricePaise: int = Field(ge=minBaseUnitPricePaise)
    availableStock: int = Field(ge=minAvailableStock)
    originPincode: str
    currency: Literal["INR"] = defaultCurrencyInr
    volumeTiers: list[VolumeTier] = Field(default_factory=list)
    minimumOrderQuantity: int = Field(
        default=defaultMinimumOrderQuantity,
        ge=minOrderQuantityLimit,
    )
    jewelryFacet: Optional[JewelryFacet] = None
    apparelFacet: Optional[ApparelFacet] = None
    pharmaFacet: Optional[PharmaFacet] = None
    fmcgFacet: Optional[FmcgFacet] = None


__all__ = [
    "ApparelFacet",
    "FmcgFacet",
    "JewelryFacet",
    "PharmaFacet",
    "ProductAttributes",
    "UniversalProductListing",
    "VolumeTier",
    "defaultCurrencyInr",
    "defaultMinimumOrderQuantity",
    "maxDiscountBps",
    "maxGstRatePercent",
    "minAvailableStock",
    "minBaseUnitPricePaise",
    "minDiscountBps",
    "minDosageMg",
    "minGrossWeightGrams",
    "minGstRatePercent",
    "minOrderQuantityLimit",
    "minShelfLifeDays",
    "minVolumeQuantity",
]
