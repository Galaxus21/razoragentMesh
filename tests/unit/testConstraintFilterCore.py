"""Tests for NegativeConstraintFilter core checks: allergens, brands, weight, SLA (Core Suite)."""

from razoragentMesh.packages.vectorHealer.src.constraints.constraintFilter import (
    NegativeConstraintFilter,
)
from razoragentMesh.packages.vectorHealer.src.constraints.negativeManifestSchema import (
    NegativeConstraintManifest,
)

testMaxWeightGrams: int = 500
testMaxSlaHours: int = 48


def testConstraintFilterAllergenBreachRejection() -> None:
    """Verifies candidate rejection when excluded allergens appear in attributes or facets."""
    manifest = NegativeConstraintManifest(
        excludedAllergens=["peanut", "soy"],
    )
    filterEngine = NegativeConstraintFilter(manifest)

    # Direct attribute allergen breach
    itemDirectAllergen = {
        "skuId": "SKU-TEST-01",
        "brand": "SafeBrand",
        "attributes": {"allergens": ["peanut_oil"], "weightGrams": 200, "slaHours": 24},
    }
    evalDirect = filterEngine.evaluateCandidate(itemDirectAllergen)
    assert evalDirect.isAllowed is False
    assert "ALLERGEN_BREACH:peanut" in str(evalDirect.rejectionReason)

    # FMCG facet allergen breach with whitespace / casing
    itemFmcgAllergen = {
        "skuId": "SKU-FMCG-01",
        "brand": "SafeBrand",
        "fmcgFacet": {"allergens": ["  De-fatted SOY Flour  "]},
        "attributes": {"weightGrams": 200, "slaHours": 24},
    }
    evalFmcg = filterEngine.evaluateCandidate(itemFmcgAllergen)
    assert evalFmcg.isAllowed is False
    assert "ALLERGEN_BREACH:soy" in str(evalFmcg.rejectionReason)


def testConstraintFilterBrandExclusionRejection() -> None:
    """Verifies candidate rejection when brand is in exclusion list with case normalization."""
    manifest = NegativeConstraintManifest(
        excludedBrands=["BadBrand", "UnwantedBrand"],
    )
    filterEngine = NegativeConstraintFilter(manifest)

    # Standard brand rejection
    itemBadBrand = {
        "skuId": "SKU-TEST-02",
        "brand": "BadBrand",
        "attributes": {"allergens": [], "weightGrams": 200, "slaHours": 24},
    }
    evalBad = filterEngine.evaluateCandidate(itemBadBrand)
    assert evalBad.isAllowed is False
    assert "BRAND_EXCLUDED:badbrand" in str(evalBad.rejectionReason)

    # Casing and whitespace brand rejection
    itemCasingBrand = {
        "skuId": "SKU-BRAND-01",
        "brand": "  UNWANTEDBRAND  ",
        "attributes": {"allergens": [], "weightGrams": 200, "slaHours": 24},
    }
    evalCasing = filterEngine.evaluateCandidate(itemCasingBrand)
    assert evalCasing.isAllowed is False
    assert "BRAND_EXCLUDED:unwantedbrand" in str(evalCasing.rejectionReason)


def testConstraintFilterWeightLimitExceeded() -> None:
    """Verifies candidate rejection when gross weight exceeds maxWeightGrams."""
    manifest = NegativeConstraintManifest(
        maxWeightGrams=testMaxWeightGrams,
    )
    filterEngine = NegativeConstraintFilter(manifest)

    # Weight exceeded
    itemOverweight = {
        "skuId": "SKU-TEST-03",
        "brand": "GoodBrand",
        "attributes": {"weightGrams": 600, "slaHours": 24},
    }
    evalOver = filterEngine.evaluateCandidate(itemOverweight)
    assert evalOver.isAllowed is False
    assert "WEIGHT_LIMIT_EXCEEDED:600g" in str(evalOver.rejectionReason)

    # Weight compliant (boundary check)
    itemExactWeight = {
        "skuId": "SKU-TEST-03B",
        "brand": "GoodBrand",
        "attributes": {"weightGrams": testMaxWeightGrams, "slaHours": 24},
    }
    evalExact = filterEngine.evaluateCandidate(itemExactWeight)
    assert evalExact.isAllowed is True
    assert evalExact.rejectionReason is None


def testConstraintFilterSlaHoursExceeded() -> None:
    """Verifies candidate rejection when fulfillment SLA exceeds maxSlaHours."""
    manifest = NegativeConstraintManifest(
        maxSlaHours=testMaxSlaHours,
    )
    filterEngine = NegativeConstraintFilter(manifest)

    # SLA exceeded
    itemSlow = {
        "skuId": "SKU-SLOW-01",
        "brand": "GoodBrand",
        "attributes": {"weightGrams": 200, "slaHours": 72},
    }
    evalSlow = filterEngine.evaluateCandidate(itemSlow)
    assert evalSlow.isAllowed is False
    assert "SLA_EXCEEDED:72h" in str(evalSlow.rejectionReason)

    # SLA compliant
    itemFast = {
        "skuId": "SKU-FAST-01",
        "brand": "GoodBrand",
        "attributes": {"weightGrams": 200, "slaHours": 24},
    }
    evalFast = filterEngine.evaluateCandidate(itemFast)
    assert evalFast.isAllowed is True
    assert evalFast.rejectionReason is None


def testConstraintFilterCompliantCandidatePasses() -> None:
    """Verifies that candidates satisfying all constraints pass evaluation cleanly."""
    manifest = NegativeConstraintManifest(
        excludedAllergens=["peanut", "soy"],
        excludedBrands=["BadBrand"],
        maxWeightGrams=testMaxWeightGrams,
        maxSlaHours=testMaxSlaHours,
    )
    filterEngine = NegativeConstraintFilter(manifest)

    itemValid = {
        "skuId": "SKU-TEST-04",
        "brand": "GoodBrand",
        "attributes": {
            "allergens": ["gluten"],
            "weightGrams": 300,
            "slaHours": 24,
        },
    }
    evalValid = filterEngine.evaluateCandidate(itemValid)
    assert evalValid.isAllowed is True
    assert evalValid.skuId == "SKU-TEST-04"
    assert evalValid.rejectionReason is None
