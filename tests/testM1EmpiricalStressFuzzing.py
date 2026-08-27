"""Empirical randomized fuzzing and stress harness for Milestone 1 modules."""

from decimal import Decimal
import random
import pytest

from razoragentMesh.packages.catalogSanitizer import (
    InvalidSkuIdentifierException,
    SchemaSanitizationFailureException,
    cleanAndTruncateText,
    sanitizeMerchantSkuQuote,
)
from razoragentMesh.packages.mandateEngine.settlement.settlementExceptions import (
    ArithmeticDriftException,
)
from razoragentMesh.packages.merchantApi.src.adapters.csvIngestionAdapter import (
    ingestCsvContent,
    parseCsvRow,
)
from razoragentMesh.packages.merchantApi.src.catalog.pricingFormulaEngine import (
    computeSpotLinkedQuote,
)
from razoragentMesh.packages.merchantApi.src.catalog.spotRateOracle import (
    createInMemorySpotRateOracle,
)
from razoragentMesh.packages.merchantApi.src.schemas.dynamicPricingSchema import (
    DynamicPricingRule,
    SupportedOracleFeedSymbol,
)

testMerchantDid = "did:razoragent:merchant:stress01"


# ---------------------------------------------------------------------------
# Stress Harness 1: Catalog Sanitizer Fuzzing
# ---------------------------------------------------------------------------


def _buildFuzzQuotePayload(idx: int, corruptType: str) -> dict:
    """Helper to synthesize fuzzed quote payload with specific mutation strategy."""
    zeroWidthPool = ["\u200b", "\u200c", "\u200d", "\ufeff"]
    ansiPool = ["\x1b[31m", "\x1b[0m"]
    markupPool = ["<script>alert(1)</script>", "[link](http://evil.com)"]
    titleJunk = "".join(random.choices(zeroWidthPool + ansiPool + markupPool, k=2))
    cgst, sgst = random.randint(0, 5000), random.randint(0, 5000)
    totalTax = cgst + sgst if corruptType != "tax_drift" else (cgst + sgst + 10)

    return {
        "skuId": f"SKU-FUZZ-{idx:03d}" if corruptType != "bad_sku" else "INVALID_NO_PREFIX",
        "title": f"Fuzzed Product {titleJunk}",
        "description": f"Description with {titleJunk}",
        "availableStock": random.randint(0, 100) if corruptType != "bool_stock" else True,
        "baseUnitPricePaise": random.randint(100, 100000) if corruptType != "float_price" else 99.99,
        "offeredUnitPricePaise": random.randint(100, 100000),
        "hsnCode": "84821010",
        "gstRatePercent": 18,
        "taxBreakdown": {"cgstPaise": cgst, "sgstPaise": sgst, "igstPaise": 0, "totalTaxPaise": totalTax},
        "quoteExpiryTimestamp": 1780000000,
        "quoteHash": "f" * 64,
    }


def testSanitizerAdversarialFuzzingHarness() -> None:
    """Fuzzes sanitizer with 100 randomized corrupted payloads asserting fault isolation."""
    random.seed(42)
    corruptOptions = ["valid", "bad_sku", "float_price", "bool_stock", "tax_drift", "corrupt_markup"]

    for i in range(100):
        corruptType = random.choice(corruptOptions)
        rawPayload = _buildFuzzQuotePayload(i, corruptType)

        if corruptType in ("valid", "corrupt_markup"):
            quote = sanitizeMerchantSkuQuote(rawPayload)
            assert quote.skuId == f"SKU-FUZZ-{i:03d}"
            assert "\u200b" not in quote.title and "\x1b" not in quote.description
        elif corruptType == "bad_sku":
            with pytest.raises(InvalidSkuIdentifierException):
                sanitizeMerchantSkuQuote(rawPayload)
        elif corruptType in ("float_price", "bool_stock"):
            with pytest.raises(SchemaSanitizationFailureException):
                sanitizeMerchantSkuQuote(rawPayload)
        elif corruptType == "tax_drift":
            with pytest.raises(ArithmeticDriftException):
                sanitizeMerchantSkuQuote(rawPayload)


# ---------------------------------------------------------------------------
# Stress Harness 2: CSV Batch Parsing Fuzzing
# ---------------------------------------------------------------------------


def testCsvIngestionStressHarness() -> None:
    """Fuzzes CSV ingestion with 100 random rows including malformed lines and asserts batch isolation."""
    random.seed(1337)
    rows = ["skuId,title,basePriceInr,availableStock,hsnCode,category"]

    for i in range(100):
        isCorrupt = random.choice([False, False, True])
        if isCorrupt:
            corruptVariant = random.choice(["empty_sku", "empty_title", "bad_price", "negative_price"])
            if corruptVariant == "empty_sku":
                rows.append(f",Item {i},100.00,10,8471,general")
            elif corruptVariant == "empty_title":
                rows.append(f"SKU-FUZZ-{i},,100.00,10,8471,general")
            elif corruptVariant == "bad_price":
                rows.append(f"SKU-FUZZ-{i},Item {i},ABC,10,8471,general")
            elif corruptVariant == "negative_price":
                rows.append(f"SKU-FUZZ-{i},Item {i},-50.00,10,8471,general")
        else:
            price = f"{random.randint(10, 5000)}.{random.randint(0, 99):02d}"
            rows.append(f"SKU-FUZZ-{i},Valid Item {i},{price},{random.randint(1, 50)},8471,general")

    csvContent = "\n".join(rows)
    listings, result = ingestCsvContent(csvContent, merchantDid=testMerchantDid)
    assert result.totalRowsProcessed == 100
    assert result.successCount + result.failureCount == 100
    assert len(listings) == result.successCount
    assert len(result.failedSkuIds) == result.failureCount


# ---------------------------------------------------------------------------
# Stress Harness 3: Pricing Formula Engine Fuzzing
# ---------------------------------------------------------------------------


@pytest.mark.asyncio
async def testPricingFormulaEngineStressInvariants() -> None:
    """Fuzzes pricing formula engine across 50 random combinations asserting mathematical invariants."""
    random.seed(999)
    oracle = createInMemorySpotRateOracle()

    for _ in range(50):
        weight = Decimal(str(round(random.uniform(0.1, 500.0), 3)))
        purity = Decimal(str(random.choice([0.750, 0.916, 0.999, 1.0])))
        rule = DynamicPricingRule(
            pricingType="FORMULA_SPOT_LINKED",
            oracleFeedSymbol=SupportedOracleFeedSymbol.GOLD_24K.value,
            netWeightGrams=weight,
            purityMultiplier=purity,
            makingChargesPaise=random.randint(0, 100000),
            makingChargesType=random.choice(["FIXED_PAISE", "PERCENTAGE_OF_GOLD"]),
            stoneChargesPaise=random.randint(0, 50000),
            maxQuoteTtlSeconds=60,
        )
        quote = await computeSpotLinkedQuote(
            rule=rule,
            oracle=oracle,
            gstRatePercent=random.choice([0, 3, 5, 12, 18, 28]),
            currentTimestamp=1700000000,
        )
        # Verify INV-01, INV-02, INV-03, INV-04
        assert isinstance(quote.unitPricePaise, int) and quote.unitPricePaise >= 0
        taxable = quote.goldCostPaise + quote.makingChargesPaise + quote.stoneChargesPaise
        assert quote.unitPricePaise == taxable + quote.gstPaise
