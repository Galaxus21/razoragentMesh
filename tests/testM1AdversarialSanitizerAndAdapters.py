"""Adversarial stress-test suite for Catalog Sanitizer, CSV Ingestion, and Shopify Store Adapters."""

from decimal import Decimal
import pytest

from razoragentMesh.packages.catalogSanitizer import (
    InvalidSkuIdentifierException,
    SanitizedSkuQuote,
    SchemaSanitizationFailureException,
    cleanAndTruncateText,
    sanitizeMerchantSkuQuote,
    stripAnsiEscapes,
    stripMarkdownAndHtml,
    stripZeroWidthCharacters,
)
from razoragentMesh.packages.mandateEngine.settlement.settlementExceptions import (
    ArithmeticDriftException,
)
from razoragentMesh.packages.merchantApi.src.adapters.csvIngestionAdapter import (
    ingestCsvContent,
    parseCsvRow,
)
from razoragentMesh.packages.merchantApi.src.adapters.shopifyStoreAdapter import (
    _extractShopifyAllergens,
    _extractShopifyPromotions,
    _inferShopifyCategory,
    mapShopifyVariantToSku,
    processShopifyWebhook,
)
from razoragentMesh.packages.merchantApi.src.schemas.bulkIngestSchema import (
    ShopifyWebhookPayload,
)

testMerchantDid = "did:razoragent:merchant:adv001"


# ---------------------------------------------------------------------------
# Catalog Sanitizer Adversarial Tests
# ---------------------------------------------------------------------------


def testSanitizerRejectsBooleansInNumericFields() -> None:
    """Verifies that booleans are strictly rejected in all financial integer fields."""
    basePayload = {
        "skuId": "SKU-ADV-001",
        "title": "Test Title",
        "description": "Test Desc",
        "availableStock": 10,
        "baseUnitPricePaise": 10000,
        "offeredUnitPricePaise": 9500,
        "hsnCode": "84821010",
        "gstRatePercent": 18,
        "taxBreakdown": {"cgstPaise": 855, "sgstPaise": 855, "igstPaise": 0, "totalTaxPaise": 1710},
        "quoteExpiryTimestamp": 1780000000,
        "quoteHash": "a" * 64,
    }
    payloadWithBool = dict(basePayload, baseUnitPricePaise=True)
    with pytest.raises(SchemaSanitizationFailureException):
        sanitizeMerchantSkuQuote(payloadWithBool)

    payloadWithBoolStock = dict(basePayload, availableStock=False)
    with pytest.raises(SchemaSanitizationFailureException):
        sanitizeMerchantSkuQuote(payloadWithBoolStock)


def testSanitizerDetectsTaxBreakdownDrift() -> None:
    """Verifies that arithmetic drift between components and total tax is rejected."""
    driftPayload = {
        "skuId": "SKU-ADV-002",
        "title": "Drift Test",
        "description": "Drift Desc",
        "availableStock": 5,
        "baseUnitPricePaise": 10000,
        "offeredUnitPricePaise": 10000,
        "gstRatePercent": 18,
        "taxBreakdown": {
            "cgstPaise": 900,
            "sgstPaise": 900,
            "igstPaise": 0,
            "totalTaxPaise": 1801,  # 1801 != 900 + 900 + 0
        },
        "quoteExpiryTimestamp": 1780000000,
    }
    with pytest.raises(ArithmeticDriftException):
        sanitizeMerchantSkuQuote(driftPayload)


def testSanitizerUnicodeAndAnsiInjectionStripping() -> None:
    """Verifies stripping of adversarial unicode code points, ANSI escapes, and XSS markup."""
    adversarialText = "\u200b\u200c\x1b[31mExploit\x1b[0m <script>alert(1)</script> [Click Me](http://evil.com) \ufeff"
    cleaned = cleanAndTruncateText(adversarialText, maxLength=50)
    assert cleaned == "Exploit alert(1) Click Me"
    assert "\u200b" not in cleaned
    assert "\x1b" not in cleaned
    assert "<script>" not in cleaned
    assert "http://evil.com" not in cleaned


