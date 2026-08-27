"""Unit tests for merchantApi onboarding, CSV/Shopify/ERP adapters, and promotions."""

import pytest

from razoragentMesh.packages.merchantApi.src.adapters.csvIngestionAdapter import (
    ingestCsvContent,
    normalizeInrToPaise,
)
from razoragentMesh.packages.merchantApi.src.adapters.erpSyncAdapter import (
    processBatchSync,
)
from razoragentMesh.packages.merchantApi.src.adapters.shopifyStoreAdapter import (
    processShopifyWebhook,
)
from razoragentMesh.packages.merchantApi.src.onboarding.merchantRegistrar import (
    buildMerchantProfile,
    generateMerchantKeypair,
    validateGstin,
)
from razoragentMesh.packages.merchantApi.src.onboarding.razorpayAccountLinker import (
    buildRouteLinkedAccountRef,
    validateRazorpayAccountId,
)
from razoragentMesh.packages.merchantApi.src.schemas.bulkIngestSchema import (
    ErpBatchSyncRequest,
    ShopifyWebhookPayload,
)
from razoragentMesh.packages.merchantApi.src.schemas.merchantSchema import (
    MerchantRegistrationRequest,
)

validGstin1 = "27AAPFU0939F1ZV"
validGstin2 = "29AAAAA0000A1ZY"
invalidGstin = "INVALID_GSTIN_123"
validRazorpayAccount = "acc_0123456789ABCDEF0123"
invalidRazorpayAccount = "invalid_acc"
testMerchantDid = "did:razoragent:merchant:abcdef0123456789"


def testValidateGstin() -> None:
    """Verifies GSTIN regex and mod-36 checksum validation."""
    assert validateGstin(validGstin1) is True
    assert validateGstin(validGstin2) is True
    assert validateGstin(invalidGstin) is False
    assert validateGstin("27AAPFU0939F1Z0") is False
    assert validateGstin("") is False


def testValidateRazorpayAccountId() -> None:
    """Verifies Razorpay Route account ID format."""
    assert validateRazorpayAccountId(validRazorpayAccount) is True
    assert validateRazorpayAccountId(invalidRazorpayAccount) is False
    assert validateRazorpayAccountId("acc_short") is False


def testBuildRouteLinkedAccountRef() -> None:
    """Verifies generation of Route split reference dictionary."""
    ref = buildRouteLinkedAccountRef(validRazorpayAccount, testMerchantDid)
    assert ref["account_id"] == validRazorpayAccount
    assert ref["merchant_did"] == testMerchantDid

    with pytest.raises(ValueError):
        buildRouteLinkedAccountRef("bad_acc", testMerchantDid)


def testMerchantRegistrarAndProfile() -> None:
    """Verifies Ed25519 keypair generation and profile minting."""
    req = MerchantRegistrationRequest(
        businessName="Acme Robotics", contactEmail="ops@acme.in",
        gstin=validGstin1, originPincode="560001", razorpayAccountId=validRazorpayAccount,
    )
    keypair = generateMerchantKeypair(req)
    assert keypair.merchantDid.startswith("did:razoragent:merchant:")
    assert len(keypair.publicKeyHex) == 64 and len(keypair.privateKeyHex) == 64

    profile = buildMerchantProfile(req, keypair)
    assert profile.merchantDid == keypair.merchantDid
    assert profile.businessName == "Acme Robotics" and profile.registeredAtTimestamp > 0


def testNormalizeInrToPaise() -> None:
    """Verifies decimal rupee to integer paise conversion."""
    assert normalizeInrToPaise("42.50") == 4250
    assert normalizeInrToPaise(100) == 10000
    assert normalizeInrToPaise("3500.00") == 350000
    with pytest.raises(Exception):
        normalizeInrToPaise(-10)


def testCsvIngestionAdapter() -> None:
    """Verifies CSV parsing with volume tiers and facet extraction."""
    csvData = (
        "skuId,title,description,category,brand,hsnCode,gstRatePercent,basePriceInr,availableStock,originPincode,size,color,allergens,volumeTiersJson\n"
        'SKU-TEST-01,Test Shirt,Cotton T-Shirt,apparel,BrandX,6109,5,499.00,100,560001,M,Blue,,"[{""minQuantity"": 10, ""discountBps"": 500}]"\n'
        "SKU-TEST-02,Peanut Bar,Snack,fmcg,SnackCo,2106,18,50.00,200,560001,,,peanut;almond,\n"
        "SKU-BAD,,,,,,\n"
    )
    listings, result = ingestCsvContent(csvData, testMerchantDid)
    assert result.totalRowsProcessed == 3 and result.successCount == 2 and result.failureCount == 1
    assert len(listings) == 2

    assert listings[0].skuId == "SKU-TEST-01" and listings[0].apparelFacet.size == "M"
    assert listings[1].skuId == "SKU-TEST-02" and "peanut" in listings[1].fmcgFacet.allergens


