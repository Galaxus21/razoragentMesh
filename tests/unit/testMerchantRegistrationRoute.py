"""Unit tests for merchant registration route and domain exception hierarchy."""

import pytest
from starlette.testclient import TestClient

from razoragentMesh.packages.merchantApi.src.exceptions.merchantExceptions import (
    BulkIngestionException,
    CatalogNotFoundException,
    InvalidGstinException,
    InvalidRazorpayAccountException,
    MerchantApiException,
    MerchantStorageUnavailableException,
    PolicyConflictException,
    PolicyNotFoundException,
)
from razoragentMesh.packages.merchantApi.src.merchantApp import createMerchantApp
from razoragentMesh.packages.merchantApi.src.routes.dependencies import getRedisClient
from razoragentMesh.packages.merchantApi.src.schemas.merchantSchema import (
    MerchantRegistrationRequest,
)
from razoragentMesh.tests.mockInfraHelpers import MockRedisAsync

# Test Constants
validGstin1: str = "27AAPFU0939F1ZV"
validGstin2: str = "29AAAAA0000A1ZY"
invalidChecksumGstin: str = "27AAPFU0939F1Z0"
shortRazorpayAccount: str = "acc_short123"
validRazorpayAccount: str = "acc_0123456789ABCDEF0123"
testBusinessName: str = "Apex Dynamics"
testContactEmail: str = "ops@apexdynamics.in"
testOriginPincode: str = "560001"


def testMerchantApiExceptionHierarchy() -> None:
    """Verifies status codes, messages, and inheritance across domain exceptions."""
    baseExc = MerchantApiException("Generic error", 418)
    assert isinstance(baseExc, Exception)
    assert baseExc.statusCode == 418
    assert baseExc.message == "Generic error"

    gstinExc = InvalidGstinException()
    assert isinstance(gstinExc, MerchantApiException)
    assert gstinExc.statusCode == 400
    assert "GSTIN" in gstinExc.message

    razorpayExc = InvalidRazorpayAccountException()
    assert isinstance(razorpayExc, MerchantApiException)
    assert razorpayExc.statusCode == 400
    assert "Razorpay" in razorpayExc.message

    catalogExc = CatalogNotFoundException("SKU not found")
    assert isinstance(catalogExc, MerchantApiException)
    assert catalogExc.statusCode == 404

    policyNotFoundExc = PolicyNotFoundException("Policy missing")
    assert isinstance(policyNotFoundExc, MerchantApiException)
    assert policyNotFoundExc.statusCode == 404

    policyConflictExc = PolicyConflictException()
    assert isinstance(policyConflictExc, MerchantApiException)
    assert policyConflictExc.statusCode == 409

    bulkExc = BulkIngestionException("CSV failed")
    assert isinstance(bulkExc, MerchantApiException)
    assert bulkExc.statusCode == 400

    storageExc = MerchantStorageUnavailableException()
    assert isinstance(storageExc, MerchantApiException)
    assert storageExc.statusCode == 503


def testSuccessfulMerchantRegistration() -> None:
    """Verifies registration route returns 201 and valid DID profile."""
    app = createMerchantApp()
    mockRedis = MockRedisAsync()
    app.state.redis = mockRedis
    app.dependency_overrides[getRedisClient] = lambda: mockRedis

    with TestClient(app) as client:
        payload = {
            "businessName": testBusinessName,
            "contactEmail": testContactEmail,
            "gstin": validGstin1,
            "originPincode": testOriginPincode,
            "razorpayAccountId": validRazorpayAccount,
        }
        response = client.post("/api/v1/merchant/register", json=payload)
        assert response.status_code == 201
        data = response.json()
        assert data["businessName"] == testBusinessName
        assert data["merchantDid"].startswith("did:razoragent:merchant:")
        assert data["registeredAtTimestamp"] > 0


