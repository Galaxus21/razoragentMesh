"""Unit and integration tests for merchantApi onboarding, adapters, routes, and app factory."""

import io
import time
import pytest
from starlette.testclient import TestClient

from razoragentMesh.packages.merchantApi.src.adapters.csvIngestionAdapter import (
    ingestCsvContent,
    normalizeInrToPaise,
    parseCsvRow,
)
from razoragentMesh.packages.merchantApi.src.adapters.erpSyncAdapter import (
    ErpDeltaResult,
    processBatchSync,
    processErpDelta,
)
from razoragentMesh.packages.merchantApi.src.adapters.shopifyStoreAdapter import (
    mapShopifyVariantToSku,
    processShopifyWebhook,
)
from razoragentMesh.packages.merchantApi.src.merchantApp import createMerchantApp
from razoragentMesh.packages.merchantApi.src.onboarding.merchantRegistrar import (
    buildMerchantProfile,
    generateMerchantKeypair,
    mintMerchantDid,
    validateGstin,
)
from razoragentMesh.packages.merchantApi.src.onboarding.razorpayAccountLinker import (
    buildRouteLinkedAccountRef,
    validateRazorpayAccountId,
)
from razoragentMesh.packages.merchantApi.src.routes.dependencies import getRedisClient
from razoragentMesh.packages.merchantApi.src.schemas.bulkIngestSchema import (
    ErpBatchSyncRequest,
    ShopifyWebhookPayload,
)
from razoragentMesh.packages.merchantApi.src.schemas.merchantSchema import (
    MerchantRegistrationRequest,
)
from razoragentMesh.packages.merchantApi.src.schemas.policySchema import NegotiationPolicy
from razoragentMesh.packages.merchantApi.src.schemas.universalProductSchema import (
    UniversalProductListing,
)
from razoragentMesh.tests.mockInfraHelpers import MockRedisAsync

# Test Constants
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
    assert validateGstin("27AAPFU0939F1Z0") is False  # Wrong checksum char
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
        businessName="Acme Robotics",
        contactEmail="ops@acme.in",
        gstin=validGstin1,
        originPincode="560001",
        razorpayAccountId=validRazorpayAccount,
    )
    keypair = generateMerchantKeypair(req)
    assert keypair.merchantDid.startswith("did:razoragent:merchant:")
    assert len(keypair.publicKeyHex) == 64
    assert len(keypair.privateKeyHex) == 64

    profile = buildMerchantProfile(req, keypair)
    assert profile.merchantDid == keypair.merchantDid
    assert profile.businessName == "Acme Robotics"
    assert profile.registeredAtTimestamp > 0


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

    assert result.totalRowsProcessed == 3
    assert result.successCount == 2
    assert result.failureCount == 1
    assert len(listings) == 2

    # Check apparel listing
    apparelListing = listings[0]
    assert apparelListing.skuId == "SKU-TEST-01"
    assert apparelListing.baseUnitPricePaise == 49900
    assert apparelListing.apparelFacet is not None
    assert apparelListing.apparelFacet.size == "M"
    assert apparelListing.apparelFacet.color == "Blue"
    assert len(apparelListing.volumeTiers) == 1

    # Check FMCG listing
    fmcgListing = listings[1]
    assert fmcgListing.skuId == "SKU-TEST-02"
    assert fmcgListing.baseUnitPricePaise == 5000
    assert fmcgListing.fmcgFacet is not None
    assert "peanut" in fmcgListing.fmcgFacet.allergens
    assert "almond" in fmcgListing.fmcgFacet.allergens


def testShopifyStoreAdapter() -> None:
    """Verifies Shopify webhook mapping with allergen extraction from tags."""
    payload = ShopifyWebhookPayload(
        id=987654321,
        title="Organic Protein Bar",
        body_html="<p>Delicious bar</p>",
        tags="allergens:peanuts,dairy, organic, energy",
        variants=[
            {
                "id": 111,
                "price": "120.00",
                "inventory_quantity": 50,
                "option1": "Large",
                "option2": "Chocolate",
            }
        ],
    )
    listings = processShopifyWebhook(payload, testMerchantDid)
    assert len(listings) == 1
    listing = listings[0]
    assert listing.skuId == "SHOPIFY-987654321-111"
    assert listing.baseUnitPricePaise == 12000
    assert listing.availableStock == 50
    assert listing.fmcgFacet is not None
    assert "peanuts" in listing.fmcgFacet.allergens
    assert "dairy" in listing.fmcgFacet.allergens


def testErpSyncAdapter() -> None:
    """Verifies parsing of ERP delta batch updates."""
    req = ErpBatchSyncRequest(
        merchantDid=testMerchantDid,
        batchId="batch-001",
        deltas=[
            {"skuId": "SKU-001", "stockDelta": -5, "newPricePaise": 410000},
            {"skuId": "SKU-002", "stockDelta": 10},
            {"skuId": "", "stockDelta": 10},  # Bad SKU
            {"skuId": "SKU-003", "stockDelta": "bad"},  # Bad delta
        ],
    )
    deltaResults, syncResult = processBatchSync(req)
    assert syncResult.appliedCount == 2
    assert syncResult.rejectedCount == 2
    assert deltaResults[0].applied is True
    assert deltaResults[2].applied is False


