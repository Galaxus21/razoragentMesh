"""Unit tests for merchantApi constants, HSN directory, and schemas."""

from decimal import Decimal
import pytest
from pydantic import ValidationError

from razoragentMesh.packages.merchantApi import (
    ApparelFacet,
    CsvIngestResult,
    CsvIngestRow,
    DynamicPricingRule,
    ErpBatchSyncRequest,
    ErpBatchSyncResult,
    FmcgFacet,
    JewelryFacet,
    MerchantKeypairRecord,
    MerchantProfile,
    MerchantRegistrationRequest,
    NegotiationPolicy,
    PharmaFacet,
    ShopifyWebhookPayload,
    SupportedOracleFeedSymbol,
    UniversalProductListing,
    VolumeTier,
    catalogUpdateActionAdded,
    catalogUpdateActionRemoved,
    catalogUpdateActionUpdated,
    defaultGstRatePercent,
    defaultQuoteTtlSeconds,
    gstinRegexPattern,
    hsnCodeDirectory,
    hsnCodeMaxLength,
    hsnCodeMinLength,
    hsnPrefixLength,
    jewelryGstRatePercent,
    maxCsvRowsPerBatch,
    maxSkuDescriptionLength,
    maxSkuTitleLength,
    merchantApiDefaultPort,
    pinCodeRegexPattern,
    razorpayRouteAccountPrefix,
    redisCatalogHashKeyPrefix,
    redisCatalogUpdatesChannel,
    redisMerchantPolicyKeyPrefix,
    redisSpotRateKeyPrefix,
    resolveGstRate,
    spotRateTtlSeconds,
    zeroRatedGstPercent,
)


def testConstantsExportedValues() -> None:
    """Verify all merchant constants have correct types and values."""
    assert merchantApiDefaultPort == 4002
    assert redisCatalogHashKeyPrefix == "mesh:catalog:"
    assert redisMerchantPolicyKeyPrefix == "mesh:merchant:policy:"
    assert redisCatalogUpdatesChannel == "mesh:catalog:updates"
    assert redisSpotRateKeyPrefix == "mesh:oracle:spot:"
    assert spotRateTtlSeconds == 5
    assert defaultQuoteTtlSeconds == 60
    assert hsnCodeMinLength == 4
    assert hsnCodeMaxLength == 8
    assert maxCsvRowsPerBatch == 500
    assert maxSkuTitleLength == 150
    assert maxSkuDescriptionLength == 500
    assert razorpayRouteAccountPrefix == "acc_"
    assert catalogUpdateActionAdded == "CATALOG_ITEM_ADDED"
    assert catalogUpdateActionUpdated == "CATALOG_ITEM_UPDATED"
    assert catalogUpdateActionRemoved == "CATALOG_ITEM_REMOVED"
    assert defaultGstRatePercent == 18
    assert zeroRatedGstPercent == 0
    assert jewelryGstRatePercent == 3
    assert hsnPrefixLength == 4


def testResolveGstRate() -> None:
    """Test HSN GST rate resolution logic."""
    assert resolveGstRate("71131910") == 3
    assert resolveGstRate("84713010") == 18
    assert resolveGstRate("04012000") == 0
    assert resolveGstRate("30049099") == 12
    assert resolveGstRate("99999999") == 18  # fallback
    assert resolveGstRate("12") == 18  # short code fallback
    assert resolveGstRate("") == 18  # empty fallback


def testDynamicPricingRuleSchema() -> None:
    """Test dynamic spot pricing schema validation and immutability."""
    rule = DynamicPricingRule(
        pricingType="FORMULA_SPOT_LINKED",
        oracleFeedSymbol=SupportedOracleFeedSymbol.GOLD_24K.value,
        purityMultiplier=Decimal("0.9167"),
        netWeightGrams=Decimal("10.5"),
        makingChargesPaise=50000,
        makingChargesType="FIXED_PAISE",
        stoneChargesPaise=10000,
        maxQuoteTtlSeconds=60,
    )
    assert rule.pricingType == "FORMULA_SPOT_LINKED"
    assert rule.purityMultiplier == Decimal("0.9167")
    assert rule.makingChargesPaise == 50000

    # Immutability
    with pytest.raises(ValidationError):
        rule.makingChargesPaise = 60000  # type: ignore[misc]

    # Extra forbid
    with pytest.raises(ValidationError):
        DynamicPricingRule(extraField=123)  # type: ignore[call-arg]


def testUniversalProductListingWithFacets() -> None:
    """Test UniversalProductListing with various facets."""
    volumeTiers = [
        VolumeTier(minQuantity=10, discountBps=500),
        VolumeTier(minQuantity=50, discountBps=1000),
    ]

    jewelryFacet = JewelryFacet(
        purityCarat=22,
        grossWeightGrams=Decimal("12.50"),
        hallmarkNumber="BIS-HM-998877",
        dynamicPricingRule=DynamicPricingRule(
            pricingType="FORMULA_SPOT_LINKED",
            oracleFeedSymbol=SupportedOracleFeedSymbol.GOLD_22K.value,
        ),
    )

    apparelFacet = ApparelFacet(
        size="XL",
        color="Navy Blue",
        fabric=["cotton", "linen"],
        fitType="slim",
        gender="M",
    )

    pharmaFacet = PharmaFacet(
        activeSalt="Paracetamol",
        dosageMg=650,
        schedule="OTC",
        prescriptionRequired=False,
    )

    fmcgFacet = FmcgFacet(
        allergens=["peanuts"],
        shelfLifeDays=180,
        isVeg=True,
        fssaiNumber="10012345678901",
    )

    listing = UniversalProductListing(
        skuId="SKU-GOLD-RING-001",
        merchantDid="did:razoragent:merchant:abcdef123456",
        title="22K Gold Handcrafted Ring",
        description="Authentic hallmarked gold ring with high polish finish.",
        category="Jewelry",
        hsnCode="71131910",
        gstRatePercent=3,
        baseUnitPricePaise=8500000,
        availableStock=5,
        originPincode="560001",
        volumeTiers=volumeTiers,
        minimumOrderQuantity=1,
        jewelryFacet=jewelryFacet,
        apparelFacet=apparelFacet,
        pharmaFacet=pharmaFacet,
        fmcgFacet=fmcgFacet,
    )

    assert listing.skuId == "SKU-GOLD-RING-001"
    assert listing.gstRatePercent == 3
    assert len(listing.volumeTiers) == 2
    assert listing.jewelryFacet is not None
    assert listing.jewelryFacet.purityCarat == 22