def testSanitizerLengthTruncationBoundary() -> None:
    """Verifies clean text truncation at exact character boundaries."""
    longText = "A" * 150
    assert len(cleanAndTruncateText(longText, maxLength=128)) == 128
    assert cleanAndTruncateText("", maxLength=100) == ""


# ---------------------------------------------------------------------------
# CSV Ingestion Adapter Adversarial Tests
# ---------------------------------------------------------------------------


def testCsvIngestionMalformedRowIsolation() -> None:
    """Verifies that missing sku, missing title, and invalid prices are safely isolated."""
    csvContent = (
        "skuId,title,basePriceInr,availableStock\n"
        "SKU-GOOD-1,Good Item 1,199.00,10\n"
        ",No Sku Item,299.00,5\n"
        "SKU-NO-TITLE,,399.00,5\n"
        "SKU-BAD-PRICE,Bad Price,NOT_A_PRICE,5\n"
        "SKU-NEG-PRICE,Negative Price,-49.00,5\n"
        "SKU-GOOD-2,Good Item 2,499.50,15\n"
    )
    listings, result = ingestCsvContent(csvContent, merchantDid=testMerchantDid)
    assert result.totalRowsProcessed == 6
    assert result.successCount == 2
    assert result.failureCount == 4
    assert len(listings) == 2
    assert listings[0].skuId == "SKU-GOOD-1"
    assert listings[0].baseUnitPricePaise == 19900
    assert listings[1].skuId == "SKU-GOOD-2"
    assert listings[1].baseUnitPricePaise == 49950


def testCsvApparelAndFmcgFacetParsing() -> None:
    """Verifies parsing of Apparel and FMCG facets from CSV dictionary."""
    apparelRow = {
        "skuId": "SKU-APP-01",
        "title": "Silk Saree",
        "basePriceInr": "4500.00",
        "size": "Free",
        "color": "Crimson",
        "fabric": "Silk, Zari",
    }
    apparelListing = parseCsvRow(apparelRow, merchantDid=testMerchantDid)
    assert apparelListing is not None and apparelListing.apparelFacet is not None
    assert apparelListing.apparelFacet.color == "Crimson"
    assert apparelListing.apparelFacet.fabric == ["Silk", "Zari"]

    fmcgRow = {
        "skuId": "SKU-FMCG-01",
        "title": "Almond Milk",
        "basePriceInr": "250.00",
        "allergens": "Nuts; Tree Nuts",
        "isVeg": "true",
        "fssaiNumber": "10020030040050",
    }
    fmcgListing = parseCsvRow(fmcgRow, merchantDid=testMerchantDid)
    assert fmcgListing is not None and fmcgListing.fmcgFacet is not None
    assert fmcgListing.fmcgFacet.allergens == ["Nuts", "Tree Nuts"]
    assert fmcgListing.fmcgFacet.isVeg is True


def testCsvJewelryAndPharmaFacetParsing() -> None:
    """Verifies parsing of Jewelry and Pharma facets from CSV dictionary."""
    jewelryRow = {
        "skuId": "SKU-JEW-01",
        "title": "22K Bangle",
        "basePriceInr": "75000.00",
        "carat": "22",
        "grossWeightGrams": "12.500",
        "hallmarkNumber": "BIS-22K-1234",
    }
    jewListing = parseCsvRow(jewelryRow, merchantDid=testMerchantDid)
    assert jewListing is not None and jewListing.jewelryFacet is not None
    assert jewListing.jewelryFacet.purityCarat == 22
    assert jewListing.jewelryFacet.grossWeightGrams == Decimal("12.500")

    pharmaRow = {
        "skuId": "SKU-PHARM-01",
        "title": "Amoxicillin 500mg",
        "basePriceInr": "120.00",
        "activeSalt": "Amoxicillin Trihydrate",
        "dosageMg": "500",
        "prescriptionRequired": "yes",
        "schedule": "Schedule H",
    }
    pharmaListing = parseCsvRow(pharmaRow, merchantDid=testMerchantDid)
    assert pharmaListing is not None and pharmaListing.pharmaFacet is not None
    assert pharmaListing.pharmaFacet.activeSalt == "Amoxicillin Trihydrate"
    assert pharmaListing.pharmaFacet.prescriptionRequired is True


