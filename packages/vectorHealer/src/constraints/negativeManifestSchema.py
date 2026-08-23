"""Negative constraint manifest and evaluation schemas."""

from typing import Dict, List, Optional
from pydantic import BaseModel, ConfigDict, Field


class NegativeConstraintManifest(BaseModel):
    """User and enterprise negative constraint specification."""

    model_config = ConfigDict(frozen=True, extra="forbid")

    excludedAllergens: List[str] = Field(default_factory=list)
    excludedBrands: List[str] = Field(default_factory=list)
    maxWeightGrams: Optional[int] = Field(default=None)
    maxDimensionCm: Optional[Dict[str, int]] = Field(default=None)
    maxSlaHours: Optional[int] = Field(default=None)


class ConstraintEvaluationResult(BaseModel):
    """Result of negative constraint evaluation on a SKU candidate."""

    model_config = ConfigDict(frozen=True, extra="forbid")

    skuId: str
    isAllowed: bool
    rejectionReason: Optional[str] = None


__all__ = [
    "ConstraintEvaluationResult",
    "NegativeConstraintManifest",
]
