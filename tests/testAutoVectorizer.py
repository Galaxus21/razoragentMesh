"""Unit test suite for facet text synthesis and vector descriptor generation."""

from decimal import Decimal
import pytest

from razoragentMesh.packages.merchantApi.src.catalog.autoVectorizer import (
    synthesizeFacetDescription,
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
    VolumeTier,
)

# Test constants
testMerchantDid: str = "did:razoragent:merchant:test001"
testOriginPincode: str = "560001"
goldRingWeightGrams: Decimal = Decimal("4.5")
maxAllowedDescriptionLength: int = 500
goldPurityCarat22: int = 22
paracetamolDosageMg500: int = 500


def testJewelryFacetDescriptionSynthesis() -> None:
    """Verifies synthesis of jewelry facet metadata including weight, hallmark, and HSN."""
    pricingRule = DynamicPricingRule(
        pricingType="FORMULA_SPOT_LINKED",
        oracleFeedSymbol=SupportedOracleFeedSymbol.GOLD_22K.value,
        netWeightGrams=goldRingWeightGrams,
        purityMultiplier=Decimal("0.9167"),
    )
    listing = UniversalProductListing(
        skuId="SKU-JEW-22K-001",
        merchantDid=testMerchantDid,
        title="22K Gold Handcrafted Ring",
        description="Authentic hallmarked gold ring",
        category="Jewelry",
        hsnCode="71131910",
        gstRatePercent=3,
        baseUnitPricePaise=3200000,
        availableStock=5,
        originPincode=testOriginPincode,
        jewelryFacet=JewelryFacet(
            purityCarat=22,
            grossWeightGrams=goldRingWeightGrams,
            hallmarkNumber="916",
            dynamicPricingRule=pricingRule,
        ),
    )
    description = synthesizeFacetDescription(listing)

    assert isinstance(description, str)
    assert len(description) > 0
    assert "Jewelry" in description
    assert "22K" in description or "22" in description
    assert "Gold" in description
    assert "71131910" in description
    assert "BIS Hallmark 916" in description


def testApparelFacetDescriptionSynthesis() -> None:
    """Verifies synthesis of apparel attributes including size, color, and fabric."""
    listing = UniversalProductListing(
        skuId="SKU-APP-KURTA-001",
        merchantDid=testMerchantDid,
        title="Handloom Cotton Kurta",
        description="Pure handspun cotton kurta",
        category="Apparel",
        hsnCode="61091000",
        gstRatePercent=5,
        baseUnitPricePaise=189900,
        availableStock=25,
        originPincode=testOriginPincode,
        apparelFacet=ApparelFacet(
            size="M",
            color="Navy Blue",
            fabric=["Cotton"],
            fitType="Regular",
            gender="M",
        ),
    )
    description = synthesizeFacetDescription(listing)

    assert "Apparel" in description
    assert "Cotton" in description or "cotton" in description.lower()
    assert "Size M" in description or "M" in description
    assert "Navy Blue" in description
    assert "HSN 61091000" in description


def testPharmaFacetDescriptionSynthesis() -> None:
    """Verifies synthesis of pharmaceutical ingredient, dosage, and regulatory schedule."""
    listing = UniversalProductListing(
        skuId="SKU-PHARM-PARA-001",
        merchantDid=testMerchantDid,
        title="Paracetamol 500mg Tablets",
        description="Antipyretic and analgesic formulation",
        category="Pharma",
        hsnCode="30049099",
        gstRatePercent=12,
        baseUnitPricePaise=4500,
        availableStock=200,
        originPincode=testOriginPincode,
        pharmaFacet=PharmaFacet(
            activeSalt="Paracetamol",
            dosageMg=paracetamolDosageMg500,
            schedule="Schedule H",
            prescriptionRequired=True,
        ),
    )
    description = synthesizeFacetDescription(listing)

    assert "Pharma" in description
    assert "Paracetamol" in description
    assert "Schedule H" in description
    assert "HSN 30049099" in description


def testFmcgFacetDescriptionSynthesis() -> None:
    """Verifies synthesis of FMCG allergen declarations and dietary attributes."""
    listing = UniversalProductListing(
        skuId="SKU-FMCG-OIL-001",
        merchantDid=testMerchantDid,
        title="Cold-Pressed Groundnut Oil 1L",
        description="100% natural cold pressed peanut oil",
        category="FMCG",
        hsnCode="15081000",
        gstRatePercent=5,
        baseUnitPricePaise=285000,
        availableStock=50,
        originPincode=testOriginPincode,
        fmcgFacet=FmcgFacet(
            allergens=["peanuts"],
            isVeg=True,
            shelfLifeDays=180,
        ),
    )
    description = synthesizeFacetDescription(listing)

    assert "FMCG" in description
    assert "peanuts" in description
    assert "Veg" in description
    assert "HSN 15081000" in description


def testGenericListingNoFacet() -> None:
    """Verifies fallback synthesis behavior when no specialized industry facets exist."""
    listing = UniversalProductListing(
        skuId="SKU-FURN-CHAIR-001",
        merchantDid=testMerchantDid,
        title="Ergonomic Mesh Office Chair",
        description="High-back office chair with lumbar adjustment",
        category="Furniture",
        hsnCode="94031000",
        gstRatePercent=18,
        baseUnitPricePaise=850000,
        availableStock=15,
        originPincode=testOriginPincode,
    )
    description = synthesizeFacetDescription(listing)

    assert "Furniture" in description
    assert "Ergonomic Mesh Office Chair" in description
    assert "HSN 94031000" in description


def testDescriptionLengthConstraint() -> None:
    """Verifies that synthesized text representations do not exceed maximum length bounds."""
    longTitle = "Premium Multi-Tier Enterprise Grade Modular Ergonomic Workstation"
    listing = UniversalProductListing(
        skuId="SKU-LONG-001",
        merchantDid=testMerchantDid,
        title=longTitle,
        description="Extended description for enterprise procurement",
        category="OfficeSupplies",
        hsnCode="94032010",
        gstRatePercent=18,
        baseUnitPricePaise=12500000,
        availableStock=10,
        originPincode=testOriginPincode,
        volumeTiers=[VolumeTier(minQuantity=10, discountBps=500)],
    )
    description = synthesizeFacetDescription(listing)

    assert len(description) <= maxAllowedDescriptionLength
