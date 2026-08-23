"""Shopify store webhook adapter translating Shopify product variants into UniversalProductListings."""

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
    ProductAttributes,
    UniversalProductListing,
)
from .csvIngestionAdapter import normalizeInrToPaise

allergensTagPrefix: str = "allergens:"
allergenTagPrefix: str = "allergen:"


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
    variant: dict[str, Any],
    allergens: list[str],
) -> tuple[Optional[ApparelFacet], Optional[FmcgFacet]]:
    """Constructs Apparel and FMCG domain facets for Shopify variant."""
    size = variant.get("option1")
    color = variant.get("option2")

    apparel = None
    if size:
        apparel = ApparelFacet(
            size=str(size).strip(),
            color=str(color).strip() if color else None,
        )

    fmcg = None
    if allergens:
        fmcg = FmcgFacet(allergens=allergens)

    return apparel, fmcg


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
    apparelFacet, fmcgFacet = _buildFacets(variant, allergens)

    return UniversalProductListing(
        skuId=skuId,
        merchantDid=merchantDid,
        title=product.title,
        description=product.body_html or product.title,
        category="apparel",
        hsnCode=defaultHsnCode,
        gstRatePercent=defaultGstRate,
        baseUnitPricePaise=pricePaise,
        availableStock=stock,
        originPincode=originPincode,
        apparelFacet=apparelFacet,
        fmcgFacet=fmcgFacet,
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
