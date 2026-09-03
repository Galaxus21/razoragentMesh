"""Universal product catalog schemas with multi-industry faceted extensions."""

from decimal import Decimal
from typing import Literal, Optional
from pydantic import BaseModel, ConfigDict, Field, model_validator

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
minPromotionStartsAtUnix: int = 0
minPromotionDurationSeconds: int = 1
minPromotionDiscountPaise: int = 0
minPromotionFixedPricePaise: int = 0
minPromotionLimitedStock: int = 0
minPromoCodeLength: int = 3
maxPromoCodeLength: int = 32
minCashbackPaise: int = 0
maxPromoCodesPerSku: int = 10


class ScheduledPromotionSchema(BaseModel):
    """Scheduled promotional flash sale campaign with temporal and discount bounds."""

    model_config = ConfigDict(frozen=True, extra="forbid")

    campaignId: str = Field(min_length=1)
    name: str = Field(min_length=1)
    startsAtUnix: int = Field(ge=minPromotionStartsAtUnix)
    endsAtUnix: int = Field(gt=minPromotionStartsAtUnix)
    discountBps: Optional[int] = Field(default=None, ge=minDiscountBps, le=maxDiscountBps)
    discountPaise: Optional[int] = Field(default=None, ge=minPromotionDiscountPaise)
    fixedPricePaise: Optional[int] = Field(default=None, ge=minPromotionFixedPricePaise)
    limitedStockAllocated: Optional[int] = Field(default=None, ge=minPromotionLimitedStock)

    @model_validator(mode="after")
    def validatePromotionInvariants(self) -> "ScheduledPromotionSchema":
        """Enforces temporal bounds and at least one discount/price definition."""
        if self.endsAtUnix <= self.startsAtUnix:
            raise ValueError(
                f"Invalid temporal window: endsAtUnix ({self.endsAtUnix}) must be strictly greater than startsAtUnix ({self.startsAtUnix})"
            )
        if (
            self.discountBps is None
            and self.discountPaise is None
            and self.fixedPricePaise is None
        ):
            raise ValueError(
                "At least one of discountBps, discountPaise, or fixedPricePaise must be specified."
            )
        return self


class MerchantCampaignOffer(BaseModel):
    """A standing percentage discount the merchant runs on this SKU, optionally capped."""

    model_config = ConfigDict(frozen=True, extra="forbid")

    label: Optional[str] = None
    discountBps: int = Field(ge=minDiscountBps, le=maxDiscountBps)
    # A cap is what stops a percentage campaign from being ruinous on a high-value SKU. None
    # means uncapped, which is a real choice; zero would mean "no discount at all" and is not the
    # same thing, so the two are kept distinct rather than collapsed into a sentinel.
    capPaise: Optional[int] = Field(default=None, ge=minPromotionDiscountPaise)


class MerchantPromoCodeOffer(BaseModel):
    """One promo code this merchant honours on this SKU."""

    model_config = ConfigDict(frozen=True, extra="forbid")

    code: str = Field(min_length=minPromoCodeLength, max_length=maxPromoCodeLength)
    discountBps: int = Field(ge=minDiscountBps, le=maxDiscountBps)
    label: Optional[str] = None


class MerchantAuthoredOffers(BaseModel):
    """The offers a merchant writes for one SKU, replacing the demo-wide hardcoded defaults.

    Until this existed, three of the four discount types a quote can apply were global constants
    in the MCP server (`festiveCampaignBps`, `upiCashbackPaise`, a single `corporatePromoCode`),
    identical for every SKU in the mesh and unwritable by any merchant. Only volume tiers and
    scheduled promotions were actually the merchant's.

    Presence is the statement. If this object is on a listing at all it describes that SKU's
    offers COMPLETELY, so an absent `campaign` means no campaign rather than "fall back to the
    demo default" -- otherwise a merchant would have no way to switch the festive discount off.
    """

    model_config = ConfigDict(frozen=True, extra="forbid")

    campaign: Optional[MerchantCampaignOffer] = None
    paymentRailCashbackPaise: Optional[int] = Field(default=None, ge=minCashbackPaise)
    promoCodes: list[MerchantPromoCodeOffer] = Field(
        default_factory=list, max_length=maxPromoCodesPerSku
    )

    @model_validator(mode="after")
    def validatePromoCodesAreDistinct(self) -> "MerchantAuthoredOffers":
        """Two rows with the same code make the second unreachable and the form look broken."""
        seen = [offer.code.strip().upper() for offer in self.promoCodes]
        if len(seen) != len(set(seen)):
            raise ValueError("Promo codes must be distinct; the same code was listed twice.")
        return self


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
    promotions: list[ScheduledPromotionSchema] = Field(default_factory=list)
    merchantOffers: Optional[MerchantAuthoredOffers] = None
    jewelryFacet: Optional[JewelryFacet] = None
    apparelFacet: Optional[ApparelFacet] = None
    pharmaFacet: Optional[PharmaFacet] = None
    fmcgFacet: Optional[FmcgFacet] = None


__all__ = [
    "ApparelFacet",
    "FmcgFacet",
    "MerchantAuthoredOffers",
    "MerchantCampaignOffer",
    "MerchantPromoCodeOffer",
    "JewelryFacet",
    "PharmaFacet",
    "ProductAttributes",
    "ScheduledPromotionSchema",
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
    "minPromotionDiscountPaise",
    "minPromotionDurationSeconds",
    "minPromotionFixedPricePaise",
    "minPromotionLimitedStock",
    "minPromotionStartsAtUnix",
    "minShelfLifeDays",
    "minVolumeQuantity",
]
