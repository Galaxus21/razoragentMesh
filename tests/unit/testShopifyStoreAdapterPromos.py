"""Unit test suite for Shopify Store Adapter promotions, allergen parsing, and domain facets."""

from decimal import Decimal
from typing import List
import pytest

from razoragentMesh.packages.merchantApi.src.adapters.shopifyStoreAdapter import (
    _extractShopifyAllergens,
    _extractShopifyPromotions,
    processShopifyWebhook,
)
from razoragentMesh.packages.merchantApi.src.schemas.bulkIngestSchema import (
    ShopifyWebhookPayload,
)
from razoragentMesh.packages.merchantApi.src.schemas.universalProductSchema import (
    UniversalProductListing,
)

testMerchantDid: str = "did:razoragent:merchant:abcdef0123456789"
sampleVariantPayload: List[dict] = [{"id": 555, "price": "4200.00", "inventory_quantity": 25}]
samplePromoTag1: str = "promo:FLASH30:3000:1700000000:1700100000"
samplePromoTag2: str = "promo:FESTIVE10"
sampleAllergenTags: str = "allergens:peanuts, dairy, organic, energy"


def testShopifyStoreAdapterParameterizedPromoTags() -> None:
    """Verifies parsing of structured 4-part promotional tags (campaign:bps:start:end)."""
    payload = ShopifyWebhookPayload(
        id=123456789,
        title="Promotional Office Chair",
        tags=f"{samplePromoTag1}, furniture",
        variants=sampleVariantPayload,
    )
    listings: List[UniversalProductListing] = processShopifyWebhook(payload, testMerchantDid)
    assert len(listings) == 1
    listing = listings[0]
    assert len(listing.promotions) == 1

    promo = listing.promotions[0]
    assert promo.campaignId == "FLASH30"
    assert promo.name == "FLASH30"
    assert promo.discountBps == 3000
    assert promo.startsAtUnix == 1700000000
    assert promo.endsAtUnix == 1700100000


def testShopifyStoreAdapterNamedPromoTags() -> None:
    """Verifies parsing and resolution of named promo tags into discount basis points."""
    tagsString = "promo:FESTIVE10, promo:SUPER25, promo:WELCOME"
    payload = ShopifyWebhookPayload(
        id=234567890,
        title="Festive Gift Box",
        tags=tagsString,
        variants=sampleVariantPayload,
    )
    listings = processShopifyWebhook(payload, testMerchantDid)
    assert len(listings) == 1
    promos = listings[0].promotions
    assert len(promos) == 3

    assert promos[0].campaignId == "shopify-festive10"
    assert promos[0].discountBps == 1000
    assert promos[1].campaignId == "shopify-super25"
    assert promos[1].discountBps == 2500
    assert promos[2].campaignId == "shopify-welcome"
    assert promos[2].discountBps == 1000  # Fallback default 10%


def testShopifyStoreAdapterAllergenTagExtraction() -> None:
    """Verifies allergen parser extracts allergens and ignores excluded dietary words."""
    rawTags = "organic, vegan, allergens:peanuts, soy, gluten, promo:SAVE20, color:blue"
    allergens = _extractShopifyAllergens(rawTags)
    assert "peanuts" in allergens
    assert "soy" in allergens
    assert "gluten" in allergens
    assert "organic" not in allergens
    assert "vegan" not in allergens

    payload = ShopifyWebhookPayload(
        id=345678901,
        title="Almond Energy Bar",
        tags="fmcg, allergen:almonds; cashew, nonveg",
        variants=[{"id": 1, "price": "50.00", "inventory_quantity": 100}],
    )
    listings = processShopifyWebhook(payload, testMerchantDid)
    assert len(listings) == 1
    assert listings[0].fmcgFacet is not None
    assert "almonds" in listings[0].fmcgFacet.allergens
    assert "cashew" in listings[0].fmcgFacet.allergens
    assert listings[0].fmcgFacet.isVeg is False


def testShopifyStoreAdapterVerticalDomainTags() -> None:
    """Verifies multi-industry facet extraction for apparel, jewelry, and pharma."""
    apparelPayload = ShopifyWebhookPayload(
        id=401,
        title="Cotton Denim Shirt",
        tags="apparel, cotton, polyester",
        variants=[{"id": 11, "price": "1499.00", "option1": "L", "option2": "Navy"}],
    )
    appListing = processShopifyWebhook(apparelPayload, testMerchantDid)[0]
    assert appListing.apparelFacet is not None
    assert appListing.apparelFacet.size == "L"
    assert appListing.apparelFacet.color == "Navy"
    assert "cotton" in appListing.apparelFacet.fabric

    jewelryPayload = ShopifyWebhookPayload(
        id=402,
        title="24K Gold Ring",
        tags="jewelry, 24k",
        variants=[{"id": 12, "price": "45000.00", "grams": 8200}],
    )
    jewListing = processShopifyWebhook(jewelryPayload, testMerchantDid)[0]
    assert jewListing.jewelryFacet is not None
    assert jewListing.jewelryFacet.purityCarat == 24
    assert jewListing.jewelryFacet.grossWeightGrams == Decimal("8.2")

    pharmaPayload = ShopifyWebhookPayload(
        id=403,
        title="Paracetamol 500",
        tags="pharma, medicine, salt:Paracetamol, prescription",
        variants=[{"id": 13, "price": "30.00"}],
    )
    pharmListing = processShopifyWebhook(pharmaPayload, testMerchantDid)[0]
    assert pharmListing.pharmaFacet is not None
    assert pharmListing.pharmaFacet.activeSalt == "Paracetamol"
    assert pharmListing.pharmaFacet.prescriptionRequired is True


def testShopifyStoreAdapterInvalidPromoTagResilience() -> None:
    """Verifies malformed promo tags are safely ignored without crashing ingestion."""
    corruptedTags = "promo:, promo:BAD:NOT_A_NUM:100:200, promo:INVERTED:1000:500:200, valid:tag"
    payload = ShopifyWebhookPayload(
        id=501,
        title="Resilient Product",
        tags=corruptedTags,
        variants=sampleVariantPayload,
    )
    listings = processShopifyWebhook(payload, testMerchantDid)
    assert len(listings) == 1
    # Invalid structured tags should not crash or produce invalid ranges
    for promo in listings[0].promotions:
        assert promo.endsAtUnix > promo.startsAtUnix
