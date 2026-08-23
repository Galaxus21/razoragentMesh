"""Unit test suite for MCX gold/silver dynamic spot-rate formula engine."""

from decimal import Decimal
import time
import pytest

from razoragentMesh.packages.merchantApi.src.catalog.pricingFormulaEngine import (
    StalePriceQuoteException,
    computeSpotLinkedQuote,
    verifyQuoteNotExpired,
)
from razoragentMesh.packages.merchantApi.src.catalog.spotRateOracle import (
    createInMemorySpotRateOracle,
    fallbackSpotRatesPerGramPaise,
)
from razoragentMesh.packages.merchantApi.src.schemas.dynamicPricingSchema import (
    DynamicPricingRule,
    SupportedOracleFeedSymbol,
)

# Valuation and weight constants
gold24kWeightFiveGrams: Decimal = Decimal("5.0")
gold22kWeightThreePointFiveGrams: Decimal = Decimal("3.5")
gold22kWeightThreeGrams: Decimal = Decimal("3.0")
silverWeightFiveHundredGrams: Decimal = Decimal("500.0")
purityMultiplierPure: Decimal = Decimal("1.0")
purityMultiplier22k: Decimal = Decimal("0.9167")
goldGstRatePercent: int = 3
defaultQuoteTtlSeconds: int = 60
fixedMakingChargesPaise: int = 45000
percentageMakingChargesBps: int = 1200
customSeedRatePaise: int = 500000
fixedStoneChargesZero: int = 0
fixedTimestamp: int = 1700000000


@pytest.mark.asyncio
async def testGold24kSpotLinkedQuoteCalculation() -> None:
    """Verifies 24K gold quote calculation with zero making charges."""
    oracle = createInMemorySpotRateOracle()
    rule = DynamicPricingRule(
        pricingType="FORMULA_SPOT_LINKED",
        oracleFeedSymbol=SupportedOracleFeedSymbol.GOLD_24K.value,
        netWeightGrams=gold24kWeightFiveGrams,
        purityMultiplier=purityMultiplierPure,
        makingChargesPaise=0,
        makingChargesType="FIXED_PAISE",
        stoneChargesPaise=fixedStoneChargesZero,
        maxQuoteTtlSeconds=defaultQuoteTtlSeconds,
    )
    quote = await computeSpotLinkedQuote(
        rule=rule,
        oracle=oracle,
        gstRatePercent=goldGstRatePercent,
        currentTimestamp=fixedTimestamp,
    )

    expectedGoldCost = int(gold24kWeightFiveGrams * Decimal("679500") * purityMultiplierPure)
    expectedGst = (expectedGoldCost * goldGstRatePercent) // 100
    expectedUnitPrice = expectedGoldCost + expectedGst

    assert quote.goldCostPaise == expectedGoldCost
    assert quote.gstPaise == expectedGst
    assert quote.unitPricePaise == expectedUnitPrice
    assert quote.expiresAtTimestamp == fixedTimestamp + defaultQuoteTtlSeconds
    assert isinstance(quote.unitPricePaise, int)


@pytest.mark.asyncio
async def testGold22kWithMakingChargesFixedPaise() -> None:
    """Verifies 22K gold quote with fixed paise making charges."""
    oracle = createInMemorySpotRateOracle()
    rule = DynamicPricingRule(
        pricingType="FORMULA_SPOT_LINKED",
        oracleFeedSymbol=SupportedOracleFeedSymbol.GOLD_24K.value,
        netWeightGrams=gold22kWeightThreePointFiveGrams,
        purityMultiplier=purityMultiplier22k,
        makingChargesPaise=fixedMakingChargesPaise,
        makingChargesType="FIXED_PAISE",
        stoneChargesPaise=fixedStoneChargesZero,
        maxQuoteTtlSeconds=defaultQuoteTtlSeconds,
    )
    quote = await computeSpotLinkedQuote(
        rule=rule,
        oracle=oracle,
        gstRatePercent=goldGstRatePercent,
        currentTimestamp=fixedTimestamp,
    )

    expectedGoldCost = int(gold22kWeightThreePointFiveGrams * Decimal("679500") * purityMultiplier22k)
    expectedTaxable = expectedGoldCost + fixedMakingChargesPaise
    expectedGst = (expectedTaxable * goldGstRatePercent) // 100
    expectedUnitPrice = expectedTaxable + expectedGst

    assert quote.goldCostPaise == expectedGoldCost
    assert quote.makingChargesPaise == fixedMakingChargesPaise
    assert quote.gstPaise == expectedGst
    assert quote.unitPricePaise == expectedUnitPrice
    assert isinstance(quote.unitPricePaise, int)