def testCsvVolumeTiersAndEscapedJsonPromotions() -> None:
    """Verifies volume tiers parsing and escaped-quotes JSON promotions handling."""
    row = {
        "skuId": "SKU-TIER-01",
        "title": "Bulk Pen Pack",
        "basePriceInr": "50.00",
        "volumeTiersJson": '[{"minQuantity": 50, "discountBps": 1000}, {"minQuantity": 100, "discountBps": 2000}]',
        "promotionsJson": '[{\\"campaignId\\": \\"CAMP1\\", \\"discountBps\\": 500, \\"startsAtUnix\\": 100, \\"endsAtUnix\\": 200}]',
    }
    listing = parseCsvRow(row, merchantDid=testMerchantDid)
    assert listing is not None
    assert len(listing.volumeTiers) == 2
    assert listing.volumeTiers[0].minQuantity == 50
    assert listing.volumeTiers[0].discountBps == 1000
    assert len(listing.promotions) == 1
    assert listing.promotions[0].campaignId == "CAMP1"


# ---------------------------------------------------------------------------
# Shopify Store Adapter Adversarial Tests
# ---------------------------------------------------------------------------


def testShopifyAllergenExtractionWithExcludedWords() -> None:
    """Verifies allergen parser filters excluded words and terminates at subsequent tags."""
    tags = "organic, vegan, allergens:peanuts, soy, gluten, promo:SAVE20, color:blue"
    allergens = _extractShopifyAllergens(tags)
    assert "peanuts" in allergens
    assert "soy" in allergens
    assert "gluten" in allergens
    assert "organic" not in allergens
    assert "vegan" not in allergens
    assert "color:blue" not in allergens


def testShopifyCategoryInferenceHierarchy() -> None:
    """Verifies category inference for jewelry, pharma, fmcg, and default apparel."""
    assert _inferShopifyCategory("pure 22k gold necklace") == "jewelry"
    assert _inferShopifyCategory("prescription medicine for fever") == "pharma"
    assert _inferShopifyCategory("organic grocery food pack") == "fmcg"
    assert _inferShopifyCategory("denim casual jacket") == "apparel"


def testShopifyJewelryWeightAndCaratFallback() -> None:
    """Verifies 18K/24K tag purity parsing and grams division with fallback."""
    payload18k = ShopifyWebhookPayload(
        id=112233,
        title="18K Gold Earring",
        tags="jewelry, 18k",
        variants=[{"id": "var_18k", "price": "15000.00", "grams": 3500}],
    )
    listings = processShopifyWebhook(payload18k, merchantDid=testMerchantDid)
    assert len(listings) == 1
    jewFacet = listings[0].jewelryFacet
    assert jewFacet is not None
    assert jewFacet.purityCarat == 18
    assert jewFacet.grossWeightGrams == Decimal("3.5")

    payloadZeroGrams = ShopifyWebhookPayload(
        id=112234,
        title="24K Gold Coin",
        tags="jewelry, 24k",
        variants=[{"id": "var_zero", "price": "35000.00", "grams": 0}],
    )
    listingsZero = processShopifyWebhook(payloadZeroGrams, merchantDid=testMerchantDid)
    assert len(listingsZero) == 1
    assert listingsZero[0].jewelryFacet is not None
    assert listingsZero[0].jewelryFacet.purityCarat == 24
    assert listingsZero[0].jewelryFacet.grossWeightGrams == Decimal("5.0")
