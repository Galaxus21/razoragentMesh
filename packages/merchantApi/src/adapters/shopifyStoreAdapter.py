from decimal import Decimal
import re
import time
from typing import Any, Optional

from ..constants.merchantConstants import (
    defaultGstRatePercent,
    defaultHsnCode,
    defaultOriginPincode,
)
from ..schemas.bulkIngestSchema import ShopifyWebhookPayload
from ..schemas.universalProductSchema import (
    ApparelFacet,
    FmcgFacet,
    JewelryFacet,
    PharmaFacet,
    ProductAttributes,
    ScheduledPromotionSchema,
    UniversalProductListing,
)
from .csvIngestionAdapter import normalizeInrToPaise

allergensTagPrefix: str = "allergens:"
allergenTagPrefix: str = "allergen:"
promoTagPrefix: str = "promo:"
defaultPromotionDurationSeconds: int = 86400 * 30  # 30 days
defaultNamedPromoDiscountBps: int = 1000  # 10%
maxPromotionBps: int = 10000
minPromotionBps: int = 0
bpsPerPercent: int = 100


def _extractShopifyPromotions(tags: Optional[str]) -> list[ScheduledPromotionSchema]:
    """Extracts scheduled promotions from Shopify product tag annotations."""
    if not tags or not tags.strip():
        return []
    promotions: list[ScheduledPromotionSchema] = []
    currentUnix = int(time.time())

    for part in tags.split(","):
        cleanPart = part.strip()
        if not cleanPart.lower().startswith(promoTagPrefix):
            continue

        promoContent = cleanPart[len(promoTagPrefix):].strip()
        segments = promoContent.split(":")

        if len(segments) >= 4:
            try:
                cId = segments[0].strip()
                rawBps = int(segments[1].strip())
                bps = min(maxPromotionBps, max(minPromotionBps, rawBps))
                starts = int(segments[2].strip())
                ends = int(segments[3].strip())
                if ends > starts:
                    promotions.append(
                        ScheduledPromotionSchema(
                            campaignId=cId,
                            name=cId,
                            startsAtUnix=starts,
                            endsAtUnix=ends,
                            discountBps=bps,
                        )
                    )
                    continue
            except Exception:
                pass

        try:
            tagName = segments[0].strip()
            if not tagName:
                continue
            match = re.search(r"(\d+)$", tagName)
            discountBps = int(match.group(1)) * bpsPerPercent if match else defaultNamedPromoDiscountBps
            clampedBps = min(maxPromotionBps, max(minPromotionBps, discountBps))
            promotions.append(
                ScheduledPromotionSchema(
                    campaignId=f"shopify-{tagName.lower()}",
                    name=tagName,
                    startsAtUnix=currentUnix,
                    endsAtUnix=currentUnix + defaultPromotionDurationSeconds,
                    discountBps=clampedBps,
                )
            )
        except Exception:
            pass

    return promotions


def _extractShopifyAllergens(tags: Optional[str]) -> list[str]:
    """Extracts allergen list from Shopify product tag annotations."""
    if not tags or not tags.strip():
        return []
    allergens: list[str] = []
    lowerTags = tags.lower()
    for prefix in (allergensTagPrefix, allergenTagPrefix):
        if prefix in lowerTags:
            startIdx = lowerTags.find(prefix) + len(prefix)
            sub = tags[startIdx:]
            for part in sub.replace(";", ",").split(","):
                cleanPart = part.strip()
                if ":" in cleanPart:
                    break
                if cleanPart and cleanPart.lower() not in ("organic", "energy", "vegan", "vegetarian", "nonveg"):
                    if cleanPart not in allergens:
                        allergens.append(cleanPart)
    return allergens


