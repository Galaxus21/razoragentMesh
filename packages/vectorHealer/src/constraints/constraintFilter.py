"""Negative constraint AST evaluator for Layer 3 self-healing filters."""

from typing import Any, Dict, List, Optional
from .negativeManifestSchema import (
    ConstraintEvaluationResult,
    NegativeConstraintManifest,
)


class NegativeConstraintFilter:
    """Boolean AST evaluator enforcing allergen, brand, weight, material, OTC, veg, and SLA bounds."""

    def __init__(self, manifest: NegativeConstraintManifest) -> None:
        self.manifest = manifest
        self._normalizedAllergens = {a.lower().strip() for a in manifest.excludedAllergens}
        self._normalizedBrands = {b.lower().strip() for b in manifest.excludedBrands}
        self._normalizedMaterials = {m.lower().strip() for m in manifest.excludedMaterials}
        self._normalizedSalts = {s.lower().strip() for s in manifest.excludedActiveSalts}

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

    def _checkMaterials(self, fabrics: List[str]) -> Optional[str]:
        """Evaluates candidate fabrics/materials against excluded material list."""
        for mat in self._normalizedMaterials:
            for f in fabrics:
                if mat in f.lower() or f.lower() in mat:
                    return f"MATERIAL_EXCLUDED:{mat}"
        return None

    def _checkSalts(self, activeSalt: str) -> Optional[str]:
        """Evaluates candidate active pharma ingredients against excluded salt list."""
        if not activeSalt:
            return None
        saltClean = activeSalt.lower().strip()
        for s in self._normalizedSalts:
            if s in saltClean or saltClean in s:
                return f"ACTIVE_SALT_EXCLUDED:{s}"
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

    def _checkVegInvariant(
        self,
        fmcgFacet: Dict[str, Any],
        attributes: Dict[str, Any],
        skuPayload: Dict[str, Any],
    ) -> Optional[str]:
        """Enforces vegetarian constraint defaulting to False (fail-closed) when omitted."""
        if not self.manifest.requireVeg:
            return None
        if "isVeg" in fmcgFacet:
            isVeg = bool(fmcgFacet["isVeg"])
        elif "isVeg" in attributes:
            isVeg = bool(attributes["isVeg"])
        elif "isVeg" in skuPayload:
            isVeg = bool(skuPayload["isVeg"])
        else:
            isVeg = False
        if not isVeg:
            return "NON_VEG_EXCLUDED"
        return None

    def evaluateCandidate(self, skuPayload: Dict[str, Any]) -> ConstraintEvaluationResult:
        """Runs full suite of boolean constraint checks on SKU payload."""
        skuId = skuPayload["skuId"]
        brand = skuPayload.get("brand", "").lower().strip()
        attributes = skuPayload.get("attributes", {})
        apparelFacet = skuPayload.get("apparelFacet", {}) or {}
        fmcgFacet = skuPayload.get("fmcgFacet", {}) or {}
        pharmaFacet = skuPayload.get("pharmaFacet", {}) or {}

        rawAllergens = (
            attributes.get("allergens", [])
            or skuPayload.get("allergens", [])
            or fmcgFacet.get("allergens", [])
        )
        itemAllergens = [str(a).lower().strip() for a in rawAllergens]
        weight = attributes.get("weightGrams") or skuPayload.get("weightGrams")

        allergenReason = self._checkAllergens(itemAllergens)
        if allergenReason:
            return ConstraintEvaluationResult(skuId=skuId, isAllowed=False, rejectionReason=allergenReason)

        brandReason = self._checkBrand(brand)
        if brandReason:
            return ConstraintEvaluationResult(skuId=skuId, isAllowed=False, rejectionReason=brandReason)

        fabrics = apparelFacet.get("fabric", []) or attributes.get("fabric", []) or skuPayload.get("fabric", [])
        if isinstance(fabrics, str):
            fabrics = [fabrics]
        materialReason = self._checkMaterials(fabrics)
        if materialReason:
            return ConstraintEvaluationResult(skuId=skuId, isAllowed=False, rejectionReason=materialReason)

        activeSalt = pharmaFacet.get("activeSalt") or attributes.get("activeSalt") or skuPayload.get("activeSalt", "")
        saltReason = self._checkSalts(str(activeSalt))
        if saltReason:
            return ConstraintEvaluationResult(skuId=skuId, isAllowed=False, rejectionReason=saltReason)

        if self.manifest.requireOtcOnly:
            rxReq = pharmaFacet.get("prescriptionRequired") or attributes.get("prescriptionRequired", False)
            if rxReq:
                return ConstraintEvaluationResult(
                    skuId=skuId,
                    isAllowed=False,
                    rejectionReason="PRESCRIPTION_REQUIRED_BREACH",
                )

        vegReason = self._checkVegInvariant(fmcgFacet, attributes, skuPayload)
        if vegReason:
            return ConstraintEvaluationResult(
                skuId=skuId,
                isAllowed=False,
                rejectionReason=vegReason,
            )

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
