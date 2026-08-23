"""Unit test suite for merchantApi catalog domain logic layer."""

from decimal import Decimal
import pytest
import pytest_asyncio

from razoragentMesh.packages.merchantApi import (
    ApparelFacet,
    ArithmeticDriftException,
    AutoVectorizer,
    CatalogManager,
    DynamicPricingRule,
    FmcgFacet,
    JewelryFacet,
    PharmaFacet,
    QdrantPayloadPatcher,
    SpotLinkedQuote,
    SpotRateOracle,
    StalePriceQuoteException,
    SupportedOracleFeedSymbol,
    UniversalProductListing,
    computeSpotLinkedQuote,
    createInMemorySpotRateOracle,
    fallbackSpotRatesPerGramPaise,
    normalizeInrToPaise,
    resolveGstRate,
    resolveHsnGstRate,
    synthesizeFacetDescription,
    validateHsnCode,
    verifyQuoteNotExpired,
)
from razoragentMesh.tests.mockInfraHelpers import MockQdrantClient, MockRedisAsync


@pytest.fixture
def mockQdrant() -> MockQdrantClient:
    client = MockQdrantClient()
    client.createCollection("merchantCatalog")
    return client


@pytest_asyncio.fixture
async def mockRedis() -> MockRedisAsync:
    client = MockRedisAsync()
    yield client
    await client.flushdb()


# ---------------------------------------------------------------------------
# Test SpotRateOracle
# ---------------------------------------------------------------------------


@pytest.mark.asyncio
async def testSpotRateOracleFallbackRates(mockRedis: MockRedisAsync) -> None:
    oracle = SpotRateOracle(redisClient=mockRedis)
    rate24k = await oracle.getSpotRatePerGramPaise(
        "MCX_GOLD_24K_INR_PER_GRAM"
    )
    assert rate24k == fallbackSpotRatesPerGramPaise["MCX_GOLD_24K_INR_PER_GRAM"]

    # Verify cached in Redis
    cachedRate = await mockRedis.get("mesh:oracle:spot:MCX_GOLD_24K_INR_PER_GRAM")
    assert cachedRate == str(rate24k)


@pytest.mark.asyncio
async def testSpotRateOracleSeedCustomRate(mockRedis: MockRedisAsync) -> None:
    oracle = SpotRateOracle(redisClient=mockRedis)
    customRate = 700000
    await oracle.seedFallbackRate("MCX_GOLD_24K_INR_PER_GRAM", customRate)
    fetchedRate = await oracle.getSpotRatePerGramPaise("MCX_GOLD_24K_INR_PER_GRAM")
    assert fetchedRate == customRate


@pytest.mark.asyncio
async def testSpotRateOracleUnsupportedSymbol(mockRedis: MockRedisAsync) -> None:
    oracle = SpotRateOracle(redisClient=mockRedis)
    with pytest.raises(ValueError, match="Unsupported oracle feed symbol"):
        await oracle.getSpotRatePerGramPaise("MCX_PLATINUM_INR_PER_GRAM")


@pytest.mark.asyncio
async def testInMemorySpotRateOracleFactory() -> None:
    customSeeds = {"MCX_GOLD_24K_INR_PER_GRAM": 685000}
    oracle = createInMemorySpotRateOracle(seedRates=customSeeds)
    rate = await oracle.getSpotRatePerGramPaise("MCX_GOLD_24K_INR_PER_GRAM")
    assert rate == 685000


# ---------------------------------------------------------------------------
# Test PricingFormulaEngine
# ---------------------------------------------------------------------------


