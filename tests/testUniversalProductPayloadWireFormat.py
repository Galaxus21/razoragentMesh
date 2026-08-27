"""Adversarial Wire-Format Verification for Merchant SKU Studio & UniversalProductListing.

Empirically tests that JSON payloads emitted by Next.js Merchant SKU Studio
strictly validate against Layer 4 Pydantic UniversalProductListing schemas.
"""

from decimal import Decimal
import json
import pytest
from pydantic import ValidationError

from razoragentMesh.packages.merchantApi.src.schemas.universalProductSchema import (
    ApparelFacet,
    FmcgFacet,
    JewelryFacet,
    PharmaFacet,
    UniversalProductListing,
    VolumeTier,
)
from razoragentMesh.packages.merchantApi.src.schemas.dynamicPricingSchema import (
    DynamicPricingRule,
)


class TestUniversalProductPayloadWireFormat:
    """Validates full compatibility between Frontend Studio payloads and Backend Schemas."""

    def test_default_jewelry_bullion_payload_validation(self) -> None:
        """TC-WIRE-01: Default 22K Gold bullion payload with formula pricing."""
        raw_json = json.dumps({
            "skuId": "SKU-LUX-001", "merchantDid": "did:razoragent:merchant:990a1b2c3d4e5f67",
            "title": "22K Gold Traditional Bridal Ring (10.5g)",
            "description": "BIS Hallmarked 916 Pure Gold Bridal Ring with ornate filigree pattern.",
            "category": "Jewelry", "hsnCode": "71131910", "gstRatePercent": 3,
            "baseUnitPricePaise": 8250000, "availableStock": 15, "originPincode": "560001",
            "currency": "INR", "minimumOrderQuantity": 1,
            "volumeTiers": [{"minQuantity": 5, "discountBps": 250}, {"minQuantity": 20, "discountBps": 500}],
            "jewelryFacet": {
                "purityCarat": 22, "grossWeightGrams": "10.5", "hallmarkNumber": "BIS-HM-916-2026-BLR",
                "dynamicPricingRule": {
                    "pricingType": "FORMULA_SPOT_LINKED", "oracleFeedSymbol": "MCX_GOLD_22K_INR_PER_GRAM",
                    "purityMultiplier": "0.9167", "netWeightGrams": "10.5", "makingChargesPaise": 250000,
                    "makingChargesType": "FIXED_PAISE", "stoneChargesPaise": 50000, "maxQuoteTtlSeconds": 60,
                },
            },
        })
        listing = UniversalProductListing.model_validate_json(raw_json)
        assert listing.skuId == "SKU-LUX-001" and listing.gstRatePercent == 3 and listing.baseUnitPricePaise == 8250000
        assert listing.jewelryFacet is not None and listing.jewelryFacet.grossWeightGrams == Decimal("10.5")
        assert listing.jewelryFacet.dynamicPricingRule is not None
        assert listing.jewelryFacet.dynamicPricingRule.pricingType == "FORMULA_SPOT_LINKED"
        assert listing.jewelryFacet.dynamicPricingRule.makingChargesPaise == 250000
        assert len(listing.volumeTiers) == 2


    def test_apparel_facet_payload_validation(self) -> None:
        """TC-WIRE-02: Apparel listing with size, color, fabric array, and unisex gender."""
        raw_json = json.dumps({
            "skuId": "SKU-APP-001",
            "merchantDid": "did:razoragent:merchant:990a1b2c3d4e5f67",
            "title": "Organic Cotton Crewneck T-Shirt",
            "description": "Premium 100% bio-washed organic cotton slim fit t-shirt.",
            "category": "Apparel",
            "hsnCode": "61091000",
            "gstRatePercent": 5,
            "baseUnitPricePaise": 99900,
            "availableStock": 250,
            "originPincode": "641601",
            "currency": "INR",
            "minimumOrderQuantity": 1,
            "volumeTiers": [
                {"minQuantity": 10, "discountBps": 1000},
                {"minQuantity": 50, "discountBps": 2000},
            ],
            "apparelFacet": {
                "size": "XL",
                "color": "Midnight Blue",
                "fabric": ["100% Organic Cotton", "Elastane"],
                "fitType": "Slim Fit",
                "gender": "UNISEX",
            },
        })

        listing = UniversalProductListing.model_validate_json(raw_json)
        assert listing.skuId == "SKU-APP-001"
        assert listing.apparelFacet is not None
        assert listing.apparelFacet.size == "XL"
        assert listing.apparelFacet.gender == "UNISEX"
        assert listing.apparelFacet.fabric == ["100% Organic Cotton", "Elastane"]
        assert listing.jewelryFacet is None
        assert listing.pharmaFacet is None
        assert listing.fmcgFacet is None

    def test_pharma_facet_payload_validation(self) -> None:
        """TC-WIRE-03: Pharma listing with active salt, dosageMg, and schedule."""
        raw_json = json.dumps({
            "skuId": "SKU-MED-500",
            "merchantDid": "did:razoragent:merchant:990a1b2c3d4e5f67",
            "title": "Paracetamol 650mg Tablets (Strip of 15)",
            "description": "Fast-acting analgesic and antipyretic tablets.",
            "category": "Pharma",
            "hsnCode": "30049099",
            "gstRatePercent": 12,
            "baseUnitPricePaise": 3500,
            "availableStock": 5000,
            "originPincode": "400001",
            "currency": "INR",
            "minimumOrderQuantity": 1,
            "volumeTiers": [],
            "pharmaFacet": {
                "activeSalt": "Paracetamol IP",
                "dosageMg": 650,
                "schedule": "Over the Counter",
                "prescriptionRequired": False,
            },
        })

        listing = UniversalProductListing.model_validate_json(raw_json)
        assert listing.skuId == "SKU-MED-500"
        assert listing.pharmaFacet is not None
        assert listing.pharmaFacet.activeSalt == "Paracetamol IP"
        assert listing.pharmaFacet.dosageMg == 650
        assert listing.pharmaFacet.prescriptionRequired is False

    def test_fmcg_facet_payload_validation(self) -> None:
        """TC-WIRE-04: FMCG packaged food with allergens, shelf-life, and FSSAI license."""
        raw_json = json.dumps({
            "skuId": "SKU-FMCG-HONEY-500",
            "merchantDid": "did:razoragent:merchant:990a1b2c3d4e5f67",
            "title": "Raw Organic Forest Honey (500g)",
            "description": "Unfiltered, unpasteurized pure wildflower forest honey.",
            "category": "FMCG",
            "hsnCode": "04090000",
            "gstRatePercent": 5,
            "baseUnitPricePaise": 45000,
            "availableStock": 120,
            "originPincode": "110001",
            "currency": "INR",
            "minimumOrderQuantity": 2,
            "volumeTiers": [
                {"minQuantity": 6, "discountBps": 500},
            ],
            "fmcgFacet": {
                "allergens": ["Pollen"],
                "shelfLifeDays": 730,
                "isVeg": True,
                "fssaiNumber": "10012011000123",
            },
        })

        listing = UniversalProductListing.model_validate_json(raw_json)
        assert listing.skuId == "SKU-FMCG-HONEY-500"
        assert listing.fmcgFacet is not None
        assert listing.fmcgFacet.fssaiNumber == "10012011000123"
        assert listing.fmcgFacet.isVeg is True
        assert listing.fmcgFacet.shelfLifeDays == 730

    def test_generic_product_without_facets(self) -> None:
        """TC-WIRE-05: Standard electronics product with no vertical facets."""
        raw_json = json.dumps({
            "skuId": "SKU-ELEC-USB-C",
            "merchantDid": "did:razoragent:merchant:990a1b2c3d4e5f67",
            "title": "Braided 100W USB-C Fast Charging Cable (2m)",
            "description": "High-durability nylon braided 100W PD 3.0 Type-C cable.",
            "category": "Electronics",
            "hsnCode": "85444299",
            "gstRatePercent": 18,
            "baseUnitPricePaise": 59900,
            "availableStock": 800,
            "originPincode": "560068",
            "currency": "INR",
            "minimumOrderQuantity": 1,
            "volumeTiers": [
                {"minQuantity": 5, "discountBps": 500},
                {"minQuantity": 25, "discountBps": 1200},
                {"minQuantity": 100, "discountBps": 2500},
            ],
        })

        listing = UniversalProductListing.model_validate_json(raw_json)
        assert listing.skuId == "SKU-ELEC-USB-C"
        assert listing.jewelryFacet is None
        assert listing.apparelFacet is None
        assert listing.pharmaFacet is None
        assert listing.fmcgFacet is None
        assert len(listing.volumeTiers) == 3

    def test_extra_forbidden_field_rejection(self) -> None:
        """TC-WIRE-06: Schema forbids unmapped fields (e.g. leaked selectedFacet)."""
        raw_json = json.dumps({
            "skuId": "SKU-INVALID-001",
            "merchantDid": "did:razoragent:merchant:990a1b2c3d4e5f67",
            "title": "Invalid SKU with Extra Field",
            "description": "Test description.",
            "category": "General",
            "hsnCode": "84713010",
            "gstRatePercent": 18,
            "baseUnitPricePaise": 10000,
            "availableStock": 10,
            "originPincode": "560001",
            "currency": "INR",
            "minimumOrderQuantity": 1,
            "volumeTiers": [],
            "selectedFacet": "jewelry",  # FORBIDDEN: Should not be in wire payload
        })

        with pytest.raises(ValidationError) as exc_info:
            UniversalProductListing.model_validate_json(raw_json)
        assert "extra_forbidden" in str(exc_info.value)
