from typing import Any, Dict, List, Optional
from pydantic import BaseModel, ConfigDict, Field
import pytest

# Benchmark Constants
targetAllergen = "peanut"
rejectedSkuId = "SKU-201"
selectedSkuId = "SKU-205"


class NegativeConstraintManifest(BaseModel):
    """User/Enterprise negative constraint rules."""

    model_config = ConfigDict(frozen=True, extra="forbid")
    excludedAllergens: list[str] = Field(default_factory=list)
    excludedBrands: list[str] = Field(default_factory=list)
    maxWeightGrams: Optional[int] = Field(default=None)


class ConstraintEvaluationResult(BaseModel):
    model_config = ConfigDict(frozen=True, extra="forbid")
    skuId: str
    isAllowed: bool
    rejectionReason: Optional[str] = None


class NegativeConstraintFilter:
    """Boolean AST evaluator enforcing allergen, brand, and physical constraints."""

    def __init__(self, manifest: NegativeConstraintManifest) -> None:
        self.manifest = manifest
        self._normalizedAllergens = {a.lower().strip() for a in manifest.excludedAllergens}
        self._normalizedBrands = {b.lower().strip() for b in manifest.excludedBrands}

    def evaluateCandidate(self, skuPayload: Dict[str, Any]) -> ConstraintEvaluationResult:
        skuId = skuPayload["skuId"]
        brand = skuPayload.get("brand", "").lower().strip()
        attributes = skuPayload.get("attributes", {})
        itemAllergens = [a.lower().strip() for a in attributes.get("allergens", [])]
        weight = attributes.get("weightGrams")

        # 1. Allergen Check (case-insensitive substring/equality)
        for allergy in self._normalizedAllergens:
            for itemAllergen in itemAllergens:
                if allergy in itemAllergen or itemAllergen in allergy:
                    return ConstraintEvaluationResult(
                        skuId=skuId,
                        isAllowed=False,
                        rejectionReason=f"ALLERGEN_BREACH:{allergy}",
                    )

        # 2. Brand Check
        if brand in self._normalizedBrands:
            return ConstraintEvaluationResult(
                skuId=skuId,
                isAllowed=False,
                rejectionReason=f"BRAND_EXCLUDED:{brand}",
            )

        # 3. Physical Limits Check
        if self.manifest.maxWeightGrams is not None and weight is not None:
            if weight > self.manifest.maxWeightGrams:
                return ConstraintEvaluationResult(
                    skuId=skuId,
                    isAllowed=False,
                    rejectionReason=f"WEIGHT_LIMIT_EXCEEDED:{weight}g",
                )

        return ConstraintEvaluationResult(skuId=skuId, isAllowed=True)


def testTc05NegativeConstraintAllergenRejection(
    catalogFixtures: List[Dict[str, Any]],
    mockQdrantClient: Any,
) -> None:
    """TC-05: Negative Constraint Filtering — Peanut allergen blacklist rejects SKU-201 and selects SKU-205."""
    manifest = NegativeConstraintManifest(
        excludedAllergens=["peanut", "peanut_oil"],
        excludedBrands=["BadBrand"],
    )
    filterEngine = NegativeConstraintFilter(manifest)

    # Candidate 1: SKU-201 (Contains Peanut Oil)
    sku201 = next(s for s in catalogFixtures if s["skuId"] == rejectedSkuId)
    eval201 = filterEngine.evaluateCandidate(sku201)

    assert not eval201.isAllowed
    assert eval201.rejectionReason is not None
    assert "ALLERGEN_BREACH" in eval201.rejectionReason

    # Candidate 2: SKU-205 (Sunflower Oil - Allergen Free)
    sku205 = next(s for s in catalogFixtures if s["skuId"] == selectedSkuId)
    eval205 = filterEngine.evaluateCandidate(sku205)

    assert eval205.isAllowed
    assert eval205.rejectionReason is None


def testTc05ExcludedBrandAndWeightFiltering(
    catalogFixtures: List[Dict[str, Any]],
) -> None:
    """Verifies that brand exclusion and weight limit constraints evaluate deterministically."""
    manifest = NegativeConstraintManifest(
        excludedBrands=["SensTech"],
        maxWeightGrams=400,
    )
    filterEngine = NegativeConstraintFilter(manifest)

    # SKU-001 has brand 'SensTech' -> Excluded
    sku001 = next(s for s in catalogFixtures if s["skuId"] == "SKU-001")
    evalBrand = filterEngine.evaluateCandidate(sku001)
    assert not evalBrand.isAllowed
    assert "BRAND_EXCLUDED:senstech" in str(evalBrand.rejectionReason)

    # SKU-301 has weight 1050g > maxWeightGrams 400g -> Excluded
    sku301 = next(s for s in catalogFixtures if s["skuId"] == "SKU-301")
    evalWeight = filterEngine.evaluateCandidate(sku301)
    assert not evalWeight.isAllowed
    assert "WEIGHT_LIMIT_EXCEEDED" in str(evalWeight.rejectionReason)
