"""Adversarial Benchmark Module 3 — Merchant API ERP Ingestion & Fault Isolation.

Covers:
- TC-15: ERP batch pagination idempotency & non-negative stock clamping (max(0, currentStock + delta)).
- TC-16: Corrupted payload fault isolation isolating float prices, string booleans, negative prices/stock
         into rejectedSkuIds while cleanly applying valid SKUs.
"""

from decimal import Decimal
from typing import Any, List
import pytest

from razoragentMesh.packages.merchantApi.src.adapters.csvIngestionAdapter import (
    ingestCsvContent,
)
from razoragentMesh.packages.merchantApi.src.adapters.erpSyncAdapter import (
    ErpBatchSyncRequest,
    ErpBatchSyncResult,
    ErpDeltaResult,
    processBatchSync,
    processErpDelta,
)
from razoragentMesh.packages.merchantApi.src.catalog.catalogManager import (
    CatalogManager,
)
from razoragentMesh.packages.merchantApi.src.catalog.priceNormalizer import (
    ArithmeticDriftException,
    normalizeInrToPaise,
)
from razoragentMesh.packages.merchantApi.src.schemas.universalProductSchema import (
    UniversalProductListing,
)
from razoragentMesh.tests.mockInfraHelpers import MockRedisAsync

sampleMerchantDidTc15: str = "did:mesh:merchant_tc15_01"
sampleBatchIdTc15: str = "BATCH-PAGINATED-2026-001"
clampSkuId: str = "SKU-CLAMP-01"
sampleOriginPincode: str = "560001"
sampleHsnCode: str = "84713010"


def _createBaseProductListing(skuId: str, stock: int, pricePaise: int) -> UniversalProductListing:
    """Helper to build a valid UniversalProductListing instance."""
    return UniversalProductListing(
        skuId=skuId,
        merchantDid=sampleMerchantDidTc15,
        title=f"Sample Product {skuId}",
        description=f"Description for {skuId}",
        category="electronics",
        hsnCode=sampleHsnCode,
        gstRatePercent=18,
        baseUnitPricePaise=pricePaise,
        availableStock=stock,
        originPincode=sampleOriginPincode,
    )


@pytest.mark.asyncio
async def testTc15StockClampingNonNegativeInvariant() -> None:
    """TC-15: Inventory adjustments clamp to zero when negative delta exceeds available stock."""
    mockRedis = MockRedisAsync()
    initialStock = 10
    basePrice = 50000
    listing = _createBaseProductListing(clampSkuId, initialStock, basePrice)
    await CatalogManager.upsertListing(mockRedis, listing)

    # Apply negative delta exceeding current stock (-25 on stock 10)
    applied = await CatalogManager.applyStockPriceDelta(mockRedis, clampSkuId, stockDelta=-25)
    assert applied is True

    updatedListing = await CatalogManager.getListing(mockRedis, sampleMerchantDidTc15, clampSkuId)
    assert updatedListing is not None
    assert updatedListing.availableStock == 0

    stockKey = f"mesh:catalog:{clampSkuId}:stock"
    storedStock = await mockRedis.get(stockKey)
    assert storedStock == "0"

    # Re-apply positive delta (15 on stock 0)
    await CatalogManager.applyStockPriceDelta(mockRedis, clampSkuId, stockDelta=15)
    updatedListing2 = await CatalogManager.getListing(mockRedis, sampleMerchantDidTc15, clampSkuId)
    assert updatedListing2 is not None
    assert updatedListing2.availableStock == 15

    # Update both price and stock
    await CatalogManager.applyStockPriceDelta(
        mockRedis, clampSkuId, stockDelta=-5, newPricePaise=55000
    )
    updatedListing3 = await CatalogManager.getListing(mockRedis, sampleMerchantDidTc15, clampSkuId)
    assert updatedListing3 is not None
    assert updatedListing3.availableStock == 10
    assert updatedListing3.baseUnitPricePaise == 55000


