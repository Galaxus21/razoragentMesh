"""Adversarial stress-test suite for AutoVectorizer and Pricing Formula Engine."""

from decimal import Decimal
import math
import pytest

from razoragentMesh.packages.merchantApi.src.catalog.autoVectorizer import (
    AutoVectorizer,
    _EmbeddingEngine,
    synthesizeFacetDescription,
)
from razoragentMesh.packages.merchantApi.src.catalog.pricingFormulaEngine import (
    SpotLinkedQuote,
    StalePriceQuoteException,
    computeSpotLinkedQuote,
    verifyQuoteNotExpired,
)
from razoragentMesh.packages.merchantApi.src.catalog.spotRateOracle import (
    createInMemorySpotRateOracle,
)
from razoragentMesh.packages.merchantApi.src.schemas.dynamicPricingSchema import (
    DynamicPricingRule,
    SupportedOracleFeedSymbol,
)
from razoragentMesh.packages.merchantApi.src.schemas.universalProductSchema import (
    ApparelFacet,
    FmcgFacet,
    JewelryFacet,
    PharmaFacet,
    UniversalProductListing,
)
from razoragentMesh.tests.mockInfraHelpers import MockQdrantClient

testMerchantDid = "did:razoragent:merchant:adv002"
testPincode = "560001"


# ---------------------------------------------------------------------------
# AutoVectorizer and Facet Synthesis Adversarial Tests
# ---------------------------------------------------------------------------


def testSparseListingFacetSynthesis() -> None:
    """Verifies synthesis gracefully handles listing with zero domain facets and minimal metadata."""
    sparseListing = UniversalProductListing(
        skuId="SKU-SPARSE-001",
        merchantDid=testMerchantDid,
        title="Minimal Widget",
        description="",
        category="General",
        hsnCode="9999",
        gstRatePercent=18,
        baseUnitPricePaise=1000,
        availableStock=10,
        originPincode=testPincode,
    )
    desc = synthesizeFacetDescription(sparseListing)
    assert desc == "General | Minimal Widget | HSN 9999"


def testMultiIndustrySimultaneousFacetSynthesis() -> None:
    """Verifies that listings with multiple vertical facets synthesize all fragments deterministically."""
    richListing = UniversalProductListing(
        skuId="SKU-RICH-001",
        merchantDid=testMerchantDid,
        title="Luxury Ayurvedic Gold Cream",
        description="Ayurvedic cosmetic with pure 24K gold dust",
        category="Cosmetics",
        hsnCode="33049910",
        gstRatePercent=18,
        baseUnitPricePaise=500000,
        availableStock=100,
        originPincode=testPincode,
        jewelryFacet=JewelryFacet(
            purityCarat=24,
            grossWeightGrams=Decimal("0.5"),
            hallmarkNumber="BIS-999",
        ),
        apparelFacet=ApparelFacet(size="50ml", color="Gold", fabric=["Jar"]),
        fmcgFacet=FmcgFacet(allergens=["Saffron"], isVeg=True, shelfLifeDays=365),
        pharmaFacet=PharmaFacet(activeSalt="Swarna Bhasma", dosageMg=50, prescriptionRequired=False),
    )
    desc = synthesizeFacetDescription(richListing)
    assert "Cosmetics" in desc
    assert "Luxury Ayurvedic Gold Cream" in desc
    assert "Gross 0.5g" in desc
    assert "BIS-999" in desc
    assert "Size 50ml" in desc
    assert "Allergens: Saffron" in desc
    assert "Veg" in desc
    assert "Active: Swarna Bhasma" in desc
    assert "HSN 33049910" in desc


def testEmbeddingEngineVectorProperties() -> None:
    """Verifies that embedding engine produces 384-dim normalized L2 unit vectors."""
    engine = _EmbeddingEngine()
    v1 = engine.embed("Organic Cotton T-Shirt")
    v2 = engine.embed("Organic Cotton T-Shirt")
    assert len(v1) == 384
    assert v1 == v2
    normSq = sum(x * x for x in v1)
    assert math.isclose(normSq, 1.0, rel_tol=1e-5)


