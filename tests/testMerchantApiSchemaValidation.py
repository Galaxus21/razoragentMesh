"""Unit tests for merchantApi schema validation, adversarial bounds, and promotions."""

from decimal import Decimal
import pytest
from pydantic import ValidationError

from razoragentMesh.packages.merchantApi import (
    FmcgFacet,
    JewelryFacet,
    MerchantKeypairRecord,
    MerchantProfile,
    MerchantRegistrationRequest,
    PharmaFacet,
    ScheduledPromotionSchema,
    VolumeTier,
)
from razoragentMesh.packages.vectorHealer.src.constraints.negativeManifestSchema import (
    NegativeConstraintManifest,
)
from razoragentMesh.packages.vectorHealer.src.constraints.constraintFilter import (
    NegativeConstraintFilter,
)


def testMerchantRegistrationValidation() -> None:
    """Test merchant onboarding request validation."""
    req = MerchantRegistrationRequest(
        businessName="Acme Enterprises Pvt Ltd", gstin="29ABCDE1234F1ZW",
        razorpayAccountId="acc_test123456", contactEmail="ops@acme.in", originPincode="560001",
    )
    assert req.businessName == "Acme Enterprises Pvt Ltd" and req.razorpayAccountId == "acc_test123456"

    with pytest.raises(ValidationError):
        MerchantRegistrationRequest(
            businessName="Acme", gstin="INVALID_GSTIN", razorpayAccountId="acc_123",
            contactEmail="ops@acme.in", originPincode="560001",
        )
    with pytest.raises(ValidationError):
        MerchantRegistrationRequest(
            businessName="Acme", gstin="29ABCDE1234F1ZW", razorpayAccountId="merchant_123",
            contactEmail="ops@acme.in", originPincode="560001",
        )
    with pytest.raises(ValidationError):
        MerchantRegistrationRequest(
            businessName="Acme", gstin="29ABCDE1234F1ZW", razorpayAccountId="acc_123",
            contactEmail="ops@acme.in", originPincode="060001",
        )


def testMerchantProfileAndKeypairRecords() -> None:
    """Test merchant public profile and keypair record schemas."""
    profile = MerchantProfile(
        merchantDid="did:razoragent:merchant:123456", publicKeyHex="0123456789abcdef",
        businessName="Acme Enterprises Pvt Ltd", gstin="29ABCDE1234F1ZW",
        razorpayAccountId="acc_test123456", contactEmail="ops@acme.in",
        originPincode="560001", registeredAtTimestamp=1700000000,
    )
    assert profile.merchantDid == "did:razoragent:merchant:123456"

    keypair = MerchantKeypairRecord(
        merchantDid="did:razoragent:merchant:123456", publicKeyHex="0123456789abcdef",
        privateKeyHex="fedcba9876543210", registeredAtTimestamp=1700000000,
    )
    assert keypair.privateKeyHex == "fedcba9876543210"


def testFacetAdversarialBounds() -> None:
    """Test adversarial and boundary conditions for polymorphic domain facets."""
    with pytest.raises(ValidationError):
        JewelryFacet(purityCarat=14, grossWeightGrams=Decimal("10.0"))  # type: ignore[arg-type]

    with pytest.raises(ValidationError):
        JewelryFacet(purityCarat=22, grossWeightGrams=Decimal("0.001"))

    with pytest.raises(ValidationError):
        PharmaFacet(activeSalt="Paracetamol", dosageMg=-10)

    with pytest.raises(ValidationError):
        FmcgFacet(shelfLifeDays=0)

    with pytest.raises(ValidationError):
        VolumeTier(minQuantity=5, discountBps=15000)

    with pytest.raises(ValidationError):
        VolumeTier(minQuantity=0, discountBps=500)


