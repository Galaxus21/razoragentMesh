"""Unit test suite for core Shopify Store Adapter webhook processing and variant extraction."""

from typing import Any, Dict, List
import pytest

from razoragentMesh.packages.merchantApi.src.adapters.shopifyStoreAdapter import (
    mapShopifyVariantToSku,
    processShopifyWebhook,
)
from razoragentMesh.packages.merchantApi.src.schemas.bulkIngestSchema import (
    ShopifyWebhookPayload,
)
from razoragentMesh.packages.merchantApi.src.schemas.universalProductSchema import (
    UniversalProductListing,
)

testMerchantDid: str = "did:razoragent:merchant:abcdef0123456789"
defaultHsnCodeValue: str = "6109"
defaultGstRateValue: int = 18
defaultOriginPincodeValue: str = "400001"
sampleProductId: int = 987654321
sampleVariantId: int = 111
samplePriceString: str = "120.00"
sampleStockQuantity: int = 50
sampleProductTitle: str = "Organic Protein Bar"
sampleProductHtml: str = "<p>Delicious nutritious bar</p>"


def testShopifyStoreAdapterBasicProductMapping() -> None:
    """Verifies single product and variant mapping to UniversalProductListing."""
    payload = ShopifyWebhookPayload(
        id=sampleProductId,
        title=sampleProductTitle,
        body_html=sampleProductHtml,
        variants=[
            {
                "id": sampleVariantId,
                "price": samplePriceString,
                "inventory_quantity": sampleStockQuantity,
                "option1": "Large",
                "option2": "Chocolate",
            }
        ],
    )
    listings: List[UniversalProductListing] = processShopifyWebhook(payload, testMerchantDid)
    assert len(listings) == 1

    firstListing = listings[0]
    expectedSku = f"SHOPIFY-{sampleProductId}-{sampleVariantId}"
    assert firstListing.skuId == expectedSku
    assert firstListing.merchantDid == testMerchantDid
    assert firstListing.title == sampleProductTitle
    assert firstListing.description == sampleProductHtml
    assert firstListing.baseUnitPricePaise == 12000
    assert firstListing.availableStock == sampleStockQuantity
    assert firstListing.hsnCode == defaultHsnCodeValue
    assert firstListing.gstRatePercent == defaultGstRateValue
    assert firstListing.originPincode == defaultOriginPincodeValue


def testShopifyStoreAdapterMultiVariantExtraction() -> None:
    """Verifies multi-variant products produce distinct SKU listings with individual prices."""
    variantsList: List[Dict[str, Any]] = [
        {"id": 101, "price": "499.00", "inventory_quantity": 20, "option1": "S"},
        {"id": 102, "price": "599.00", "inventory_quantity": 30, "option1": "M"},
        {"id": 103, "price": "699.00", "inventory_quantity": 15, "option1": "L"},
    ]
    payload = ShopifyWebhookPayload(
        id=555000,
        title="Premium Crewneck Sweatshirt",
        body_html="<p>Warm fleece sweatshirt</p>",
        variants=variantsList,
    )
    listings = processShopifyWebhook(payload, testMerchantDid)
    assert len(listings) == 3

    expectedPrices = [49900, 59900, 69900]
    expectedStocks = [20, 30, 15]
    expectedVariantIds = ["101", "102", "103"]

    for idx, listing in enumerate(listings):
        assert listing.skuId == f"SHOPIFY-555000-{expectedVariantIds[idx]}"
        assert listing.baseUnitPricePaise == expectedPrices[idx]
        assert listing.availableStock == expectedStocks[idx]
        assert listing.merchantDid == testMerchantDid


def testShopifyStoreAdapterPriceNormalization() -> None:
    """Verifies decimal string prices convert to integer paise without float drift (INV-01)."""
    testCases: List[tuple[str, int]] = [
        ("149.99", 14999),
        ("0.50", 50),
        ("1200.00", 120000),
        ("99", 9900),
        ("0.01", 1),
    ]
    for rawPrice, expectedPaise in testCases:
        payload = ShopifyWebhookPayload(
            id=777,
            title="Price Test Product",
            variants=[{"id": 1, "price": rawPrice, "inventory_quantity": 10}],
        )
        listings = processShopifyWebhook(payload, testMerchantDid)
        assert len(listings) == 1
        assert listings[0].baseUnitPricePaise == expectedPaise


def testShopifyStoreAdapterHtmlBodySanitization() -> None:
    """Verifies HTML body is preserved in description or falls back to title if missing."""
    richHtml = "<div><h2>Product Highlights</h2><ul><li>Feature 1</li></ul></div>"
    payloadWithHtml = ShopifyWebhookPayload(
        id=888,
        title="Rich HTML Product",
        body_html=richHtml,
        variants=[{"id": 1, "price": "100.00", "inventory_quantity": 5}],
    )
    listingsHtml = processShopifyWebhook(payloadWithHtml, testMerchantDid)
    assert len(listingsHtml) == 1
    assert listingsHtml[0].description == richHtml

    payloadNoHtml = ShopifyWebhookPayload(
        id=889,
        title="Plain Title Fallback",
        body_html=None,
        variants=[{"id": 1, "price": "100.00", "inventory_quantity": 5}],
    )
    listingsFallback = processShopifyWebhook(payloadNoHtml, testMerchantDid)
    assert len(listingsFallback) == 1
    assert listingsFallback[0].description == "Plain Title Fallback"


def testShopifyStoreAdapterMalformedPayloadHandling() -> None:
    """Verifies handling of empty variant lists, missing IDs, and missing prices."""
    emptyPayload = ShopifyWebhookPayload(
        id=999,
        title="Empty Variants Product",
        variants=[],
    )
    assert processShopifyWebhook(emptyPayload, testMerchantDid) == []

    variantMissingId = {"price": "250.00", "inventory_quantity": 10}
    payloadMissingId = ShopifyWebhookPayload(
        id=998,
        title="Missing Variant ID",
        variants=[variantMissingId],
    )
    listingsMissingId = processShopifyWebhook(payloadMissingId, testMerchantDid)
    assert len(listingsMissingId) == 1
    assert listingsMissingId[0].skuId == "SHOPIFY-998-default"

    variantMissingPrice = {"id": 2, "inventory_quantity": 5}
    payloadMissingPrice = ShopifyWebhookPayload(
        id=997,
        title="Missing Price Variant",
        variants=[variantMissingPrice],
    )
    listingsMissingPrice = processShopifyWebhook(payloadMissingPrice, testMerchantDid)
    assert len(listingsMissingPrice) == 1
    assert listingsMissingPrice[0].baseUnitPricePaise == 0