@pytest.mark.asyncio
async def testAutoVectorizerUpsertReplacement() -> None:
    """Verifies that repeated upserts for the same SKU ID replace the existing vector point."""
    mockQdrant = MockQdrantClient()
    mockQdrant.createCollection("merchantCatalog")
    vectorizer = AutoVectorizer(qdrantClient=mockQdrant, collectionName="merchantCatalog")

    listing1 = UniversalProductListing(
        skuId="SKU-REPLACE-01",
        merchantDid=testMerchantDid,
        title="Title Version 1",
        description="Desc 1",
        category="General",
        hsnCode="8471",
        gstRatePercent=18,
        baseUnitPricePaise=10000,
        availableStock=5,
        originPincode=testPincode,
    )
    await vectorizer.upsertListing(listing1)
    pts = mockQdrant.collections["merchantCatalog"]
    assert len(pts) == 1
    assert pts[0]["payload"]["title"] == "Title Version 1"

    listing2 = UniversalProductListing(
        skuId="SKU-REPLACE-01",
        merchantDid=testMerchantDid,
        title="Title Version 2 Updated",
        description="Desc 2",
        category="General",
        hsnCode="8471",
        gstRatePercent=18,
        baseUnitPricePaise=12000,
        availableStock=0,
        originPincode=testPincode,
    )
    await vectorizer.upsertListing(listing2)
    ptsAfter = mockQdrant.collections["merchantCatalog"]
    assert len(ptsAfter) == 1
    assert ptsAfter[0]["payload"]["title"] == "Title Version 2 Updated"
    assert ptsAfter[0]["payload"]["availableStock"] == 0


@pytest.mark.asyncio
async def testAutoVectorizerRemoveListing() -> None:
    """Verifies removal of vector and metadata point from Qdrant by SKU ID."""
    mockQdrant = MockQdrantClient()
    mockQdrant.createCollection("merchantCatalog")
    vectorizer = AutoVectorizer(qdrantClient=mockQdrant, collectionName="merchantCatalog")

    listing = UniversalProductListing(
        skuId="SKU-DELETE-01",
        merchantDid=testMerchantDid,
        title="Item to delete",
        description="Desc",
        category="General",
        hsnCode="8471",
        gstRatePercent=18,
        baseUnitPricePaise=10000,
        availableStock=5,
        originPincode=testPincode,
    )
    await vectorizer.upsertListing(listing)
    assert len(mockQdrant.collections["merchantCatalog"]) == 1

    await vectorizer.removeListing("SKU-DELETE-01")
    assert len(mockQdrant.collections["merchantCatalog"]) == 0


# ---------------------------------------------------------------------------
# Pricing Formula Engine Adversarial Tests
# ---------------------------------------------------------------------------


@pytest.mark.asyncio
async def testPricingFormulaEngineZeroWeightBoundary() -> None:
    """Verifies zero net weight yields zero gold cost and correct flat charges."""
    oracle = createInMemorySpotRateOracle()
    rule = DynamicPricingRule(
        pricingType="FORMULA_SPOT_LINKED",
        oracleFeedSymbol=SupportedOracleFeedSymbol.GOLD_24K.value,
        netWeightGrams=Decimal("0.0"),
        purityMultiplier=Decimal("1.0"),
        makingChargesPaise=5000,
        makingChargesType="FIXED_PAISE",
        stoneChargesPaise=1000,
        maxQuoteTtlSeconds=60,
    )
    quote = await computeSpotLinkedQuote(
        rule=rule,
        oracle=oracle,
        gstRatePercent=3,
        currentTimestamp=1700000000,
    )
    assert quote.goldCostPaise == 0
    assert quote.makingChargesPaise == 5000
    assert quote.stoneChargesPaise == 1000
    assert quote.gstPaise == 180
    assert quote.unitPricePaise == 6180


@pytest.mark.asyncio
async def testPricingFormulaEngineBpsMakingCharges() -> None:
    """Verifies making charges computed via PERCENTAGE_OF_GOLD basis points."""
    oracle = createInMemorySpotRateOracle()
    rule = DynamicPricingRule(
        pricingType="FORMULA_SPOT_LINKED",
        oracleFeedSymbol=SupportedOracleFeedSymbol.GOLD_24K.value,
        netWeightGrams=Decimal("10.0"),
        purityMultiplier=Decimal("1.0"),
        makingChargesType="PERCENTAGE_OF_GOLD",
        makingChargesPaise=1500,  # 15% (1500 bps)
        stoneChargesPaise=0,
        maxQuoteTtlSeconds=120,
    )
    quote = await computeSpotLinkedQuote(
        rule=rule,
        oracle=oracle,
        gstRatePercent=3,
        currentTimestamp=1700000000,
    )
    expectedGoldCost = 6795000
    expectedMaking = (6795000 * 1500) // 10000
    assert quote.goldCostPaise == expectedGoldCost
    assert quote.makingChargesPaise == expectedMaking
    expectedTaxable = expectedGoldCost + expectedMaking
    expectedGst = (expectedTaxable * 3) // 100
    assert quote.gstPaise == expectedGst
    assert quote.unitPricePaise == expectedTaxable + expectedGst


def testStaleQuoteVerificationMillisecondDelta() -> None:
    """Verifies timestamp staleness raises StalePriceQuoteException with exact delta."""
    verifyQuoteNotExpired(expiresAtTimestamp=1700000100, currentTimestamp=1700000100)

    with pytest.raises(StalePriceQuoteException) as excInfo:
        verifyQuoteNotExpired(expiresAtTimestamp=1700000100, currentTimestamp=1700000110)
    assert excInfo.value.deltaMs == 10000