def testShopifyStoreAdapter() -> None:
    """Verifies Shopify webhook mapping with allergen extraction from tags."""
    payload = ShopifyWebhookPayload(
        id=987654321, title="Organic Protein Bar", body_html="<p>Delicious bar</p>",
        tags="allergens:peanuts,dairy, organic, energy",
        variants=[{"id": 111, "price": "120.00", "inventory_quantity": 50, "option1": "Large", "option2": "Chocolate"}],
    )
    listings = processShopifyWebhook(payload, testMerchantDid)
    assert len(listings) == 1
    assert listings[0].skuId == "SHOPIFY-987654321-111"
    assert listings[0].baseUnitPricePaise == 12000 and listings[0].availableStock == 50
    assert "peanuts" in listings[0].fmcgFacet.allergens and "dairy" in listings[0].fmcgFacet.allergens


def testErpSyncAdapter() -> None:
    """Verifies parsing of ERP delta batch updates."""
    req = ErpBatchSyncRequest(
        merchantDid=testMerchantDid, batchId="batch-001",
        deltas=[
            {"skuId": "SKU-001", "stockDelta": -5, "newPricePaise": 410000},
            {"skuId": "SKU-002", "stockDelta": 10},
            {"skuId": "", "stockDelta": 10},
            {"skuId": "SKU-003", "stockDelta": "bad"},
        ],
    )
    deltaResults, syncResult = processBatchSync(req)
    assert syncResult.appliedCount == 2 and syncResult.rejectedCount == 2
    assert deltaResults[0].applied is True and deltaResults[2].applied is False


def testCsvIngestionWithPromotions() -> None:
    """Verifies CSV parsing with scheduled promotional campaigns."""
    csvData = (
        "skuId,title,description,category,brand,hsnCode,gstRatePercent,basePriceInr,availableStock,originPincode,promotionsJson\n"
        'SKU-PROMO-01,Promo Shirt,Flash sale shirt,apparel,BrandX,6109,5,499.00,100,560001,"[{""campaignId"": ""FLASH30"", ""name"": ""Flash 30% Off"", ""startsAtUnix"": 1700000000, ""endsAtUnix"": 1700100000, ""discountBps"": 3000}]"\n'
        'SKU-PROMO-02,Promo Chair,Office Chair,furniture,ComfortCo,9403,18,4200.00,50,560001,"[{""campaign_id"": ""SPECIAL700"", ""campaign_name"": ""Special Flat 700"", ""starts_at_unix"": 1700000000, ""ends_at_unix"": 1700050000, ""fixed_price_paise"": 350000}]"\n'
        "SKU-NO-PROMO,Plain Item,Regular item,apparel,BrandX,6109,5,100.00,10,560001,\n"
    )
    listings, result = ingestCsvContent(csvData, testMerchantDid)
    assert result.totalRowsProcessed == 3 and result.successCount == 3 and len(listings) == 3
    assert listings[0].promotions[0].campaignId == "FLASH30" and listings[0].promotions[0].discountBps == 3000
    assert listings[1].promotions[0].campaignId == "SPECIAL700" and listings[1].promotions[0].fixedPricePaise == 350000
    assert len(listings[2].promotions) == 0


def testShopifyStoreAdapterWithPromotions() -> None:
    """Verifies Shopify webhook mapping with parameterized and named promo tags."""
    payload = ShopifyWebhookPayload(
        id=123456789, title="Promotional Ergonomic Chair", body_html="<p>Comfortable office chair</p>",
        tags="promo:FLASH30:3000:1700000000:1700100000, promo:FESTIVE10, cotton, allergens:dust",
        variants=[{"id": 555, "price": "4200.00", "inventory_quantity": 25}],
    )
    listings = processShopifyWebhook(payload, testMerchantDid)
    assert len(listings) == 1 and len(listings[0].promotions) == 2
    assert listings[0].promotions[0].campaignId == "FLASH30" and listings[0].promotions[0].discountBps == 3000
    assert listings[0].promotions[1].campaignId == "shopify-festive10" and listings[0].promotions[1].discountBps == 1000
