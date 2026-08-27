"""Unit test suite for core CSV Ingestion Adapter parsing, price normalization, and batch limits."""

from decimal import Decimal
from typing import List
import pytest

from razoragentMesh.packages.merchantApi.src.adapters.csvIngestionAdapter import (
    ingestCsvContent,
    normalizeInrToPaise,
    parseCsvRow,
)
from razoragentMesh.packages.merchantApi.src.catalog.priceNormalizer import (
    ArithmeticDriftException,
)
from razoragentMesh.packages.merchantApi.src.schemas.bulkIngestSchema import (
    CsvIngestResult,
)
from razoragentMesh.packages.merchantApi.src.schemas.universalProductSchema import (
    UniversalProductListing,
)

testMerchantDid: str = "did:razoragent:merchant:abcdef0123456789"
defaultHsnCode: str = "6109"
defaultGstRate: int = 18
defaultPincode: str = "400001"
standardHeader: str = "skuId,title,description,category,hsnCode,gstRatePercent,basePriceInr,availableStock,originPincode\n"


def testCsvIngestionAdapterBasicRowParsing() -> None:
    """Verifies standard CSV rows parse into valid UniversalProductListing records."""
    csvContent = (
        standardHeader
        + "SKU-ROW-01,Office Chair,Ergonomic chair,furniture,94031000,18,4500.00,50,560001\n"
        + "SKU-ROW-02,Mechanical Keyboard,RGB keyboard,electronics,84716060,18,2999.00,100,560001\n"
    )
    listings, result = ingestCsvContent(csvContent, testMerchantDid)

    assert result.totalRowsProcessed == 2
    assert result.successCount == 2
    assert result.failureCount == 0
    assert len(listings) == 2

    assert listings[0].skuId == "SKU-ROW-01"
    assert listings[0].title == "Office Chair"
    assert listings[0].baseUnitPricePaise == 450000
    assert listings[0].availableStock == 50
    assert listings[0].hsnCode == "94031000"

    assert listings[1].skuId == "SKU-ROW-02"
    assert listings[1].baseUnitPricePaise == 299900
    assert listings[1].availableStock == 100


def testCsvIngestionAdapterPriceNormalization() -> None:
    """Verifies normalizeInrToPaise converts various string/integer formats and rejects invalid prices."""
    assert normalizeInrToPaise("499.00") == 49900
    assert normalizeInrToPaise(100) == 10000
    assert normalizeInrToPaise("0.99") == 99
    assert normalizeInrToPaise(Decimal("15.50")) == 1550
    assert normalizeInrToPaise("1500") == 150000

    # Float inputs are strictly rejected to prevent IEEE-754 drift
    with pytest.raises(ArithmeticDriftException):
        normalizeInrToPaise(42.50)

    with pytest.raises(ArithmeticDriftException):
        normalizeInrToPaise("-100.00")

    with pytest.raises(ArithmeticDriftException):
        normalizeInrToPaise("invalid_price_string")


def testCsvIngestionAdapterHsnAutocompletion() -> None:
    """Verifies default HSN and GST rate fallback when omitted in CSV rows."""
    minimalCsv = (
        "skuId,title,basePriceInr,availableStock\n"
        "SKU-AUTO-01,Generic Gadget,199.00,20\n"
    )
    listings, result = ingestCsvContent(minimalCsv, testMerchantDid)

    assert result.successCount == 1
    assert len(listings) == 1
    listing = listings[0]
    assert listing.hsnCode == defaultHsnCode
    assert listing.gstRatePercent == defaultGstRate
    assert listing.originPincode == defaultPincode


def testCsvIngestionAdapterBatchSummaryMetrics() -> None:
    """Verifies CsvIngestResult tracks total, success, failure counts, and failed SKU IDs."""
    mixedCsv = (
        standardHeader
        + "SKU-OK-01,Good Item 1,Desc,general,84713010,18,100.00,10,560001\n"
        + ",Missing SKU,Desc,general,84713010,18,200.00,10,560001\n"
        + "SKU-NO-TITLE,,Desc,general,84713010,18,300.00,10,560001\n"
        + "SKU-OK-02,Good Item 2,Desc,general,84713010,18,400.00,10,560001\n"
    )
    listings, result = ingestCsvContent(mixedCsv, testMerchantDid)

    assert result.totalRowsProcessed == 4
    assert result.successCount == 2
    assert result.failureCount == 2
    assert len(listings) == 2
    assert "SKU-NO-TITLE" in result.failedSkuIds
    assert len(result.failedSkuIds) == 2


def testCsvIngestionAdapterMaxBatchLimitEnforcement() -> None:
    """Verifies CSV batch size is bounded at 500 rows."""
    rows: List[str] = [standardHeader]
    for idx in range(1, 520):
        rows.append(f"SKU-BATCH-{idx},Item {idx},Desc,general,84713010,18,10.00,5,560001\n")
    largeCsv = "".join(rows)

    listings, result = ingestCsvContent(largeCsv, testMerchantDid)
    assert result.totalRowsProcessed == 500
    assert result.successCount == 500
    assert len(listings) == 500


def testCsvIngestionAdapterMalformedRowResilience() -> None:
    """Verifies empty content returns zeroed metrics and corrupted rows do not abort the batch."""
    emptyListings, emptyResult = ingestCsvContent("", testMerchantDid)
    assert emptyResult.totalRowsProcessed == 0
    assert emptyResult.successCount == 0
    assert emptyResult.failureCount == 0
    assert emptyListings == []

    whitespaceListings, whitespaceResult = ingestCsvContent("   \n\n  ", testMerchantDid)
    assert whitespaceResult.totalRowsProcessed == 0
    assert whitespaceListings == []

    corruptedCsv = (
        standardHeader
        + "SKU-CORRUPT-1,Bad Price,Desc,general,84713010,18,NOT_A_PRICE,10,560001\n"
        + "SKU-VALID-END,Good Item,Desc,general,84713010,18,50.00,10,560001\n"
    )
    listings, result = ingestCsvContent(corruptedCsv, testMerchantDid)
    assert result.totalRowsProcessed == 2
    assert result.successCount == 1
    assert result.failureCount == 1
    assert listings[0].skuId == "SKU-VALID-END"
