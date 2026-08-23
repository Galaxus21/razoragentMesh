"""Negative constraint AST evaluator for Layer 3 self-healing filters."""

from typing import Any, Dict, List, Optional
from .negativeManifestSchema import (
    ConstraintEvaluationResult,
    NegativeConstraintManifest,
)


class NegativeConstraintFilter:
    """Boolean AST evaluator enforcing allergen, brand, weight, and SLA bounds."""

    def __init__(self, manifest: NegativeConstraintManifest) -> None:
        self.manifest = manifest
        self._normalizedAllergens = {a.lower().strip() for a in manifest.excludedAllergens}
        self._normalizedBrands = {b.lower().strip() for b in manifest.excludedBrands}

    def _checkAllergens(self, itemAllergens: List[str]) -> Optional[str]:
        """Evaluates candidate allergens against blacklisted allergens."""
        for allergy in self._normalizedAllergens:
            for itemAllergen in itemAllergens:
                if allergy in itemAllergen or itemAllergen in allergy:
                    return f"ALLERGEN_BREACH:{allergy}"
        return None

    def _checkBrand(self, brand: str) -> Optional[str]:
        """Evaluates candidate brand against excluded brand list."""
        if brand and brand in self._normalizedBrands:
            return f"BRAND_EXCLUDED:{brand}"
        return None

    def _checkPhysicalLimits(self, weight: Optional[int], attributes: Dict[str, Any]) -> Optional[str]:
        """Evaluates candidate physical weight and dimension constraints."""
        if self.manifest.maxWeightGrams is not None and weight is not None:
            if weight > self.manifest.maxWeightGrams:
                return f"WEIGHT_LIMIT_EXCEEDED:{weight}g"

        if self.manifest.maxDimensionCm is not None:
            dimensions = attributes.get("dimensionsCm", {})
            for dimKey, maxDimVal in self.manifest.maxDimensionCm.items():
                candDimVal = dimensions.get(dimKey)
                if candDimVal is not None and candDimVal > maxDimVal:
                    return f"DIMENSION_LIMIT_EXCEEDED:{dimKey}:{candDimVal}cm"
        return None

    def evaluateCandidate(self, skuPayload: Dict[str, Any]) -> ConstraintEvaluationResult:
        """Runs full suite of boolean constraint checks on SKU payload."""
        skuId = skuPayload["skuId"]
        brand = skuPayload.get("brand", "").lower().strip()
        attributes = skuPayload.get("attributes", {})
        rawAllergens = attributes.get("allergens", []) or skuPayload.get("allergens", [])
        itemAllergens = [str(a).lower().strip() for a in rawAllergens]
        weight = attributes.get("weightGrams") or skuPayload.get("weightGrams")

        allergenReason = self._checkAllergens(itemAllergens)
        if allergenReason:
            return ConstraintEvaluationResult(skuId=skuId, isAllowed=False, rejectionReason=allergenReason)

        brandReason = self._checkBrand(brand)
        if brandReason:
            return ConstraintEvaluationResult(skuId=skuId, isAllowed=False, rejectionReason=brandReason)

        physicalReason = self._checkPhysicalLimits(weight, attributes)
        if physicalReason:
            return ConstraintEvaluationResult(skuId=skuId, isAllowed=False, rejectionReason=physicalReason)

        if self.manifest.maxSlaHours is not None:
            slaHours = skuPayload.get("slaHours") or attributes.get("slaHours")
            if slaHours is not None and slaHours > self.manifest.maxSlaHours:
                return ConstraintEvaluationResult(
                    skuId=skuId,
                    isAllowed=False,
                    rejectionReason=f"SLA_EXCEEDED:{slaHours}h",
                )

        return ConstraintEvaluationResult(skuId=skuId, isAllowed=True)


__all__ = [
    "ConstraintEvaluationResult",
    "NegativeConstraintFilter",
    "NegativeConstraintManifest",
]