def testTc15ErpBatchPaginationIdempotency() -> None:
    """TC-15: Duplicate batch ingestion produces identical deterministic results."""
    batchDeltas = [
        {"skuId": "SKU-PAGE-01", "stockDelta": -5, "newPricePaise": 48000},
        {"skuId": "SKU-PAGE-02", "stockDelta": 10, "newPricePaise": 12000},
        {"skuId": "SKU-PAGE-03", "stockDelta": 0},
    ]
    request = ErpBatchSyncRequest(
        merchantDid=sampleMerchantDidTc15,
        batchId=sampleBatchIdTc15,
        deltas=batchDeltas,
    )

    deltaResults1, syncResult1 = processBatchSync(request)
    deltaResults2, syncResult2 = processBatchSync(request)

    assert syncResult1.appliedCount == syncResult2.appliedCount == 3
    assert syncResult1.rejectedCount == syncResult2.rejectedCount == 0
    assert syncResult1.rejectedSkuIds == syncResult2.rejectedSkuIds == []
    assert len(deltaResults1) == len(deltaResults2) == 3

    for res1, res2 in zip(deltaResults1, deltaResults2):
        assert res1.skuId == res2.skuId
        assert res1.applied is True
        assert res1.reason is None


def testTc16CorruptedPayloadFaultIsolation() -> None:
    """TC-16: Corrupted batch items are isolated into rejectedSkuIds while valid items apply."""
    contaminatedDeltas = [
        {"skuId": "SKU-VALID-1", "stockDelta": 5, "newPricePaise": 29900},
        {"skuId": "SKU-FLOAT-1", "stockDelta": 2, "newPricePaise": "42.50"},
        {"skuId": "SKU-BOOL-1", "stockDelta": "true"},
        {"skuId": "SKU-NEG-1", "stockDelta": 1, "newPricePaise": -500},
        {"skuId": "   ", "stockDelta": 10},
        {"skuId": "SKU-BAD-PRICE", "stockDelta": 1, "newPricePaise": "abc"},
        {"skuId": "SKU-NO-STOCK"},
        {"skuId": "SKU-VALID-2", "stockDelta": -2},
    ]
    request = ErpBatchSyncRequest(
        merchantDid=sampleMerchantDidTc15,
        batchId="BATCH-CONTAMINATED-01",
        deltas=contaminatedDeltas,
    )

    deltaResults, syncResult = processBatchSync(request)

    assert syncResult.appliedCount == 2
    assert syncResult.rejectedCount == 6
    assert "SKU-FLOAT-1" in syncResult.rejectedSkuIds
    assert "SKU-BOOL-1" in syncResult.rejectedSkuIds
    assert "SKU-NEG-1" in syncResult.rejectedSkuIds
    assert "SKU-BAD-PRICE" in syncResult.rejectedSkuIds

    validResults = [r for r in deltaResults if r.applied]
    assert len(validResults) == 2
    assert {r.skuId for r in validResults} == {"SKU-VALID-1", "SKU-VALID-2"}


def testTc16PriceNormalizerFaultIsolation() -> None:
    """TC-16: Float values and malformed strings trigger ArithmeticDriftException."""
    with pytest.raises(ArithmeticDriftException):
        normalizeInrToPaise(42.50)

    with pytest.raises(ArithmeticDriftException):
        normalizeInrToPaise("-100.00")

    with pytest.raises(ArithmeticDriftException):
        normalizeInrToPaise(-500)

    with pytest.raises(ArithmeticDriftException):
        normalizeInrToPaise("invalid_currency_str")

    assert normalizeInrToPaise("42.50") == 4250
    assert normalizeInrToPaise(100) == 10000
    assert normalizeInrToPaise("199.99") == 19999
    assert normalizeInrToPaise(Decimal("15.50")) == 1550


def testTc16CsvIngestionFaultIsolation() -> None:
    """TC-16: CSV ingestion cleanly isolates invalid rows and imports valid listings."""
    csvData = (
        "skuId,title,category,basePriceInr,availableStock,hsnCode\n"
        "SKU-CSV-01,Valid Product 1,electronics,499.00,20,84713010\n"
        ",Missing Sku Product,electronics,199.00,10,84713010\n"
        "SKU-CSV-02,Valid Product 2,apparel,1299.50,15,61091000\n"
        "SKU-CSV-03,Negative Price Product,food,-50.00,10,21069099\n"
        "SKU-CSV-04,,food,100.00,5,21069099\n"
    )

    listings, result = ingestCsvContent(csvData, sampleMerchantDidTc15)

    assert result.totalRowsProcessed == 5
    assert result.successCount == 2
    assert result.failureCount == 3
    assert len(listings) == 2

    assert listings[0].skuId == "SKU-CSV-01"
    assert listings[0].baseUnitPricePaise == 49900
    assert listings[1].skuId == "SKU-CSV-02"
    assert listings[1].baseUnitPricePaise == 129950