@pytest.mark.asyncio
async def testComputeSpotLinkedQuote24k() -> None:
    oracle = createInMemorySpotRateOracle()
    # 10 grams 24K gold, 8% making charges (800 bps), 3% GST (HSN 7113)
    rule = DynamicPricingRule(
        pricingType="FORMULA_SPOT_LINKED",
        oracleFeedSymbol="MCX_GOLD_24K_INR_PER_GRAM",
        netWeightGrams=Decimal("10.0"),
        purityMultiplier=Decimal("1.0"),
        makingChargesPaise=800,
        makingChargesType="PERCENTAGE_OF_GOLD",
        stoneChargesPaise=50000,
        maxQuoteTtlSeconds=300,
    )
    quote = await computeSpotLinkedQuote(
        rule=rule,
        oracle=oracle,
        gstRatePercent=3,
        currentTimestamp=1700000000,
    )
    # Spot rate = 679500 paise/gram -> 10g = 6,795,000 paise
    assert quote.goldCostPaise == 6795000
    # Making charges = 6795000 * 800 // 10000 = 543,600 paise
    assert quote.makingChargesPaise == 543600
    assert quote.stoneChargesPaise == 50000
    # Taxable = 6795000 + 543600 + 50000 = 7,388,600 paise
    # GST = 7388600 * 3 // 100 = 221,658 paise
    assert quote.gstPaise == 221658
    assert quote.unitPricePaise == 7388600 + 221658
    assert quote.expiresAtTimestamp == 1700000000 + 300
    assert isinstance(quote.unitPricePaise, int)


@pytest.mark.asyncio
async def testComputeSpotLinkedQuote22kFixedCharges() -> None:
    oracle = createInMemorySpotRateOracle()
    # 5.4 grams 22K gold (purity 0.916), fixed making charges 150000 paise, stone charges 0
    rule = DynamicPricingRule(
        pricingType="FORMULA_SPOT_LINKED",
        oracleFeedSymbol="MCX_GOLD_24K_INR_PER_GRAM",
        netWeightGrams=Decimal("5.4"),
        purityMultiplier=Decimal("0.916"),
        makingChargesPaise=150000,
        makingChargesType="FIXED_PAISE",
        stoneChargesPaise=0,
    )
    quote = await computeSpotLinkedQuote(
        rule=rule,
        oracle=oracle,
        gstRatePercent=3,
        currentTimestamp=1700000000,
    )
    expectedGoldCost = int(Decimal("5.4") * Decimal("679500") * Decimal("0.916"))
    assert quote.goldCostPaise == expectedGoldCost
    assert quote.makingChargesPaise == 150000
    assert quote.stoneChargesPaise == 0


def testVerifyQuoteNotExpired() -> None:
    # Not expired
    verifyQuoteNotExpired(expiresAtTimestamp=1700000300, currentTimestamp=1700000100)

    # Expired raises StalePriceQuoteException
    with pytest.raises(StalePriceQuoteException) as excInfo:
        verifyQuoteNotExpired(expiresAtTimestamp=1700000000, currentTimestamp=1700000050)
    assert excInfo.value.deltaMs == 50000


# ---------------------------------------------------------------------------
# Test HsnTaxResolver
# ---------------------------------------------------------------------------


def testValidateHsnCode() -> None:
    assert validateHsnCode("7113") is True
    assert validateHsnCode("61091000") is True
    assert validateHsnCode("300490") is True

    assert validateHsnCode("123") is False
    assert validateHsnCode("123456789") is False
    assert validateHsnCode("711A") is False
    assert validateHsnCode(None) is False  # type: ignore


def testResolveHsnGstRate() -> None:
    assert resolveHsnGstRate("71131900") == 3  # Jewelry
    assert resolveHsnGstRate("61091000") == 5  # T-shirts
    assert resolveHsnGstRate("6203") == 12     # Suits
    assert resolveHsnGstRate("30049099") == 12 # Pharma
    assert resolveHsnGstRate("15081000") == 5  # Edible oil
    assert resolveHsnGstRate("84713010") == 18 # Computing (default/mapped)

    with pytest.raises(ValueError, match="Malformed Indian HSN code"):
        resolveHsnGstRate("ABC123")


# ---------------------------------------------------------------------------
# Test PriceNormalizer
# ---------------------------------------------------------------------------


def testNormalizeInrToPaiseValid() -> None:
    assert normalizeInrToPaise("4200.00") == 420000
    assert normalizeInrToPaise("4200") == 420000
    assert normalizeInrToPaise(Decimal("4200.50")) == 420050
    assert normalizeInrToPaise(4200) == 420000
    assert normalizeInrToPaise("0.05") == 5


