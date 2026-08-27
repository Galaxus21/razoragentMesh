"""Unit and integration tests for merchantApi routes."""

import io
import time
from starlette.testclient import TestClient

from razoragentMesh.packages.merchantApi.src.merchantApp import createMerchantApp
from razoragentMesh.packages.merchantApi.src.routes.dependencies import getRedisClient
from razoragentMesh.tests.mockInfraHelpers import MockRedisAsync

validGstin1 = "27AAPFU0939F1ZV"
validRazorpayAccount = "acc_0123456789ABCDEF0123"


def _setupMerchantTestClient() -> tuple[TestClient, MockRedisAsync]:
    app = createMerchantApp()
    mockRedis = MockRedisAsync()
    app.state.redis = mockRedis
    app.dependency_overrides[getRedisClient] = lambda: mockRedis
    return TestClient(app), mockRedis


def testMerchantApiRegistrationRoutes() -> None:
    """Verifies merchant registration endpoint and bad GSTIN checksum rejection."""
    client, _ = _setupMerchantTestClient()
    with client:
        regPayload = {
            "businessName": "Test Merchant", "contactEmail": "test@merchant.in",
            "gstin": validGstin1, "originPincode": "560001",
            "razorpayAccountId": validRazorpayAccount,
        }
        resReg = client.post("/api/v1/merchant/register", json=regPayload)
        assert resReg.status_code == 201
        assert resReg.json()["merchantDid"].startswith("did:razoragent:merchant:")

        badRegPayload = {**regPayload, "gstin": "27AAPFU0939F1Z0"}
        resBadReg = client.post("/api/v1/merchant/register", json=badRegPayload)
        assert resBadReg.status_code == 400


def testMerchantApiCatalogCrudRoutes() -> None:
    """Verifies Catalog create, get, put, delete routes."""
    client, _ = _setupMerchantTestClient()
    with client:
        regRes = client.post("/api/v1/merchant/register", json={
            "businessName": "Test Merchant", "contactEmail": "test@merchant.in",
            "gstin": validGstin1, "originPincode": "560001", "razorpayAccountId": validRazorpayAccount,
        })
        merchantDid = regRes.json()["merchantDid"]

        skuPayload = {
            "skuId": "SKU-API-001", "merchantDid": merchantDid, "title": "API Cotton Shirt",
            "description": "High grade shirt", "category": "apparel", "hsnCode": "6109",
            "gstRatePercent": 5, "baseUnitPricePaise": 59900, "availableStock": 25, "originPincode": "560001",
        }
        resSku = client.post(f"/api/v1/merchant/{merchantDid}/catalog", json=skuPayload)
        assert resSku.status_code == 201 and resSku.json()["status"] == "created"

        resGet = client.get(f"/api/v1/merchant/{merchantDid}/catalog/SKU-API-001")
        assert resGet.status_code == 200 and resGet.json()["skuId"] == "SKU-API-001"

        updated = {**skuPayload, "baseUnitPricePaise": 54900, "availableStock": 30}
        resPut = client.put(f"/api/v1/merchant/{merchantDid}/catalog/SKU-API-001", json=updated)
        assert resPut.status_code == 200

        resDel = client.delete(f"/api/v1/merchant/{merchantDid}/catalog/SKU-API-001")
        assert resDel.status_code == 200 and resDel.json()["status"] == "deleted"


def testMerchantApiPolicyRoutes() -> None:
    """Verifies Policy set and get routes."""
    client, _ = _setupMerchantTestClient()
    with client:
        regRes = client.post("/api/v1/merchant/register", json={
            "businessName": "Test Merchant", "contactEmail": "test@merchant.in",
            "gstin": validGstin1, "originPincode": "560001", "razorpayAccountId": validRazorpayAccount,
        })
        merchantDid = regRes.json()["merchantDid"]

        now = int(time.time())
        policyPayload = {
            "merchantDid": merchantDid, "marginFloorBps": 600, "minimumOrderQuantity": 10,
            "autoAcceptSpreadPaise": 50, "maxNegotiationTurns": 4, "createdAtTimestamp": now, "updatedAtTimestamp": now,
        }
        resPutPolicy = client.put(f"/api/v1/merchant/{merchantDid}/policy", json=policyPayload)
        assert resPutPolicy.status_code == 200 and resPutPolicy.json()["marginFloorBps"] == 600

        resGetPolicy = client.get(f"/api/v1/merchant/{merchantDid}/policy")
        assert resGetPolicy.status_code == 200 and resGetPolicy.json()["maxNegotiationTurns"] == 4


def testMerchantApiBulkSyncRoutes() -> None:
    """Verifies bulk CSV, Shopify, and ERP sync routes."""
    client, _ = _setupMerchantTestClient()
    with client:
        regRes = client.post("/api/v1/merchant/register", json={
            "businessName": "Test Merchant", "contactEmail": "test@merchant.in",
            "gstin": validGstin1, "originPincode": "560001", "razorpayAccountId": validRazorpayAccount,
        })
        merchantDid = regRes.json()["merchantDid"]

        csvContent = (
            "skuId,title,description,category,hsnCode,gstRatePercent,basePriceInr,availableStock,originPincode\n"
            "SKU-BULK-01,Bulk Item 1,Item 1,apparel,6109,5,199.00,50,560001\n"
        )
        resCsv = client.post(
            f"/api/v1/merchant/{merchantDid}/bulk-csv",
            files={"file": ("test.csv", io.BytesIO(csvContent.encode("utf-8")), "text/csv")},
        )
        assert resCsv.status_code == 200 and resCsv.json()["successCount"] == 1

        shopifyPayload = {"id": 12345, "title": "Jacket", "variants": [{"id": 999, "price": "1499.00", "inventory_quantity": 10}]}
        resShopify = client.post(f"/api/v1/merchant/{merchantDid}/shopify-sync", json=shopifyPayload)
        assert resShopify.status_code == 200 and resShopify.json()["status"] == "synchronized"

        erpPayload = {"merchantDid": merchantDid, "batchId": "b-01", "deltas": [{"skuId": "SKU-BULK-01", "stockDelta": -10}]}
        resErp = client.post(f"/api/v1/merchant/{merchantDid}/erp-sync", json=erpPayload)
        assert resErp.status_code == 200 and resErp.json()["appliedCount"] == 1
