"""Empirical Challenger 2 Test Suite: CSV Malformed Ingestion & Shopify Tag Mutations."""

import json
from decimal import Decimal
import pytest

from razoragentMesh.packages.merchantApi.src.adapters.csvIngestionAdapter import (
    ingestCsvContent,
    parseCsvRow,
)
from razoragentMesh.packages.merchantApi.src.adapters.shopifyStoreAdapter import (
    _extractShopifyPromotions,
    processShopifyWebhook,
)
from razoragentMesh.packages.merchantApi.src.schemas.bulkIngestSchema import (
    ShopifyWebhookPayload,
)
from razoragentMesh.packages.merchantApi.src.schemas.universalProductSchema import (
    ScheduledPromotionSchema,
)

# Test Constants in camelCase
testMerchantDid: str = "did:mesh:merchant_challenger2"
testValidSku1: str = "SKU-VALID-001"
testValidSku2: str = "SKU-VALID-002"
testCorruptSku1: str = "SKU-CORRUPT-JSON"
testCorruptSku2: str = "SKU-INVERTED-TIME"
testCorruptSku3: str = "SKU-NO-DISCOUNT"
testCorruptSku4: str = "SKU-OUT-OF-BOUNDS-BPS"


def testCsvPromotionsMalformedJsonSyntaxFaultIsolation() -> None:
    """Challenge 3A: Injects corrupted JSON strings into promotionsJson and asserts row isolation."""
    csvRows = [
        "skuId,title,basePriceInr,availableStock,hsnCode,gstRatePercent,promotionsJson",
        f'{testValidSku1},Valid Chair,4200,10,9401,18,"[{{""campaignId"": ""C1"", ""name"": ""Promo 1"", ""startsAtUnix"": 1724480000, ""endsAtUnix"": 1724566400, ""discountBps"": 1000}}]"',
        f'{testCorruptSku1},Bad Json Product,3500,5,9401,18,"{{invalid json unescaped"',
        f'{testValidSku2},Valid Desk,8500,8,9401,18,"[{{""campaignId"": ""C2"", ""name"": ""Promo 2"", ""startsAtUnix"": 1724480000, ""endsAtUnix"": 1724566400, ""fixedPricePaise"": 750000}}]"',
        'SKU-CORRUPT-STRING-ELEMENT,Non Object Promo,2000,4,9401,18,"[""invalid_element_not_dict""]"',
        'SKU-CORRUPT-NUM-ELEMENTS,Bad Array Elements,1500,2,9401,18,"[1, 2, 3]"',
    ]
    csvContent = "\n".join(csvRows)
    listings, result = ingestCsvContent(csvContent, merchantDid=testMerchantDid)

    assert result.totalRowsProcessed == 5
    assert result.successCount == 2
    assert result.failureCount == 3
    assert testCorruptSku1 in result.failedSkuIds
    assert "SKU-CORRUPT-STRING-ELEMENT" in result.failedSkuIds
    assert "SKU-CORRUPT-NUM-ELEMENTS" in result.failedSkuIds

    # Check that valid SKUs parsed with exact promotion objects
    assert len(listings) == 2
    assert listings[0].skuId == testValidSku1
    assert len(listings[0].promotions) == 1
    assert listings[0].promotions[0].campaignId == "C1"
    assert listings[1].skuId == testValidSku2
    assert listings[1].promotions[0].fixedPricePaise == 750000