def testMerchantApiRoutes() -> None:
    """Verifies all FastAPI routes via TestClient with mock Redis state."""
    app = createMerchantApp()
    mockRedis = MockRedisAsync()
    app.state.redis = mockRedis
    app.dependency_overrides[getRedisClient] = lambda: mockRedis

    with TestClient(app) as client:
        # 1. Register Merchant
        regPayload = {
            "businessName": "Test Merchant",
            "contactEmail": "test@merchant.in",
            "gstin": validGstin1,
            "originPincode": "560001",
            "razorpayAccountId": validRazorpayAccount,
        }
        resReg = client.post("/api/v1/merchant/register", json=regPayload)
        assert resReg.status_code == 201
        profileData = resReg.json()
        merchantDid = profileData["merchantDid"]
        assert merchantDid.startswith("did:razoragent:merchant:")

        # 2. Test Invalid Registration (bad checksum on regex-valid GSTIN)
        badRegPayload = {**regPayload, "gstin": "27AAPFU0939F1Z0"}
        resBadReg = client.post("/api/v1/merchant/register", json=badRegPayload)
        assert resBadReg.status_code == 400

        # 3. Create Catalog SKU
        skuPayload = {
            "skuId": "SKU-API-001",
            "merchantDid": merchantDid,
            "title": "API Cotton Shirt",
            "description": "High grade cotton shirt",
            "category": "apparel",
            "hsnCode": "6109",
            "gstRatePercent": 5,
            "baseUnitPricePaise": 59900,
            "availableStock": 25,
            "originPincode": "560001",
        }
        resSku = client.post(f"/api/v1/merchant/{merchantDid}/catalog", json=skuPayload)
        assert resSku.status_code == 201
        assert resSku.json()["status"] == "created"

        # 4. Get SKU
        resGetSku = client.get(f"/api/v1/merchant/{merchantDid}/catalog/SKU-API-001")
        assert resGetSku.status_code == 200
        assert resGetSku.json()["skuId"] == "SKU-API-001"

        # 5. Update SKU
        updatedPayload = {**skuPayload, "baseUnitPricePaise": 54900, "availableStock": 30}
        resPutSku = client.put(f"/api/v1/merchant/{merchantDid}/catalog/SKU-API-001", json=updatedPayload)
        assert resPutSku.status_code == 200

        # 6. Set Policy
        policyPayload = {
            "merchantDid": merchantDid,
            "marginFloorBps": 600,
            "minimumOrderQuantity": 10,
            "autoAcceptSpreadPaise": 50,
            "maxNegotiationTurns": 4,
            "createdAtTimestamp": int(time.time()),
            "updatedAtTimestamp": int(time.time()),
        }
        resPolicy = client.put(f"/api/v1/merchant/{merchantDid}/policy", json=policyPayload)
        assert resPolicy.status_code == 200
        assert resPolicy.json()["marginFloorBps"] == 600

        # 7. Get Policy
        resGetPolicy = client.get(f"/api/v1/merchant/{merchantDid}/policy")
        assert resGetPolicy.status_code == 200
        assert resGetPolicy.json()["maxNegotiationTurns"] == 4

        # 8. Bulk CSV Ingest
        csvFileContent = (
            "skuId,title,description,category,hsnCode,gstRatePercent,basePriceInr,availableStock,originPincode\n"
            "SKU-BULK-01,Bulk Item 1,Item description,apparel,6109,5,199.00,50,560001\n"
            "SKU-BULK-02,Bulk Item 2,Item description,apparel,6109,5,299.00,75,560001\n"
        )
        resCsv = client.post(
            f"/api/v1/merchant/{merchantDid}/bulk-csv",
            files={"file": ("test.csv", io.BytesIO(csvFileContent.encode("utf-8")), "text/csv")},
        )
        assert resCsv.status_code == 200
        assert resCsv.json()["successCount"] == 2

        # 9. Shopify Sync
        shopifyPayload = {
            "id": 12345,
            "title": "Shopify Jacket",
            "variants": [{"id": 999, "price": "1499.00", "inventory_quantity": 10}],
        }
        resShopify = client.post(f"/api/v1/merchant/{merchantDid}/shopify-sync", json=shopifyPayload)
        assert resShopify.status_code == 200
        assert resShopify.json()["status"] == "synchronized"

        # 10. ERP Sync
        erpPayload = {
            "merchantDid": merchantDid,
            "batchId": "batch-sync-01",
            "deltas": [{"skuId": "SKU-BULK-01", "stockDelta": -10, "newPricePaise": 18900}],
        }
        resErp = client.post(f"/api/v1/merchant/{merchantDid}/erp-sync", json=erpPayload)
        assert resErp.status_code == 200
        assert resErp.json()["appliedCount"] == 1

        # 11. Delete SKU
        resDel = client.delete(f"/api/v1/merchant/{merchantDid}/catalog/SKU-API-001")
        assert resDel.status_code == 200
        assert resDel.json()["status"] == "deleted"
