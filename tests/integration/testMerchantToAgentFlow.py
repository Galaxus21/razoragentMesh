"""Integration test suite verifying merchant onboarding, discovery, and A2A procurement pipelines."""

from decimal import Decimal
import time
import pytest

from razoragentMesh.packages.mandateEngine.verification.arithmeticEnclave import (
    computeTotalPaise,
)
from razoragentMesh.packages.merchantApi.src.adapters.csvIngestionAdapter import (
    ingestCsvContent,
)
from razoragentMesh.packages.merchantApi.src.catalog.hsnTaxResolver import (
    resolveHsnGstRate,
)
from razoragentMesh.packages.merchantApi.src.catalog.priceNormalizer import (
    normalizeInrToPaise,
)
from razoragentMesh.packages.merchantApi.src.catalog.pricingFormulaEngine import (
    computeSpotLinkedQuote,
    verifyQuoteNotExpired,
)
from razoragentMesh.packages.merchantApi.src.catalog.spotRateOracle import (
    createInMemorySpotRateOracle,
    fallbackSpotRatesPerGramPaise,
)
from razoragentMesh.packages.merchantApi.src.onboarding.merchantRegistrar import (
    buildMerchantProfile,
    generateMerchantKeypair,
    validateGstin,
)
from razoragentMesh.packages.merchantApi.src.schemas.dynamicPricingSchema import (
    DynamicPricingRule,
    SupportedOracleFeedSymbol,
)
from razoragentMesh.packages.merchantApi.src.schemas.merchantSchema import (
    MerchantRegistrationRequest,
)
from razoragentMesh.packages.merchantApi.src.schemas.universalProductSchema import (
    FmcgFacet,
    JewelryFacet,
    UniversalProductListing,
    VolumeTier,
)

# Test domain and persona constants
validFmcgGstin: str = "27AAPFU0939F1ZV"
validB2bGstin: str = "29AAAAA0000A1ZY"
testPincodeMumbai: str = "400001"
testPincodeBengaluru: str = "560001"
chairBasePricePaise: int = 420000
chairHsnCode: str = "9403"
chairVolumeDiscountBps: int = 500
orderQuantityTwo: int = 2
goldWeightThreePointFiveGrams: Decimal = Decimal("3.5")
goldFixedMakingChargesPaise: int = 45000
goldGstPercent: int = 3
quoteTtlSecs: int = 60


def testD2CBrandFmcgOnboardingAndDiscovery() -> None:
    """Verifies D2C FMCG brand merchant onboarding and CSV ingestion with allergen facets."""
    assert validateGstin(validFmcgGstin) is True

    registrationReq = MerchantRegistrationRequest(
        businessName="FarmPure Organics Pvt Ltd",
        gstin=validFmcgGstin,
        razorpayAccountId="acc_farmpure123456",
        contactEmail="contact@farmpure.in",
        originPincode=testPincodeMumbai,
    )
    keypair = generateMerchantKeypair(registrationReq)
    profile = buildMerchantProfile(registrationReq, keypair)

    assert profile.merchantDid.startswith("did:razoragent:merchant:")
    assert profile.businessName == "FarmPure Organics Pvt Ltd"

    csvContent = (
        "skuId,title,description,category,brand,hsnCode,gstRatePercent,basePriceInr,availableStock,originPincode,allergens,volumeTiersJson\n"
        'SKU-FMCG-01,FarmPure Groundnut Oil 1L,Cold pressed virgin oil,fmcg,FarmPure,1508,5,2850.00,100,400001,peanuts,"[{""minQuantity"": 10, ""discountBps"": 300}]"\n'
        "SKU-FMCG-02,FarmPure Coconut Oil 500ml,Pure coconut oil,fmcg,FarmPure,1513,5,450.00,50,400001,tree_nuts,\n"
    )
    listings, ingestResult = ingestCsvContent(csvContent, profile.merchantDid)

    assert ingestResult.successCount == 2
    assert ingestResult.failureCount == 0
    assert len(listings) == 2

    assert normalizeInrToPaise("2850.00") == 285000
    firstListing = listings[0]
    assert firstListing.fmcgFacet is not None
    assert "peanuts" in firstListing.fmcgFacet.allergens


def testB2BWholesaleErgocomfortNegotiation() -> None:
    """Verifies B2B wholesale merchant setup, HSN tax resolution, and tier discount computation."""
    assert validateGstin(validB2bGstin) is True

    registrationReq = MerchantRegistrationRequest(
        businessName="ErgoComfort Seating Ltd",
        gstin=validB2bGstin,
        razorpayAccountId="acc_ergocomfort123",
        contactEmail="sales@ergocomfort.in",
        originPincode=testPincodeBengaluru,
    )
    keypair = generateMerchantKeypair(registrationReq)
    profile = buildMerchantProfile(registrationReq, keypair)

    chairListing = UniversalProductListing(
        skuId="SKU-CHAIR-B2B-01",
        merchantDid=profile.merchantDid,
        title="ErgoComfort High-Back Mesh Chair",
        description="Ergonomic high-back office chair with adjustable armrests",
        category="Furniture",
        hsnCode=chairHsnCode,
        gstRatePercent=18,
        baseUnitPricePaise=chairBasePricePaise,
        availableStock=100,
        originPincode=testPincodeBengaluru,
        volumeTiers=[VolumeTier(minQuantity=10, discountBps=chairVolumeDiscountBps)],
    )

    resolvedGst = resolveHsnGstRate(chairHsnCode)
    assert resolvedGst == 18

    discountPaise = (chairListing.baseUnitPricePaise * chairVolumeDiscountBps) // 10000
    effectiveUnitPricePaise = chairListing.baseUnitPricePaise - discountPaise
    assert discountPaise == 21000
    assert effectiveUnitPricePaise == 399000


@pytest.mark.asyncio
async def testJewelrySpotLinkedMandatePipeline() -> None:
    """Verifies jewelry dynamic pricing linked to spot oracle and exact paise mandate math."""
    pricingRule = DynamicPricingRule(
        pricingType="FORMULA_SPOT_LINKED",
        oracleFeedSymbol=SupportedOracleFeedSymbol.GOLD_22K.value,
        netWeightGrams=goldWeightThreePointFiveGrams,
        purityMultiplier=Decimal("1.0"),
        makingChargesPaise=goldFixedMakingChargesPaise,
        makingChargesType="FIXED_PAISE",
        stoneChargesPaise=0,
        maxQuoteTtlSeconds=quoteTtlSecs,
    )

    oracle = createInMemorySpotRateOracle()
    currentTime = int(time.time())
    quote = await computeSpotLinkedQuote(
        rule=pricingRule,
        oracle=oracle,
        gstRatePercent=goldGstPercent,
        currentTimestamp=currentTime,
    )

    assert quote.unitPricePaise > 0
    assert isinstance(quote.unitPricePaise, int)
    assert quote.expiresAtTimestamp > currentTime
    verifyQuoteNotExpired(quote.expiresAtTimestamp, currentTime)

    totalPaise = computeTotalPaise(quote.unitPricePaise, orderQuantityTwo)
    expectedTotal = quote.unitPricePaise * orderQuantityTwo
    assert totalPaise == expectedTotal
    assert isinstance(totalPaise, int)