def testMultiIndustryNegativeConstraintFilter() -> None:
    """Test material, active pharma salt, OTC, and veg negative constraint filtering."""
    manifest = NegativeConstraintManifest(
        excludedMaterials=["polyester", "leather"], excludedActiveSalts=["pseudoephedrine"],
        requireOtcOnly=True, requireVeg=True,
    )
    cFilter = NegativeConstraintFilter(manifest)

    res1 = cFilter.evaluateCandidate({"skuId": "SKU-SHIRT-01", "apparelFacet": {"fabric": ["cotton", "polyester"]}})
    assert not res1.isAllowed and res1.rejectionReason == "MATERIAL_EXCLUDED:polyester"

    res2 = cFilter.evaluateCandidate({"skuId": "SKU-COLD-01", "pharmaFacet": {"activeSalt": "Pseudoephedrine HCl", "prescriptionRequired": False}})
    assert not res2.isAllowed and res2.rejectionReason == "ACTIVE_SALT_EXCLUDED:pseudoephedrine"

    res3 = cFilter.evaluateCandidate({"skuId": "SKU-RX-01", "pharmaFacet": {"activeSalt": "Amoxicillin", "prescriptionRequired": True}})
    assert not res3.isAllowed and res3.rejectionReason == "PRESCRIPTION_REQUIRED_BREACH"

    res4 = cFilter.evaluateCandidate({"skuId": "SKU-FOOD-01", "fmcgFacet": {"isVeg": False, "allergens": []}})
    assert not res4.isAllowed and res4.rejectionReason == "NON_VEG_EXCLUDED"

    res5 = cFilter.evaluateCandidate({
        "skuId": "SKU-ORGANIC-01", "apparelFacet": {"fabric": ["100% organic cotton"]},
        "fmcgFacet": {"isVeg": True, "allergens": []}, "pharmaFacet": {"activeSalt": "Paracetamol", "prescriptionRequired": False},
    })
    assert res5.isAllowed and res5.rejectionReason is None


def testScheduledPromotionSchemaValid() -> None:
    """Test valid ScheduledPromotionSchema instances."""
    promoBps = ScheduledPromotionSchema(
        campaignId="CAMPAIGN-01", name="Flash Sale 30%", startsAtUnix=1700000000,
        endsAtUnix=1700100000, discountBps=3000,
    )
    assert promoBps.campaignId == "CAMPAIGN-01" and promoBps.discountBps == 3000 and promoBps.discountPaise is None

    promoPaise = ScheduledPromotionSchema(
        campaignId="CAMPAIGN-02", name="Flat 500 Off", startsAtUnix=1700000000,
        endsAtUnix=1700050000, discountPaise=50000,
    )
    assert promoPaise.discountPaise == 50000

    promoFixed = ScheduledPromotionSchema(
        campaignId="CAMPAIGN-03", name="Special Price 3500", startsAtUnix=1700000000,
        endsAtUnix=1700080000, fixedPricePaise=350000, limitedStockAllocated=10,
    )
    assert promoFixed.fixedPricePaise == 350000 and promoFixed.limitedStockAllocated == 10


def testScheduledPromotionSchemaInvariantsAndImmutability() -> None:
    """Test validation errors and immutability for ScheduledPromotionSchema."""
    promoBps = ScheduledPromotionSchema(
        campaignId="CAMPAIGN-01", name="Flash Sale 30%", startsAtUnix=1700000000,
        endsAtUnix=1700100000, discountBps=3000,
    )

    with pytest.raises(ValidationError):
        ScheduledPromotionSchema(campaignId="ERR-1", name="Invalid", startsAtUnix=1700000000, endsAtUnix=1700000000, discountBps=1000)
    with pytest.raises(ValidationError):
        ScheduledPromotionSchema(campaignId="ERR-2", name="Inverted", startsAtUnix=1700100000, endsAtUnix=1700000000, discountBps=1000)
    with pytest.raises(ValidationError):
        ScheduledPromotionSchema(campaignId="ERR-3", name="No Discount", startsAtUnix=1700000000, endsAtUnix=1700100000)
    with pytest.raises(ValidationError):
        ScheduledPromotionSchema(campaignId="ERR-4", name="Extra", startsAtUnix=1700000000, endsAtUnix=1700100000, discountBps=1000, extraProp="bad")  # type: ignore[call-arg]
    with pytest.raises(ValidationError):
        ScheduledPromotionSchema(campaignId="ERR-5", name="Excessive", startsAtUnix=1700000000, endsAtUnix=1700100000, discountBps=15000)

    with pytest.raises(ValidationError):
        promoBps.discountBps = 2000  # type: ignore[misc]
