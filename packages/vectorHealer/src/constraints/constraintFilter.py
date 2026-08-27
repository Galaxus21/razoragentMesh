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
        self._normalizedAllergens = {allergen.lower().strip() for allergen in manifest.excludedAllergens}
        self._normalizedBrands = {brand.lower().strip() for brand in manifest.excludedBrands}
        self._normalizedMaterials = {material.lower().strip() for material in manifest.excludedMaterials}
        self._normalizedSalts = {salt.lower().strip() for salt in manifest.excludedActiveSalts}

    def evaluateCandidate(self, skuPayload: Dict[str, Any]) -> ConstraintEvaluationResult:
        """Runs full suite of boolean constraint checks on SKU payload."""
        skuId = skuPayload["skuId"]
        attributes = skuPayload.get("attributes", {})
        apparelFacet = skuPayload.get("apparelFacet", {}) or {}
        fmcgFacet = skuPayload.get("fmcgFacet", {}) or {}
        pharmaFacet = skuPayload.get("pharmaFacet", {}) or {}

        rejection = (
            self._checkAllergenConstraints(skuPayload, attributes, fmcgFacet)
            or self._checkBrandConstraints(skuPayload)
            or self._checkMaterialAndPharmaConstraints(skuPayload, attributes, apparelFacet, pharmaFacet)
            or self._checkPhysicalAndDietaryConstraints(skuPayload, attributes, fmcgFacet)
            or self._checkSlaConstraints(skuPayload, attributes)
        )
        if rejection:
            return ConstraintEvaluationResult(skuId=skuId, isAllowed=False, rejectionReason=rejection)
        return ConstraintEvaluationResult(skuId=skuId, isAllowed=True)

    def _checkAllergenConstraints(
        self,
        skuPayload: Dict[str, Any],
        attributes: Dict[str, Any],
        fmcgFacet: Dict[str, Any],
    ) -> Optional[str]:
        """Extracts and evaluates item allergens against manifest exclusion list."""
        rawAllergens = (
            attributes.get("allergens", [])
            or skuPayload.get("allergens", [])
            or fmcgFacet.get("allergens", [])
        )
        itemAllergens = [str(a).lower().strip() for a in rawAllergens]
        return self._checkAllergens(itemAllergens)

    def _checkBrandConstraints(self, skuPayload: Dict[str, Any]) -> Optional[str]:
        """Extracts brand and evaluates against manifest exclusion list."""
        brand = skuPayload.get("brand", "").lower().strip()
        return self._checkBrand(brand)

    def _checkMaterialAndPharmaConstraints(
        self,
        skuPayload: Dict[str, Any],
        attributes: Dict[str, Any],
        apparelFacet: Dict[str, Any],
        pharmaFacet: Dict[str, Any],
    ) -> Optional[str]:
        """Evaluates fabric materials, active pharma salts, and OTC prescription requirements."""
        fabrics = apparelFacet.get("fabric", []) or attributes.get("fabric", []) or skuPayload.get("fabric", [])
        if isinstance(fabrics, str):
            fabrics = [fabrics]
        materialReason = self._checkMaterials(fabrics)
        if materialReason:
            return materialReason

        activeSalt = pharmaFacet.get("activeSalt") or attributes.get("activeSalt") or skuPayload.get("activeSalt", "")
        saltReason = self._checkSalts(str(activeSalt))
        if saltReason:
            return saltReason

        if self.manifest.requireOtcOnly:
            rxReq = pharmaFacet.get("prescriptionRequired") or attributes.get("prescriptionRequired", False)
            if rxReq:
                return "PRESCRIPTION_REQUIRED_BREACH"
        return None

    def _checkPhysicalAndDietaryConstraints(
        self,
        skuPayload: Dict[str, Any],
        attributes: Dict[str, Any],
        fmcgFacet: Dict[str, Any],
    ) -> Optional[str]:
        """Evaluates vegetarian dietary invariant, item weight, and dimension boundaries."""
        vegReason = self._checkVegInvariant(fmcgFacet, attributes, skuPayload)
        if vegReason:
            return vegReason
        weight = attributes.get("weightGrams") or skuPayload.get("weightGrams")
        return self._checkPhysicalLimits(weight, attributes)

    def _checkSlaConstraints(
        self,
        skuPayload: Dict[str, Any],
        attributes: Dict[str, Any],
    ) -> Optional[str]:
        """Evaluates fulfillment SLA hours against manifest ceiling."""
        if self.manifest.maxSlaHours is not None:
            slaHours = skuPayload.get("slaHours") or attributes.get("slaHours")
            if slaHours is not None and slaHours > self.manifest.maxSlaHours:
                return f"SLA_EXCEEDED:{slaHours}h"
        return None

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
        for material in self._normalizedMaterials:
            for fabricMaterial in fabrics:
                if material in fabricMaterial.lower() or fabricMaterial.lower() in material:
                    return f"MATERIAL_EXCLUDED:{material}"
        return None

    def _checkSalts(self, activeSalt: str) -> Optional[str]:
        """Evaluates candidate active pharma ingredients against excluded salt list."""
        if not activeSalt:
            return None
        saltClean = activeSalt.lower().strip()
        for excludedSalt in self._normalizedSalts:
            if excludedSalt in saltClean or saltClean in excludedSalt:
                return f"ACTIVE_SALT_EXCLUDED:{excludedSalt}"
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


__all__ = [
    "ConstraintEvaluationResult",
    "NegativeConstraintFilter",
    "NegativeConstraintManifest",
]
