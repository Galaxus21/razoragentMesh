"""Unit test suite for CSV Ingestion Adapter volume tiers, promotions, and multi-domain facets."""

from decimal import Decimal
from typing import List
import pytest

from razoragentMesh.packages.merchantApi.src.adapters.csvIngestionAdapter import (
    ingestCsvContent,
    parseCsvRow,
)
from razoragentMesh.packages.merchantApi.src.schemas.universalProductSchema import (
    ScheduledPromotionSchema,
    UniversalProductListing,
    VolumeTier,
)

testMerchantDid: str = "did:razoragent:merchant:abcdef0123456789"
sampleVolumeTiersJson: str = '[{"minQuantity": 10, "discountBps": 500}, {"minQuantity": 50, "discountBps": 1500}]'
samplePromotionsJson: str = '[{"campaignId": "FLASH20", "name": "Flash 20% Off", "startsAtUnix": 1700000000, "endsAtUnix": 1700100000, "discountBps": 2000}]'


def testCsvIngestionAdapterVolumeTiersExtraction() -> None:
    """Verifies volume tiers JSON array parsing into VolumeTier model objects."""
    row = {
        "skuId": "SKU-TIER-01",
        "title": "Bulk Cotton Yarn",
        "basePriceInr": "150.00",
        "volumeTiersJson": sampleVolumeTiersJson,
    }
    listing = parseCsvRow(row, testMerchantDid)
    assert listing is not None
    assert len(listing.volumeTiers) == 2

    tier1: VolumeTier = listing.volumeTiers[0]
    assert tier1.minQuantity == 10
    assert tier1.discountBps == 500

    tier2: VolumeTier = listing.volumeTiers[1]
    assert tier2.minQuantity == 50
    assert tier2.discountBps == 1500


def testCsvIngestionAdapterScheduledPromotionsJson() -> None:
    """Verifies parsing of camelCase and snake_case promotional campaign JSON objects."""
    camelRow = {
        "skuId": "SKU-PROMO-CAMEL",
        "title": "Promo Bag",
        "basePriceInr": "500.00",
        "promotionsJson": samplePromotionsJson,
    }
    listingCamel = parseCsvRow(camelRow, testMerchantDid)
    assert listingCamel is not None and len(listingCamel.promotions) == 1
    promo1 = listingCamel.promotions[0]
    assert promo1.campaignId == "FLASH20"
    assert promo1.discountBps == 2000
    assert promo1.startsAtUnix == 1700000000
    assert promo1.endsAtUnix == 1700100000

    snakePromoJson = '[{"campaign_id": "FLAT100", "campaign_name": "Flat 100 Off", "starts_at_unix": 1700000000, "ends_at_unix": 1700050000, "discount_paise": 10000}]'
    snakeRow = {
        "skuId": "SKU-PROMO-SNAKE",
        "title": "Promo Shoes",
        "basePriceInr": "2000.00",
        "promotionsJson": snakePromoJson,
    }
    listingSnake = parseCsvRow(snakeRow, testMerchantDid)
    assert listingSnake is not None and len(listingSnake.promotions) == 1
    promo2 = listingSnake.promotions[0]
    assert promo2.campaignId == "FLAT100"
    assert promo2.discountPaise == 10000


def testCsvIngestionAdapterApparelFacetExtraction() -> None:
    """Verifies apparel size, color, and fabric attributes extraction."""
    apparelRow = {
        "skuId": "SKU-APP-01",
        "title": "Men Slim Denim",
        "basePriceInr": "1899.00",
        "size": "32",
        "color": "Dark Indigo",
        "fabric": "Cotton, Elastane",
    }
    listing = parseCsvRow(apparelRow, testMerchantDid)
    assert listing is not None and listing.apparelFacet is not None
    assert listing.apparelFacet.size == "32"
    assert listing.apparelFacet.color == "Dark Indigo"
    assert listing.apparelFacet.fabric == ["Cotton", "Elastane"]


def testCsvIngestionAdapterFmcgFacetExtraction() -> None:
    """Verifies FMCG allergens, vegetarian certification, and FSSAI number extraction."""
    fmcgRow = {
        "skuId": "SKU-FMCG-01",
        "title": "Granola Bar",
        "basePriceInr": "40.00",
        "allergens": "Oats; Peanuts; Soy",
        "isVeg": "true",
        "fssaiNumber": "10019022009876",
    }
    listing = parseCsvRow(fmcgRow, testMerchantDid)
    assert listing is not None and listing.fmcgFacet is not None
    assert listing.fmcgFacet.allergens == ["Oats", "Peanuts", "Soy"]
    assert listing.fmcgFacet.isVeg is True
    assert listing.fmcgFacet.fssaiNumber == "10019022009876"


def testCsvIngestionAdapterJewelryAndPharmaFacets() -> None:
    """Verifies jewelry carat/weight and pharmaceutical active salt/prescription extraction."""
    jewelryRow = {
        "skuId": "SKU-JEW-01",
        "title": "22K Gold Bangle",
        "basePriceInr": "60000.00",
        "carat": "22",
        "grossWeightGrams": "10.500",
        "hallmarkNumber": "BIS-22K-4567",
    }
    jewListing = parseCsvRow(jewelryRow, testMerchantDid)
    assert jewListing is not None and jewListing.jewelryFacet is not None
    assert jewListing.jewelryFacet.purityCarat == 22
    assert jewListing.jewelryFacet.grossWeightGrams == Decimal("10.500")
    assert jewListing.jewelryFacet.hallmarkNumber == "BIS-22K-4567"

    pharmaRow = {
        "skuId": "SKU-PHARM-01",
        "title": "Cetirizine 10mg",
        "basePriceInr": "45.00",
        "activeSalt": "Cetirizine Hydrochloride",
        "dosageMg": "10",
        "prescriptionRequired": "false",
        "schedule": "Schedule H",
    }
    pharmaListing = parseCsvRow(pharmaRow, testMerchantDid)
    assert pharmaListing is not None and pharmaListing.pharmaFacet is not None
    assert pharmaListing.pharmaFacet.activeSalt == "Cetirizine Hydrochloride"
    assert pharmaListing.pharmaFacet.dosageMg == 10
    assert pharmaListing.pharmaFacet.prescriptionRequired is False


def testCsvIngestionAdapterMalformedJsonFieldsGracefulHandling() -> None:
    """Verifies invalid JSON fields are isolated and escaped quotes are handled gracefully."""
    invalidTierRow = {
        "skuId": "SKU-BAD-TIER",
        "title": "Item With Corrupt Tier",
        "basePriceInr": "100.00",
        "volumeTiersJson": "NOT_A_VALID_JSON",
    }
    listingBadTier = parseCsvRow(invalidTierRow, testMerchantDid)
    assert listingBadTier is not None
    assert listingBadTier.volumeTiers == []

    escapedPromoRow = {
        "skuId": "SKU-ESCAPED-PROMO",
        "title": "Escaped Promo Item",
        "basePriceInr": "200.00",
        "promotionsJson": '[{\\"campaignId\\": \\"CAMP1\\", \\"discountBps\\": 500, \\"startsAtUnix\\": 100, \\"endsAtUnix\\": 200}]',
    }
    listingEscaped = parseCsvRow(escapedPromoRow, testMerchantDid)
    assert listingEscaped is not None and len(listingEscaped.promotions) == 1
    assert listingEscaped.promotions[0].campaignId == "CAMP1"