@pytest.mark.asyncio
async def testGold22kWithPercentageMakingCharges() -> None:
    """Verifies 22K gold quote with basis points percentage making charges."""
    oracle = createInMemorySpotRateOracle()
    rule = DynamicPricingRule(
        pricingType="FORMULA_SPOT_LINKED",
        oracleFeedSymbol=SupportedOracleFeedSymbol.GOLD_24K.value,
        netWeightGrams=gold22kWeightThreeGrams,
        purityMultiplier=purityMultiplier22k,
        makingChargesPaise=percentageMakingChargesBps,
        makingChargesType="PERCENTAGE_OF_GOLD",
        stoneChargesPaise=fixedStoneChargesZero,
        maxQuoteTtlSeconds=defaultQuoteTtlSeconds,
    )
    quote = await computeSpotLinkedQuote(
        rule=rule,
        oracle=oracle,
        gstRatePercent=goldGstRatePercent,
        currentTimestamp=fixedTimestamp,
    )

    expectedGoldCost = int(gold22kWeightThreeGrams * Decimal("679500") * purityMultiplier22k)
    expectedMakingCharges = (expectedGoldCost * percentageMakingChargesBps) // 10000

    assert quote.goldCostPaise == expectedGoldCost
    assert quote.makingChargesPaise == expectedMakingCharges
    assert isinstance(quote.unitPricePaise, int)


@pytest.mark.asyncio
async def testSilverQuoteCalculation() -> None:
    """Verifies silver commodity quote calculation using MCX silver feed."""
    oracle = createInMemorySpotRateOracle()
    rule = DynamicPricingRule(
        pricingType="FORMULA_SPOT_LINKED",
        oracleFeedSymbol=SupportedOracleFeedSymbol.SILVER.value,
        netWeightGrams=silverWeightFiveHundredGrams,
        purityMultiplier=purityMultiplierPure,
        makingChargesPaise=0,
        makingChargesType="FIXED_PAISE",
        stoneChargesPaise=fixedStoneChargesZero,
        maxQuoteTtlSeconds=defaultQuoteTtlSeconds,
    )
    quote = await computeSpotLinkedQuote(
        rule=rule,
        oracle=oracle,
        gstRatePercent=goldGstRatePercent,
        currentTimestamp=fixedTimestamp,
    )

    silverSpotRate = fallbackSpotRatesPerGramPaise[SupportedOracleFeedSymbol.SILVER.value]
    expectedSilverCost = int(silverWeightFiveHundredGrams * Decimal(str(silverSpotRate)) * purityMultiplierPure)
    expectedGst = (expectedSilverCost * goldGstRatePercent) // 100

    assert quote.goldCostPaise == expectedSilverCost
    assert quote.unitPricePaise == expectedSilverCost + expectedGst
    assert isinstance(quote.unitPricePaise, int)


def testQuoteExpiryNotExpired() -> None:
    """Verifies that non-expired timestamps pass validation."""
    currentTime = int(time.time())
    verifyQuoteNotExpired(
        expiresAtTimestamp=currentTime + defaultQuoteTtlSeconds,
        currentTimestamp=currentTime,
    )


def testQuoteExpiryRaisesOnStaleQuote() -> None:
    """Verifies that stale quotations trigger StalePriceQuoteException."""
    currentTime = int(time.time())
    with pytest.raises(StalePriceQuoteException):
        verifyQuoteNotExpired(
            expiresAtTimestamp=currentTime - 1,
            currentTimestamp=currentTime,
        )


@pytest.mark.asyncio
async def testInMemoryOracleSeeding() -> None:
    """Verifies seeding and retrieving custom spot rates from in-memory oracle."""
    oracle = createInMemorySpotRateOracle()
    await oracle.seedFallbackRate(SupportedOracleFeedSymbol.GOLD_24K.value, customSeedRatePaise)
    retrievedRate = await oracle.getSpotRatePerGramPaise(SupportedOracleFeedSymbol.GOLD_24K.value)
    assert retrievedRate == customSeedRatePaise
