"""Tests for NegativeConstraintFilter vertical domain checks: apparel, pharma, FMCG (Verticals Suite)."""

from razoragentMesh.packages.vectorHealer.src.constraints.constraintFilter import (
    NegativeConstraintFilter,
)
from razoragentMesh.packages.vectorHealer.src.constraints.negativeManifestSchema import (
    NegativeConstraintManifest,
)

testExcludedMaterials: list[str] = ["polyester", "leather"]
testExcludedSalts: list[str] = ["pseudoephedrine", "paracetamol"]


def testConstraintFilterApparelMaterialExclusion() -> None:
    """Verifies candidate rejection when forbidden apparel materials appear in facets or attributes."""
    manifest = NegativeConstraintManifest(excludedMaterials=testExcludedMaterials)
    filterEngine = NegativeConstraintFilter(manifest)

    itemApparel = {
        "skuId": "SKU-APP-01",
        "brand": "StyleBrand",
        "apparelFacet": {"fabric": ["Cotton", "Polyester Blend"]},
        "attributes": {"weightGrams": 200, "slaHours": 12},
    }
    resApparel = filterEngine.evaluateCandidate(itemApparel)
    assert resApparel.isAllowed is False
    assert "MATERIAL_EXCLUDED:polyester" in str(resApparel.rejectionReason)

    itemLeather = {
        "skuId": "SKU-APP-02",
        "brand": "StyleBrand",
        "attributes": {"fabric": "Genuine Leather", "weightGrams": 300, "slaHours": 12},
    }
    resLeather = filterEngine.evaluateCandidate(itemLeather)
    assert resLeather.isAllowed is False
    assert "MATERIAL_EXCLUDED:leather" in str(resLeather.rejectionReason)


def testConstraintFilterPharmaActiveSaltExclusion() -> None:
    """Verifies candidate rejection when prohibited active pharmaceutical salts are detected."""
    manifest = NegativeConstraintManifest(excludedActiveSalts=testExcludedSalts)
    filterEngine = NegativeConstraintFilter(manifest)

    itemParacetamol = {
        "skuId": "SKU-PHARM-01",
        "brand": "MedBrand",
        "pharmaFacet": {"activeSalt": "Paracetamol IP 500mg", "prescriptionRequired": False},
    }
    resParacetamol = filterEngine.evaluateCandidate(itemParacetamol)
    assert resParacetamol.isAllowed is False
    assert "ACTIVE_SALT_EXCLUDED:paracetamol" in str(resParacetamol.rejectionReason)

    itemPseudo = {
        "skuId": "SKU-PHARM-02",
        "brand": "MedBrand",
        "attributes": {"activeSalt": "Pseudoephedrine Hydrochloride"},
    }
    resPseudo = filterEngine.evaluateCandidate(itemPseudo)
    assert resPseudo.isAllowed is False
    assert "ACTIVE_SALT_EXCLUDED:pseudoephedrine" in str(resPseudo.rejectionReason)


def testConstraintFilterPharmaOtcPrescriptionBreach() -> None:
    """Verifies rejection when OTC-only is mandated and prescription is required."""
    manifest = NegativeConstraintManifest(requireOtcOnly=True)
    filterEngine = NegativeConstraintFilter(manifest)

    itemRx = {
        "skuId": "SKU-PHARM-03",
        "brand": "MedBrand",
        "pharmaFacet": {"activeSalt": "Amoxicillin", "prescriptionRequired": True},
    }
    resRx = filterEngine.evaluateCandidate(itemRx)
    assert resRx.isAllowed is False
    assert resRx.rejectionReason == "PRESCRIPTION_REQUIRED_BREACH"

    itemOtc = {
        "skuId": "SKU-PHARM-04",
        "brand": "MedBrand",
        "pharmaFacet": {"activeSalt": "Cetirizine", "prescriptionRequired": False},
    }
    resOtc = filterEngine.evaluateCandidate(itemOtc)
    assert resOtc.isAllowed is True
    assert resOtc.rejectionReason is None


def testConstraintFilterFmcgVegetarianFailClosed() -> None:
    """Verifies strict fail-closed vegetarian invariant enforcement."""
    manifest = NegativeConstraintManifest(requireVeg=True)
    filterEngine = NegativeConstraintFilter(manifest)

    itemNoVeg = {"skuId": "SKU-NV-01", "attributes": {"weightGrams": 100}}
    resNoVeg = filterEngine.evaluateCandidate(itemNoVeg)
    assert resNoVeg.isAllowed is False and resNoVeg.rejectionReason == "NON_VEG_EXCLUDED"

    itemExplicitNonVeg = {"skuId": "SKU-NV-02", "fmcgFacet": {"isVeg": False}}
    resExplicit = filterEngine.evaluateCandidate(itemExplicitNonVeg)
    assert resExplicit.isAllowed is False and resExplicit.rejectionReason == "NON_VEG_EXCLUDED"

    itemVeg = {"skuId": "SKU-VEG-01", "fmcgFacet": {"isVeg": True}}
    resVeg = filterEngine.evaluateCandidate(itemVeg)
    assert resVeg.isAllowed is True and resVeg.rejectionReason is None


def testConstraintFilterMultiDomainCompoundManifest() -> None:
    """Verifies simultaneous compound constraint evaluation across multiple vertical facets."""
    manifest = NegativeConstraintManifest(
        requireVeg=True,
        requireOtcOnly=True,
        maxWeightGrams=1000,
        maxDimensionCm={"length": 30, "width": 20, "height": 15},
        maxSlaHours=24,
        excludedAllergens=["peanut"],
        excludedMaterials=["polyester"],
    )
    filterEngine = NegativeConstraintFilter(manifest)

    itemBigDim = {
        "skuId": "SKU-DIM-01",
        "attributes": {"weightGrams": 500, "slaHours": 12, "isVeg": True, "dimensionsCm": {"length": 35, "width": 15, "height": 10}},
    }
    resDim = filterEngine.evaluateCandidate(itemBigDim)
    assert resDim.isAllowed is False
    assert "DIMENSION_LIMIT_EXCEEDED:length:35cm" in str(resDim.rejectionReason)

    itemCompliant = {
        "skuId": "SKU-COMPOUND-OK",
        "brand": "CleanBrand",
        "attributes": {"weightGrams": 400, "slaHours": 18, "isVeg": True, "dimensionsCm": {"length": 20, "width": 15, "height": 10}},
        "apparelFacet": {"fabric": ["100% Organic Cotton"]},
    }
    resCompliant = filterEngine.evaluateCandidate(itemCompliant)
    assert resCompliant.isAllowed is True and resCompliant.rejectionReason is None