def testMerchantRegistrationAndProfile() -> None:
    """Test merchant onboarding request and public profile schemas."""
    req = MerchantRegistrationRequest(
        businessName="Acme Enterprises Pvt Ltd",
        gstin="29ABCDE1234F1Z5",
        razorpayAccountId="acc_test123456",
        contactEmail="ops@acme.in",
        originPincode="560001",
    )
    assert req.businessName == "Acme Enterprises Pvt Ltd"
    assert req.razorpayAccountId == "acc_test123456"

    # Invalid GSTIN
    with pytest.raises(ValidationError):
        MerchantRegistrationRequest(
            businessName="Acme",
            gstin="INVALID_GSTIN",
            razorpayAccountId="acc_123",
            contactEmail="ops@acme.in",
            originPincode="560001",
        )

    # Invalid Razorpay Account Id (missing acc_ prefix)
    with pytest.raises(ValidationError):
        MerchantRegistrationRequest(
            businessName="Acme",
            gstin="29ABCDE1234F1Z5",
            razorpayAccountId="merchant_123",
            contactEmail="ops@acme.in",
            originPincode="560001",
        )

    # Invalid Pincode
    with pytest.raises(ValidationError):
        MerchantRegistrationRequest(
            businessName="Acme",
            gstin="29ABCDE1234F1Z5",
            razorpayAccountId="acc_123",
            contactEmail="ops@acme.in",
            originPincode="060001",  # Starts with 0
        )

    profile = MerchantProfile(
        merchantDid="did:razoragent:merchant:123456",
        publicKeyHex="0123456789abcdef",
        businessName="Acme Enterprises Pvt Ltd",
        gstin="29ABCDE1234F1Z5",
        razorpayAccountId="acc_test123456",
        contactEmail="ops@acme.in",
        originPincode="560001",
        registeredAtTimestamp=1700000000,
    )
    assert profile.merchantDid == "did:razoragent:merchant:123456"

    keypair = MerchantKeypairRecord(
        merchantDid="did:razoragent:merchant:123456",
        publicKeyHex="0123456789abcdef",
        privateKeyHex="fedcba9876543210",
        registeredAtTimestamp=1700000000,
    )
    assert keypair.privateKeyHex == "fedcba9876543210"


def testBulkIngestSchemas() -> None:
    """Test CSV row, Shopify webhook, and ERP sync schemas."""
    csvRow = CsvIngestRow(
        skuId="SKU-101",
        title="Cotton Shirt",
        category="Apparel",
        description="100% pure cotton formal shirt",
        hsnCode="6109",
        basePriceInr="1499.00",
        availableStock=50,
        moq=1,
        originPincode="560001",
    )
    assert csvRow.skuId == "SKU-101"
    assert csvRow.basePriceInr == "1499.00"

    csvResult = CsvIngestResult(
        totalRowsProcessed=10,
        successCount=9,
        failureCount=1,
        failedSkuIds=["SKU-999"],
    )
    assert csvResult.totalRowsProcessed == 10

    shopifyPayload = ShopifyWebhookPayload(
        id=987654321,
        title="Shopify Item",
        body_html="<p>Item description</p>",
        variants=[{"id": 1, "price": "100.00"}],
        extraCustomField="allowed_in_shopify",
    )
    assert shopifyPayload.id == 987654321

    erpReq = ErpBatchSyncRequest(
        merchantDid="did:razoragent:merchant:123",
        batchId="batch-001",
        deltas=[{"skuId": "SKU-101", "stockDelta": -5}],
    )
    assert erpReq.batchId == "batch-001"

    erpRes = ErpBatchSyncResult(
        batchId="batch-001",
        appliedCount=1,
        rejectedCount=0,
        rejectedSkuIds=[],
    )
    assert erpRes.appliedCount == 1


def testNegotiationPolicySchema() -> None:
    """Test merchant negotiation policy bounds and defaults."""
    policy = NegotiationPolicy(
        merchantDid="did:razoragent:merchant:123",
        marginFloorBps=800,
        minimumOrderQuantity=2,
        autoAcceptSpreadPaise=100,
        maxNegotiationTurns=6,
        createdAtTimestamp=1700000000,
        updatedAtTimestamp=1700000000,
    )
    assert policy.marginFloorBps == 800
    assert policy.maxNegotiationTurns == 6

    # Invalid marginFloorBps (> 10000)
    with pytest.raises(ValidationError):
        NegotiationPolicy(
            merchantDid="did:razoragent:merchant:123",
            marginFloorBps=15000,
            createdAtTimestamp=1700000000,
            updatedAtTimestamp=1700000000,
        )
