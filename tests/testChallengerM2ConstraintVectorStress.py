"""Empirical Challenger M2 Stress Suite for ConstraintFilter and VectorSearcher."""

from typing import Any, Dict, List
import pytest

from razoragentMesh.packages.vectorHealer.src.constraints import (
    NegativeConstraintFilter,
    NegativeConstraintManifest,
)
from razoragentMesh.packages.vectorHealer.src.search.vectorSearcher import (
    VectorSearcher,
)


def testConstraintFilterAllergensAndBrands() -> None:
    """Verifies complex allergen, casing, substring, and brand exclusions."""
    manifest = NegativeConstraintManifest(
        excludedAllergens=["peanut", "soy"],
        excludedBrands=["UnwantedBrand"],
    )
    cf = NegativeConstraintFilter(manifest)

    # 1. Complex allergen in fmcgFacet
    itemFmcg = {
        "skuId": "SKU-FMCG-01",
        "brand": "PureBrand",
        "fmcgFacet": {"allergens": ["  De-fatted SOY Flour  "]},
        "attributes": {"weightGrams": 500, "slaHours": 12},
    }
    res = cf.evaluateCandidate(itemFmcg)
    assert not res.isAllowed
    assert "ALLERGEN_BREACH:soy" in res.rejectionReason

    # 2. Excluded brand
    itemBrand = {
        "skuId": "SKU-BRAND-01",
        "brand": "  UNWANTEDBRAND  ",
        "attributes": {"weightGrams": 500, "slaHours": 12},
    }
    resBrand = cf.evaluateCandidate(itemBrand)
    assert not resBrand.isAllowed
    assert "BRAND_EXCLUDED:unwantedbrand" in resBrand.rejectionReason


def testConstraintFilterFabricsSaltsAndOtc() -> None:
    """Verifies material, active pharma salts, and OTC prescription bounds."""
    manifest = NegativeConstraintManifest(
        excludedMaterials=["polyester"],
        excludedActiveSalts=["paracetamol"],
        requireOtcOnly=True,
    )
    cf = NegativeConstraintFilter(manifest)

    # 1. Fabric in apparelFacet
    itemApparel = {
        "skuId": "SKU-APP-01",
        "brand": "PureBrand",
        "apparelFacet": {"fabric": ["Cotton", "Polyester Blend"]},
        "attributes": {"weightGrams": 200, "slaHours": 12},
    }
    resMat = cf.evaluateCandidate(itemApparel)
    assert not resMat.isAllowed
    assert "MATERIAL_EXCLUDED:polyester" in resMat.rejectionReason

    # 2. Prescription breach
    itemRx = {
        "skuId": "SKU-PHARM-01",
        "brand": "PureBrand",
        "pharmaFacet": {"activeSalt": "Ibuprofen", "prescriptionRequired": True},
    }
    resRx = cf.evaluateCandidate(itemRx)
    assert not resRx.isAllowed
    assert resRx.rejectionReason == "PRESCRIPTION_REQUIRED_BREACH"

    # 3. Active salt breach
    itemSalt = {
        "skuId": "SKU-PHARM-02",
        "brand": "PureBrand",
        "pharmaFacet": {"activeSalt": "Paracetamol IP 500mg", "prescriptionRequired": False},
    }
    resSalt = cf.evaluateCandidate(itemSalt)
    assert not resSalt.isAllowed
    assert "ACTIVE_SALT_EXCLUDED:paracetamol" in resSalt.rejectionReason


def testConstraintFilterDietaryDimensionsAndSla() -> None:
    """Verifies fail-closed vegetarian invariant, physical dimensions, and SLA ceilings."""
    manifest = NegativeConstraintManifest(
        requireVeg=True,
        maxWeightGrams=1000,
        maxDimensionCm={"length": 30, "width": 20, "height": 15},
        maxSlaHours=24,
    )
    cf = NegativeConstraintFilter(manifest)

    # 1. Missing veg flag triggers fail-closed rejection
    resNoVeg = cf.evaluateCandidate({"skuId": "SKU-NV-1", "attributes": {"weightGrams": 100}})
    assert not resNoVeg.isAllowed
    assert resNoVeg.rejectionReason == "NON_VEG_EXCLUDED"

    # 2. Exceeded dimension
    itemBigDim = {
        "skuId": "SKU-DIM-1",
        "attributes": {
            "weightGrams": 500, "slaHours": 12, "isVeg": True,
            "dimensionsCm": {"length": 35, "width": 15, "height": 10},
        },
    }
    resDim = cf.evaluateCandidate(itemBigDim)
    assert not resDim.isAllowed
    assert "DIMENSION_LIMIT_EXCEEDED:length:35cm" in resDim.rejectionReason

    # 3. Exceeded SLA
    itemSlow = {
        "skuId": "SKU-SLOW-1",
        "attributes": {"weightGrams": 500, "slaHours": 48, "isVeg": True},
    }
    resSla = cf.evaluateCandidate(itemSlow)
    assert not resSla.isAllowed
    assert "SLA_EXCEEDED:48h" in resSla.rejectionReason


def testVectorSearcherStockAndPriceFiltering() -> None:
    """Verifies VectorSearcher fallback filtering for stock, price delta, and empty catalogs."""
    emptySearcher = VectorSearcher(catalogStore=[])
    assert emptySearcher.searchCandidates(
        queryVector=[1.0, 0.0], hsnCode="8471", originalPricePaise=10000, requestedQuantity=1,
    ) == []

    mockCatalog = [
        {"skuId": "SKU-LOW-STOCK", "hsnCode": "8471", "baseUnitPricePaise": 10200,
         "availableStock": 2, "embeddingVector": [1.0, 0.0]},
        {"skuId": "SKU-HIGH-PRICE", "hsnCode": "8471", "baseUnitPricePaise": 12000,
         "availableStock": 10, "embeddingVector": [1.0, 0.0]},
        {"skuId": "SKU-VALID", "hsnCode": "8471", "baseUnitPricePaise": 10300,
         "availableStock": 10, "embeddingVector": [0.99, 0.14]},
    ]
    searcher = VectorSearcher(catalogStore=mockCatalog)
    res = searcher.searchCandidates(
        queryVector=[1.0, 0.0], hsnCode="8471", originalPricePaise=10000,
        requestedQuantity=5, maxPriceDeltaPct=5.0,
    )
    assert len(res) == 1
    assert res[0].skuId == "SKU-VALID"


def testVectorSearcherMockQdrantDelegation() -> None:
    """Verifies delegation to Qdrant client when present."""
    class MockPoint:
        def __init__(self, skuId: str, price: int, stock: int, score: float) -> None:
            self.score = score
            self.payload = {"skuId": skuId, "baseUnitPricePaise": price, "availableStock": stock}

    class MockQdrant:
        def search(self, **kwargs: Any) -> List[MockPoint]:
            return [
                MockPoint("SKU-QDRANT-1", 10100, 5, 0.98),
                MockPoint("SKU-QDRANT-2", 15000, 5, 0.95),
            ]

    qdrantSearcher = VectorSearcher(qdrantClient=MockQdrant())
    res = qdrantSearcher.searchCandidates(
        queryVector=[1.0, 0.0], hsnCode="8471", originalPricePaise=10000,
        requestedQuantity=1, maxPriceDeltaPct=5.0,
    )
    assert len(res) == 1
    assert res[0].skuId == "SKU-QDRANT-1"