def testNormalizeInrToPaiseRejectsFloat() -> None:
    with pytest.raises(ArithmeticDriftException, match="Floating-point values are strictly forbidden"):
        normalizeInrToPaise(4200.50)  # type: ignore


def testNormalizeInrToPaiseRejectsNegative() -> None:
    with pytest.raises(ArithmeticDriftException, match="Negative financial amounts"):
        normalizeInrToPaise("-100.00")


def testNormalizeInrToPaiseRejectsInvalidString() -> None:
    with pytest.raises(ArithmeticDriftException, match="Failed to parse numeric string"):
        normalizeInrToPaise("invalid_money")


# ---------------------------------------------------------------------------
# Test CatalogManager
# ---------------------------------------------------------------------------


@pytest.mark.asyncio
async def testCatalogManagerLifecycle(mockRedis: MockRedisAsync) -> None:
    manager = CatalogManager(redisClient=mockRedis)

    listing = UniversalProductListing(
        skuId="SKU-GOLD-RING-01",
        merchantDid="did:mesh:merchant_tanishq_01",
        title="22K Gold Floral Ring",
        description="Floral design 22K gold ring",
        category="Jewelry",
        hsnCode="71131900",
        gstRatePercent=3,
        baseUnitPricePaise=4500000,
        availableStock=10,
        originPincode="560001",
        jewelryFacet=JewelryFacet(
            purityCarat=22,
            grossWeightGrams=Decimal("5.4"),
            hallmarkNumber="916",
        ),
    )

    # Upsert SKU
    await manager.upsertSku(listing)

    # Get SKU
    retrieved = await manager.getSku("SKU-GOLD-RING-01")
    assert retrieved is not None
    assert retrieved.skuId == "SKU-GOLD-RING-01"
    assert retrieved.title == "22K Gold Floral Ring"
    assert retrieved.gstRatePercent == 3

    # List merchant SKUs
    merchantSkus = await manager.listMerchantSkus("did:mesh:merchant_tanishq_01")
    assert "SKU-GOLD-RING-01" in merchantSkus

    # Remove SKU
    removed = await manager.removeSku("SKU-GOLD-RING-01", "did:mesh:merchant_tanishq_01")
    assert removed is True

    # Confirm removal
    assert await manager.getSku("SKU-GOLD-RING-01") is None


# ---------------------------------------------------------------------------
# Test QdrantPayloadPatcher
# ---------------------------------------------------------------------------


@pytest.mark.asyncio
async def testQdrantPayloadPatcher(mockQdrant: MockQdrantClient) -> None:
    mockQdrant.upsert("merchantCatalog", [
        {
            "id": "SKU-RING-01",
            "vector": [0.1] * 384,
            "payload": {"skuId": "SKU-RING-01", "isAvailable": True},
        },
        {
            "id": "SKU-RING-02",
            "vector": [0.2] * 384,
            "payload": {"skuId": "SKU-RING-02", "isAvailable": True},
        },
    ])

    patcher = QdrantPayloadPatcher(qdrantClient=mockQdrant, collectionName="merchantCatalog")

    # Set single SKU availability to False
    await patcher.setAvailability("SKU-RING-01", isAvailable=False)
    pts = mockQdrant.collections["merchantCatalog"]
    pt1 = next(p for p in pts if p["id"] == "SKU-RING-01")
    assert pt1["payload"]["isAvailable"] is False

    # Batch update SKUs
    await patcher.batchSetAvailability(["SKU-RING-01", "SKU-RING-02"], isAvailable=True)
    assert pt1["payload"]["isAvailable"] is True
    pt2 = next(p for p in pts if p["id"] == "SKU-RING-02")
    assert pt2["payload"]["isAvailable"] is True


# ---------------------------------------------------------------------------
# Test AutoVectorizer and Facet Synthesizer
# ---------------------------------------------------------------------------