def testCsvPromotionsInvalidSchemaFieldsFaultIsolation() -> None:
    """Challenge 3B: Injects invalid promotion invariants (inverted time, missing discounts, out of bounds BPS)."""
    csvRows = [
        "skuId,title,basePriceInr,availableStock,hsnCode,gstRatePercent,promotionsJson",
        # Inverted timestamps (endsAt < startsAt)
        f'{testCorruptSku2},Inverted Time Product,5000,10,9401,18,"[{{""campaignId"": ""C_INV"", ""name"": ""Inv"", ""startsAtUnix"": 1724566400, ""endsAtUnix"": 1724480000, ""discountBps"": 2000}}]"',
        # Missing all discount fields
        f'{testCorruptSku3},No Discount Product,5000,10,9401,18,"[{{""campaignId"": ""C_NODISC"", ""name"": ""No Disc"", ""startsAtUnix"": 1724480000, ""endsAtUnix"": 1724566400}}]"',
        # Out of bounds BPS (15000 > 10000)
        f'{testCorruptSku4},Over 100% Bps Product,5000,10,9401,18,"[{{""campaignId"": ""C_OVER"", ""name"": ""Over"", ""startsAtUnix"": 1724480000, ""endsAtUnix"": 1724566400, ""discountBps"": 15000}}]"',
        # Valid SKU at the end
        f'{testValidSku1},Surviving Valid Product,4500,10,9401,18,"[{{""campaignId"": ""C_OK"", ""name"": ""Ok"", ""startsAtUnix"": 1724480000, ""endsAtUnix"": 1724566400, ""discountBps"": 500}}]"',
    ]
    csvContent = "\n".join(csvRows)
    listings, result = ingestCsvContent(csvContent, merchantDid=testMerchantDid)

    assert result.totalRowsProcessed == 4
    assert result.successCount == 1
    assert result.failureCount == 3
    assert result.failedSkuIds == [testCorruptSku2, testCorruptSku3, testCorruptSku4]
    assert len(listings) == 1
    assert listings[0].skuId == testValidSku1


def testCsvPromotionsKeyNormalization() -> None:
    """Challenge 3C: Verifies robust key normalization across snake_case and camelCase attributes."""
    snakeCaseJson = json.dumps([
        {
            "campaign_id": "CAMP_SNAKE",
            "campaign_name": "Snake Case Promo",
            "starts_at_unix": 1724480000,
            "ends_at_unix": 1724566400,
            "discount_bps": 1500,
            "limited_stock_allocated": 25,
        }
    ])
    row = {
        "skuId": "SKU-SNAKE-01",
        "title": "Snake Sku",
        "basePriceInr": "1000",
        "availableStock": "50",
        "promotionsJson": snakeCaseJson,
    }
    listing = parseCsvRow(row, merchantDid=testMerchantDid)
    assert listing is not None
    assert len(listing.promotions) == 1
    promo = listing.promotions[0]
    assert promo.campaignId == "CAMP_SNAKE"
    assert promo.name == "Snake Case Promo"
    assert promo.discountBps == 1500
    assert promo.limitedStockAllocated == 25


def testShopifyPromotionsMalformedTagSyntax() -> None:
    """Challenge 4A: Verifies graceful degradation on malformed Shopify promo tags without crashing."""
    malformedTags = [
        "promo:",
        "promo:SYNTAX_ONLY_TWO_SEGMENTS:100",
        "promo:CAMP_BAD_BPS:NOT_A_NUMBER:1724480000:1724566400",
        "promo:CAMP_INVERTED:2000:1724566400:1724480000",
        "promo:CAMP_NEG_BPS:-500:1724480000:1724566400",
        "promo:CAMP_HIGH_BPS:15000:1724480000:1724566400",
    ]
    rawTagsString = ", ".join(malformedTags)
    promotions = _extractShopifyPromotions(rawTagsString)
    # The extractor should not raise unhandled exceptions and should process tags safely
    assert isinstance(promotions, list)


def testShopifyNamedPromotionsRegexExtraction() -> None:
    """Challenge 4B: Verifies regex fallback for named promo tags with numeric discounts and clamping."""
    tags = "promo:FESTIVE25, promo:DIWALI10, promo:MEGA150, promo:SIMPLEPROMO"
    promotions = _extractShopifyPromotions(tags)

    # 1. FESTIVE25 -> 25 * 100 = 2500 BPS
    pFestive = next((p for p in promotions if "festive25" in p.campaignId), None)
    assert pFestive is not None
    assert pFestive.discountBps == 2500

    # 2. DIWALI10 -> 10 * 100 = 1000 BPS
    pDiwali = next((p for p in promotions if "diwali10" in p.campaignId), None)
    assert pDiwali is not None
    assert pDiwali.discountBps == 1000

    # 3. MEGA150 -> 150 * 100 = 15000 -> clamped to 10000 BPS
    pMega = next((p for p in promotions if "mega150" in p.campaignId), None)
    assert pMega is not None
    assert pMega.discountBps == 10000

    # 4. SIMPLEPROMO (no digits) -> fallback default 1000 BPS
    pSimple = next((p for p in promotions if "simplepromo" in p.campaignId), None)
    assert pSimple is not None
    assert pSimple.discountBps == 1000