def testRegistrationInvalidGstinChecksum() -> None:
    """Verifies InvalidGstinException returns 400 with expected error detail."""
    app = createMerchantApp()
    mockRedis = MockRedisAsync()
    app.state.redis = mockRedis
    app.dependency_overrides[getRedisClient] = lambda: mockRedis

    with TestClient(app) as client:
        payload = {
            "businessName": testBusinessName,
            "contactEmail": testContactEmail,
            "gstin": invalidChecksumGstin,
            "originPincode": testOriginPincode,
            "razorpayAccountId": validRazorpayAccount,
        }
        response = client.post("/api/v1/merchant/register", json=payload)
        assert response.status_code == 400
        assert response.json() == {"detail": "Invalid Indian GSTIN format or checksum"}


def testRegistrationInvalidRazorpayAccount() -> None:
    """Verifies InvalidRazorpayAccountException returns 400 with expected error detail."""
    app = createMerchantApp()
    mockRedis = MockRedisAsync()
    app.state.redis = mockRedis
    app.dependency_overrides[getRedisClient] = lambda: mockRedis

    with TestClient(app) as client:
        payload = {
            "businessName": testBusinessName,
            "contactEmail": testContactEmail,
            "gstin": validGstin1,
            "originPincode": testOriginPincode,
            "razorpayAccountId": shortRazorpayAccount,
        }
        response = client.post("/api/v1/merchant/register", json=payload)
        assert response.status_code == 400
        assert response.json() == {"detail": "Invalid Razorpay Route account ID format"}


def testMerchantStorageUnavailable() -> None:
    """Verifies MerchantStorageUnavailableException returns 503 when storage backend is down."""
    app = createMerchantApp()

    async def mockFailingRedisClient() -> None:
        raise MerchantStorageUnavailableException("Redis storage service is unavailable")

    app.dependency_overrides[getRedisClient] = mockFailingRedisClient

    with TestClient(app, raise_server_exceptions=False) as client:
        payload = {
            "businessName": testBusinessName,
            "contactEmail": testContactEmail,
            "gstin": validGstin1,
            "originPincode": testOriginPincode,
            "razorpayAccountId": validRazorpayAccount,
        }
        response = client.post("/api/v1/merchant/register", json=payload)
        assert response.status_code == 503
        assert response.json() == {"detail": "Redis storage service is unavailable"}


def testCatalogNotFoundExceptionHandler() -> None:
    """Verifies CatalogNotFoundException returns 404 with SKU detail."""
    app = createMerchantApp()
    mockRedis = MockRedisAsync()
    app.state.redis = mockRedis
    app.dependency_overrides[getRedisClient] = lambda: mockRedis

    with TestClient(app) as client:
        response = client.get("/api/v1/merchant/did:razoragent:merchant:123/catalog/SKU-NON-EXISTENT")
        assert response.status_code == 404
        assert "SKU-NON-EXISTENT" in response.json()["detail"]


def testPolicyNotFoundExceptionHandler() -> None:
    """Verifies PolicyNotFoundException returns 404 with policy detail."""
    app = createMerchantApp()
    mockRedis = MockRedisAsync()
    app.state.redis = mockRedis
    app.dependency_overrides[getRedisClient] = lambda: mockRedis

    with TestClient(app) as client:
        response = client.get("/api/v1/merchant/did:razoragent:merchant:123/policy")
        assert response.status_code == 404
        assert "Negotiation policy not configured" in response.json()["detail"]


def testPolicyConflictExceptionHandler() -> None:
    """Verifies PolicyConflictException returns 409 status code."""
    app = createMerchantApp()

    @app.get("/api/v1/merchant/test-conflict")
    async def triggerConflict() -> dict[str, str]:
        raise PolicyConflictException("Policy overlap detected")

    with TestClient(app) as client:
        response = client.get("/api/v1/merchant/test-conflict")
        assert response.status_code == 409
        assert response.json() == {"detail": "Policy overlap detected"}


def testBulkIngestionExceptionHandler() -> None:
    """Verifies BulkIngestionException returns 400 status code."""
    app = createMerchantApp()

    @app.get("/api/v1/merchant/test-bulk-error")
    async def triggerBulkError() -> dict[str, str]:
        raise BulkIngestionException("Corrupted CSV structure")

    with TestClient(app) as client:
        response = client.get("/api/v1/merchant/test-bulk-error")
        assert response.status_code == 400
        assert response.json() == {"detail": "Corrupted CSV structure"}
