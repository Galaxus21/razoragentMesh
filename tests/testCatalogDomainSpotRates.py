"""Unit test suite for merchantApi spot rates, pricing formulas, and normalizers."""

from decimal import Decimal
import pytest
import pytest_asyncio

from razoragentMesh.packages.merchantApi import (
    ArithmeticDriftException,
    DynamicPricingRule,
    SpotLinkedQuote,
    SpotRateOracle,
    StalePriceQuoteException,
    computeSpotLinkedQuote,
    createInMemorySpotRateOracle,
    fallbackSpotRatesPerGramPaise,
    normalizeInrToPaise,
    resolveHsnGstRate,
    validateHsnCode,
    verifyQuoteNotExpired,
)
from razoragentMesh.tests.mockInfraHelpers import MockRedisAsync


@pytest_asyncio.fixture
async def mockRedis() -> MockRedisAsync:
    client = MockRedisAsync()
    yield client
    await client.flushdb()


@pytest.mark.asyncio
async def testSpotRateOracleFallbackRates(mockRedis: MockRedisAsync) -> None:
    oracle = SpotRateOracle(redisClient=mockRedis)
    rate24k = await oracle.getSpotRatePerGramPaise("MCX_GOLD_24K_INR_PER_GRAM")
    assert rate24k == fallbackSpotRatesPerGramPaise["MCX_GOLD_24K_INR_PER_GRAM"]

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


@pytest.mark.asyncio
async def testComputeSpotLinkedQuote24k() -> None:
    oracle = createInMemorySpotRateOracle()
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
        rule=rule, oracle=oracle, gstRatePercent=3, currentTimestamp=1700000000,
    )
    assert quote.goldCostPaise == 6795000
    assert quote.makingChargesPaise == 543600
    assert quote.stoneChargesPaise == 50000
    assert quote.gstPaise == 221658
    assert quote.unitPricePaise == 7388600 + 221658
    assert quote.expiresAtTimestamp == 1700000000 + 300
    assert isinstance(quote.unitPricePaise, int)


@pytest.mark.asyncio
async def testComputeSpotLinkedQuote22kFixedCharges() -> None:
    oracle = createInMemorySpotRateOracle()
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
        rule=rule, oracle=oracle, gstRatePercent=3, currentTimestamp=1700000000,
    )
    expectedGoldCost = int(Decimal("5.4") * Decimal("679500") * Decimal("0.916"))
    assert quote.goldCostPaise == expectedGoldCost
    assert quote.makingChargesPaise == 150000
    assert quote.stoneChargesPaise == 0


def testVerifyQuoteNotExpired() -> None:
    verifyQuoteNotExpired(expiresAtTimestamp=1700000300, currentTimestamp=1700000100)

    with pytest.raises(StalePriceQuoteException) as excInfo:
        verifyQuoteNotExpired(expiresAtTimestamp=1700000000, currentTimestamp=1700000050)
    assert excInfo.value.deltaMs == 50000


def testValidateHsnCode() -> None:
    assert validateHsnCode("7113") is True
    assert validateHsnCode("61091000") is True
    assert validateHsnCode("300490") is True
    assert validateHsnCode("123") is False
    assert validateHsnCode("123456789") is False
    assert validateHsnCode("711A") is False
    assert validateHsnCode(None) is False  # type: ignore


def testResolveHsnGstRate() -> None:
    assert resolveHsnGstRate("71131900") == 3
    assert resolveHsnGstRate("61091000") == 5
    assert resolveHsnGstRate("6203") == 12
    assert resolveHsnGstRate("30049099") == 12
    assert resolveHsnGstRate("15081000") == 5
    assert resolveHsnGstRate("84713010") == 18

    with pytest.raises(ValueError, match="Malformed Indian HSN code"):
        resolveHsnGstRate("ABC123")


def testNormalizeInrToPaiseValid() -> None:
    assert normalizeInrToPaise("4200.00") == 420000
    assert normalizeInrToPaise("4200") == 420000
    assert normalizeInrToPaise(Decimal("4200.50")) == 420050
    assert normalizeInrToPaise(4200) == 420000
    assert normalizeInrToPaise("0.05") == 5


def testNormalizeInrToPaiseRejections() -> None:
    with pytest.raises(ArithmeticDriftException, match="Floating-point values are strictly forbidden"):
        normalizeInrToPaise(4200.50)  # type: ignore

    with pytest.raises(ArithmeticDriftException, match="Negative financial amounts"):
        normalizeInrToPaise("-100.00")

    with pytest.raises(ArithmeticDriftException, match="Failed to parse numeric string"):
        normalizeInrToPaise("invalid_money")