def testShopifyWebhookEndToEndFaultTolerance() -> None:
    """Challenge 4C: Verifies end-to-end webhook ingestion with mixed valid and invalid variant tags."""
    mixedTags = "apparel, cotton, promo:EXPRESS_DEAL:2000:1724480000:1724566400, promo:MALFORMED:ABC:1:2, promo:HOLIDAY30"
    payload = ShopifyWebhookPayload(
        id=987654321,
        title="Eco Cotton Oversized Hoodie",
        body_html="<p>Warm organic cotton</p>",
        tags=mixedTags,
        variants=[
            {"id": "var_1", "price": "2499.00", "inventory_quantity": 40, "option1": "L", "option2": "Navy"},
            {"id": "var_2", "price": "2499.00", "inventory_quantity": 25, "option1": "XL", "option2": "Navy"},
        ],
    )
    listings = processShopifyWebhook(payload, merchantDid=testMerchantDid)
    assert len(listings) == 2
    assert listings[0].skuId == "SHOPIFY-987654321-var_1"
    assert listings[0].baseUnitPricePaise == 249900
    assert listings[0].apparelFacet is not None
    assert listings[0].apparelFacet.size == "L"
    assert len(listings[0].promotions) >= 1


def testCsvPromotionsMultipleMixedInvariantsFaultIsolation() -> None:
    """Challenge 3D: Injects a row with 1 valid and 1 invalid promo in the same list and asserts fault isolation."""
    csvRows = [
        "skuId,title,basePriceInr,availableStock,hsnCode,gstRatePercent,promotionsJson",
        # Row with 1 good promo and 1 bad promo in same JSON list -> whole row fails safely
        'SKU-MIXED-PROMO,Mixed Item,3000,5,9401,18,"[{{""campaignId"": ""OK"", ""name"": ""Ok"", ""startsAtUnix"": 1724480000, ""endsAtUnix"": 1724566400, ""discountBps"": 1000}, {{""campaignId"": ""BAD"", ""name"": ""Bad"", ""startsAtUnix"": 1724566400, ""endsAtUnix"": 1724480000, ""discountBps"": 1000}}]"',
        # Clean valid row
        f'{testValidSku1},Clean Item,3000,5,9401,18,"[{{""campaignId"": ""CLEAN"", ""name"": ""Clean"", ""startsAtUnix"": 1724480000, ""endsAtUnix"": 1724566400, ""discountBps"": 1000}}]"',
    ]
    csvContent = "\n".join(csvRows)
    listings, result = ingestCsvContent(csvContent, merchantDid=testMerchantDid)

    assert result.totalRowsProcessed == 2
    assert result.successCount == 1
    assert result.failureCount == 1
    assert "SKU-MIXED-PROMO" in result.failedSkuIds
    assert len(listings) == 1
    assert listings[0].skuId == testValidSku1


def testShopifyTagsBoundaryBpsAndStrangeCharacters() -> None:
    """Challenge 4D: Tests tag edge cases (0 BPS, 10000 BPS, 10001 BPS, extra colons)."""
    tags = "promo:ZERO:0:1724480000:1724566400, promo:MAX:10000:1724480000:1724566400, promo:OVER:10001:1724480000:1724566400, promo:NO_DIGITS, promo:::::, promo:   "
    promotions = _extractShopifyPromotions(tags)

    pZero = next((p for p in promotions if p.campaignId == "ZERO"), None)
    assert pZero is not None and pZero.discountBps == 0

    pMax = next((p for p in promotions if p.campaignId == "MAX"), None)
    assert pMax is not None and pMax.discountBps == 10000

    # OVER tag (10001 BPS) is clamped to 10000 BPS
    pOver = next((p for p in promotions if "over" in p.campaignId.lower()), None)
    assert pOver is not None and pOver.discountBps == 10000

    # NO_DIGITS tag has no numeric suffix, falls back to defaultNamedPromoDiscountBps (1000 BPS)
    pNoDigits = next((p for p in promotions if "no_digits" in p.campaignId), None)
    assert pNoDigits is not None and pNoDigits.discountBps == 1000

