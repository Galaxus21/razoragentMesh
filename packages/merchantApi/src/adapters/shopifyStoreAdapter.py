from decimal import Decimal
import re
import time
from typing import Any, Optional

from ..constants.merchantConstants import (
    defaultGstRatePercent,
    defaultHsnCode,
    defaultOriginPincode,
    defaultVerticalApparel,
    defaultVerticalFmcg,
    defaultVerticalJewelry,
    defaultVerticalPharma,
)
from ..schemas.bulkIngestSchema import ShopifyWebhookPayload
from ..catalog.ingressSanitizer import sanitizeListingText
from ..schemas.universalProductSchema import (
    ApparelFacet,
    FmcgFacet,
    JewelryFacet,
    PharmaFacet,
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
excludedAllergenWords: frozenset[str] = frozenset({"organic", "energy", "vegan", "vegetarian", "nonveg"})


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

    # Shopify's body_html is raw merchant HTML and reached the catalog with no scrub at all --
    # not even the .strip() the CSV path applied. sanitizeListingText strips the markup, the
    # hidden characters and the ANSI escapes, and normalizes to NFC.
    return sanitizeListingText(UniversalProductListing(
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
    ))


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
        structuredPromo = _parseStructuredPromoTag(segments)
        if structuredPromo is not None:
            promotions.append(structuredPromo)
            continue
        namedPromo = _parseNamedPromoTag(segments[0] if segments else "", currentUnix)
        if namedPromo is not None:
            promotions.append(namedPromo)

    return promotions


def _parseStructuredPromoTag(segments: list[str]) -> Optional[ScheduledPromotionSchema]:
    """Parses a structured 4-part promo tag (campaign:bps:start:end)."""
    if len(segments) < 4:
        return None
    try:
        cId = segments[0].strip()
        rawBps = int(segments[1].strip())
        bps = min(maxPromotionBps, max(minPromotionBps, rawBps))
        starts = int(segments[2].strip())
        ends = int(segments[3].strip())
        if ends > starts:
            return ScheduledPromotionSchema(
                campaignId=cId,
                name=cId,
                startsAtUnix=starts,
                endsAtUnix=ends,
                discountBps=bps,
            )
    except Exception:
        pass
    return None


def _parseNamedPromoTag(tagName: str, currentUnix: int) -> Optional[ScheduledPromotionSchema]:
    """Parses a named promo tag with regex-extracted discount bps or default fallback."""
    try:
        cleanTag = tagName.strip()
        if not cleanTag:
            return None
        match = re.search(r"(\d+)$", cleanTag)
        discountBps = int(match.group(1)) * bpsPerPercent if match else defaultNamedPromoDiscountBps
        clampedBps = min(maxPromotionBps, max(minPromotionBps, discountBps))
        return ScheduledPromotionSchema(
            campaignId=f"shopify-{cleanTag.lower()}",
            name=cleanTag,
            startsAtUnix=currentUnix,
            endsAtUnix=currentUnix + defaultPromotionDurationSeconds,
            discountBps=clampedBps,
        )
    except Exception:
        return None


def _parseAllergenPrefixSection(tags: str, lowerTags: str, prefix: str) -> list[str]:
    """Parses comma/semicolon-separated allergen tokens from a tag prefix section."""
    if prefix not in lowerTags:
        return []
    startIdx = lowerTags.find(prefix) + len(prefix)
    sub = tags[startIdx:]
    extracted: list[str] = []
    for part in sub.replace(";", ",").split(","):
        cleanPart = part.strip()
        if ":" in cleanPart:
            break
        if not cleanPart or cleanPart.lower() in excludedAllergenWords:
            continue
        extracted.append(cleanPart)
    return extracted


def _extractShopifyAllergens(tags: Optional[str]) -> list[str]:
    """Extracts allergen list from Shopify product tag annotations."""
    if not tags or not tags.strip():
        return []
    allergens: list[str] = []
    lowerTags = tags.lower()
    for prefix in (allergensTagPrefix, allergenTagPrefix):
        for item in _parseAllergenPrefixSection(tags, lowerTags, prefix):
            if item not in allergens:
                allergens.append(item)
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
    category = _inferShopifyCategory(tagsLower)
    apparel = _buildShopifyApparelFacet(category, tagsLower, variant)
    fmcg = (
        FmcgFacet(allergens=allergens, isVeg="nonveg" not in tagsLower)
        if (category == defaultVerticalFmcg or allergens)
        else None
    )
    jewelry = _buildShopifyJewelryFacet(category, tagsLower, variant)
    pharma = _buildShopifyPharmaFacet(category, tagsLower, product.tags)
    return apparel, fmcg, jewelry, pharma, category


def _inferShopifyCategory(tagsLower: str) -> str:
    """Infers product category from Shopify lowercase tags string."""
    if any(k in tagsLower for k in ("jewelry", "gold", "silver")):
        return defaultVerticalJewelry
    if any(k in tagsLower for k in ("pharma", "medicine", "drug")):
        return defaultVerticalPharma
    if any(k in tagsLower for k in ("fmcg", "food", "grocery")):
        return defaultVerticalFmcg
    return defaultVerticalApparel


def _buildShopifyApparelFacet(
    category: str,
    tagsLower: str,
    variant: dict[str, Any],
) -> Optional[ApparelFacet]:
    """Constructs ApparelFacet from variant options and product tags."""
    size = variant.get("option1")
    color = variant.get("option2")
    if category != defaultVerticalApparel and not (size or color):
        return None
    fabric: list[str] = []
    if "cotton" in tagsLower:
        fabric.append("cotton")
    if "polyester" in tagsLower:
        fabric.append("polyester")
    return ApparelFacet(
        size=str(size).strip() if size else None,
        color=str(color).strip() if color else None,
        fabric=fabric,
    )


def _buildShopifyJewelryFacet(
    category: str,
    tagsLower: str,
    variant: dict[str, Any],
) -> Optional[JewelryFacet]:
    """Constructs JewelryFacet for jewelry category variants."""
    if category != defaultVerticalJewelry:
        return None
    purity: Any = 22
    if "18k" in tagsLower or "18 karat" in tagsLower:
        purity = 18
    elif "24k" in tagsLower or "24 karat" in tagsLower:
        purity = 24
    rawGrams = variant.get("grams", 5000)
    grams = (Decimal(str(rawGrams)) / Decimal("1000")) if rawGrams else Decimal("5.0")
    if grams <= Decimal("0"):
        grams = Decimal("5.0")
    return JewelryFacet(purityCarat=purity, grossWeightGrams=grams)


def _buildShopifyPharmaFacet(
    category: str,
    tagsLower: str,
    rawTags: Optional[str],
) -> Optional[PharmaFacet]:
    """Constructs PharmaFacet for pharmaceutical category products."""
    if category != defaultVerticalPharma:
        return None
    salt = "Paracetamol"
    for part in (rawTags or "").split(","):
        clean = part.strip()
        if clean.lower().startswith("salt:"):
            salt = clean.split(":", 1)[1].strip()
    return PharmaFacet(
        activeSalt=salt,
        dosageMg=500,
        prescriptionRequired="prescription" in tagsLower or "rx" in tagsLower,
    )


__all__ = [
    "mapShopifyVariantToSku",
    "processShopifyWebhook",
]