def _buildFacets(
    product: ShopifyWebhookPayload,
    variant: dict[str, Any],
    allergens: list[str],
) -> tuple[
    Optional[ApparelFacet],
    Optional[FmcgFacet],
    Optional[JewelryFacet],
    Optional[PharmaFacet],
    str,
]:
    """Constructs multi-industry domain facets and infers category for Shopify variant."""
    tagsLower = (product.tags or "").lower()
    size = variant.get("option1")
    color = variant.get("option2")

    category = "apparel"
    if "jewelry" in tagsLower or "gold" in tagsLower or "silver" in tagsLower:
        category = "jewelry"
    elif "pharma" in tagsLower or "medicine" in tagsLower or "drug" in tagsLower:
        category = "pharma"
    elif "fmcg" in tagsLower or "food" in tagsLower or "grocery" in tagsLower:
        category = "fmcg"

    apparel = None
    if category == "apparel" or size or color:
        fabric = []
        if "cotton" in tagsLower:
            fabric.append("cotton")
        if "polyester" in tagsLower:
            fabric.append("polyester")
        apparel = ApparelFacet(
            size=str(size).strip() if size else None,
            color=str(color).strip() if color else None,
            fabric=fabric,
        )

    fmcg = None
    if category == "fmcg" or allergens:
        fmcg = FmcgFacet(
            allergens=allergens,
            isVeg="nonveg" not in tagsLower,
        )

    jewelry = None
    if category == "jewelry":
        purity: Any = 22
        if "18k" in tagsLower or "18 karat" in tagsLower:
            purity = 18
        elif "24k" in tagsLower or "24 karat" in tagsLower:
            purity = 24
        grams = Decimal(str(variant.get("grams", 5000))) / Decimal("1000") if variant.get("grams") else Decimal("5.0")
        if grams <= 0:
            grams = Decimal("5.0")
        jewelry = JewelryFacet(
            purityCarat=purity,
            grossWeightGrams=grams,
        )

    pharma = None
    if category == "pharma":
        salt = "Paracetamol"
        for part in (product.tags or "").split(","):
            if part.strip().lower().startswith("salt:"):
                salt = part.strip().split(":", 1)[1].strip()
        pharma = PharmaFacet(
            activeSalt=salt,
            dosageMg=500,
            prescriptionRequired="prescription" in tagsLower or "rx" in tagsLower,
        )

    return apparel, fmcg, jewelry, pharma, category


def mapShopifyVariantToSku(
    product: ShopifyWebhookPayload,
    variant: dict[str, Any],
    merchantDid: str,
    defaultHsnCode: str = defaultHsnCode,
    defaultGstRate: int = defaultGstRatePercent,
    originPincode: str = defaultOriginPincode,
) -> UniversalProductListing:
    """Maps a single Shopify product variant to a UniversalProductListing."""
    variantId = str(variant.get("id", "default")).strip()
    skuId = f"SHOPIFY-{product.id}-{variantId}"
    pricePaise = normalizeInrToPaise(str(variant.get("price", "0")).strip())
    stock = int(variant.get("inventory_quantity") or 0)

    allergens = _extractShopifyAllergens(product.tags)
    apparelFacet, fmcgFacet, jewelryFacet, pharmaFacet, category = _buildFacets(product, variant, allergens)
    promotions = _extractShopifyPromotions(product.tags)

    return UniversalProductListing(
        skuId=skuId,
        merchantDid=merchantDid,
        title=product.title,
        description=product.body_html or product.title,
        category=category,
        hsnCode=defaultHsnCode,
        gstRatePercent=defaultGstRate,
        baseUnitPricePaise=pricePaise,
        availableStock=stock,
        originPincode=originPincode,
        promotions=promotions,
        apparelFacet=apparelFacet,
        fmcgFacet=fmcgFacet,
        jewelryFacet=jewelryFacet,
        pharmaFacet=pharmaFacet,
    )


def processShopifyWebhook(
    payload: ShopifyWebhookPayload,
    merchantDid: str,
) -> list[UniversalProductListing]:
    """Processes inbound Shopify webhook payload and produces list of product listings."""
    listings: list[UniversalProductListing] = []
    variants = payload.variants if isinstance(payload.variants, list) else []

    for variant in variants:
        if isinstance(variant, dict):
            listing = mapShopifyVariantToSku(payload, variant, merchantDid)
            listings.append(listing)

    return listings


__all__ = [
    "mapShopifyVariantToSku",
    "processShopifyWebhook",
]