def testSynthesizeFacetDescription() -> None:
    jewelryListing = UniversalProductListing(
        skuId="SKU-JEW-01",
        merchantDid="did:mesh:m1",
        title="Tanishq 22K Gold Ring",
        description="Authentic hallmark gold ring",
        category="Jewelry",
        hsnCode="7113",
        gstRatePercent=3,
        baseUnitPricePaise=3600000,
        availableStock=5,
        originPincode="560001",
        jewelryFacet=JewelryFacet(
            purityCarat=22,
            grossWeightGrams=Decimal("5.4"),
            hallmarkNumber="916",
        ),
    )
    desc1 = synthesizeFacetDescription(jewelryListing)
    assert "Jewelry" in desc1
    assert "Tanishq 22K Gold Ring" in desc1
    assert "Gross 5.4g" in desc1
    assert "BIS Hallmark 916" in desc1
    assert "HSN 7113" in desc1

    apparelListing = UniversalProductListing(
        skuId="SKU-APP-01",
        merchantDid="did:mesh:m2",
        title="FabIndia Cotton Kurta",
        description="Pure cotton handcrafted kurta",
        category="Apparel",
        hsnCode="6109",
        gstRatePercent=5,
        baseUnitPricePaise=199900,
        availableStock=20,
        originPincode="110001",
        apparelFacet=ApparelFacet(
            size="M",
            color="Navy Blue",
            fabric=["Cotton"],
        ),
    )
    desc2 = synthesizeFacetDescription(apparelListing)
    assert desc2 == "Apparel | FabIndia Cotton Kurta | Size M | Navy Blue | Fabric: Cotton | HSN 6109"

    pharmaListing = UniversalProductListing(
        skuId="SKU-PHARM-01",
        merchantDid="did:mesh:m3",
        title="Crocin 500mg",
        description="Paracetamol tablet 500mg",
        category="Pharma",
        hsnCode="3004",
        gstRatePercent=12,
        baseUnitPricePaise=5000,
        availableStock=100,
        originPincode="400001",
        pharmaFacet=PharmaFacet(
            activeSalt="Paracetamol",
            dosageMg=500,
            schedule="Schedule H",
        ),
    )
    desc3 = synthesizeFacetDescription(pharmaListing)
    assert desc3 == "Pharma | Crocin 500mg | Active: Paracetamol | Schedule H | HSN 3004"

    fmcgListing = UniversalProductListing(
        skuId="SKU-OIL-01",
        merchantDid="did:mesh:m4",
        title="FarmPure Groundnut Oil 15L",
        description="Cold pressed virgin groundnut oil",
        category="FMCG",
        hsnCode="1508",
        gstRatePercent=5,
        baseUnitPricePaise=280000,
        availableStock=15,
        originPincode="380001",
        fmcgFacet=FmcgFacet(
            allergens=["Peanuts"],
            isVeg=True,
        ),
    )
    desc4 = synthesizeFacetDescription(fmcgListing)
    assert desc4 == "FMCG | FarmPure Groundnut Oil 15L | Allergens: Peanuts | Veg | HSN 1508"


@pytest.mark.asyncio
async def testAutoVectorizerUpsertAndRemove(mockQdrant: MockQdrantClient) -> None:
    vectorizer = AutoVectorizer(qdrantClient=mockQdrant, collectionName="merchantCatalog")

    listing = UniversalProductListing(
        skuId="SKU-JEW-02",
        merchantDid="did:mesh:m1",
        title="MMTC-PAMP 24K Gold Coin 10g",
        description="999.9 pure gold coin",
        category="Jewelry",
        hsnCode="7114",
        gstRatePercent=3,
        baseUnitPricePaise=6800000,
        availableStock=8,
        originPincode="122001",
        jewelryFacet=JewelryFacet(
            purityCarat=24,
            grossWeightGrams=Decimal("10.0"),
            hallmarkNumber="9999",
        ),
    )

    await vectorizer.upsertListing(listing)

    # Verify point is in Qdrant collection
    pts = mockQdrant.collections["merchantCatalog"]
    assert len(pts) == 1
    assert pts[0]["id"] == "SKU-JEW-02"
    assert len(pts[0]["vector"]) == 384
    assert pts[0]["payload"]["skuId"] == "SKU-JEW-02"
    assert pts[0]["payload"]["isAvailable"] is True
    assert pts[0]["payload"]["gstRatePercent"] == 3

    # Remove listing
    await vectorizer.removeListing("SKU-JEW-02")
    ptsAfter = mockQdrant.collections["merchantCatalog"]
    assert len(ptsAfter) == 0
