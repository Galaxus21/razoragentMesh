"""Facet-aware text synthesizer and 384-dimensional vector catalog indexer."""

import inspect
import math
from typing import Any, Dict, List, Optional

from ..constants.merchantConstants import (
    defaultCollectionName,
    defaultVectorDimension,
    modelNameMiniLm,
)
from ..schemas.universalProductSchema import UniversalProductListing


def _formatFacetEntry(key: str, value: Any) -> Optional[str]:
    """Formats an individual facet or attribute key-value pair into a normalized text fragment."""
    if isinstance(value, bool):
        return key if value else None

    if isinstance(value, (list, set, tuple)):
        joinedItems = ", ".join(str(item) for item in value)
        return f"{key}: {joinedItems}"

    strValue = str(value).strip()
    if not strValue:
        return None

    normalizedKey = key.lower()
    if normalizedKey in ("gross", "grossweight", "grossweightgrams"):
        return strValue if "gross" in strValue.lower() else f"Gross {strValue}"
    if normalizedKey == "size":
        return strValue if "size" in strValue.lower() else f"Size {strValue}"
    if normalizedKey == "color":
        return strValue
    if normalizedKey in strValue.lower():
        return strValue

    return f"{key}: {strValue}"


def _extractFacetedSegments(listing: UniversalProductListing) -> List[str]:
    """Extracts domain-specific facet fragments for jewelry, apparel, pharma, and FMCG."""
    segments: List[str] = []

    if getattr(listing, "jewelryFacet", None) is not None:
        jf = listing.jewelryFacet
        segments.append(f"Gross {jf.grossWeightGrams}g")
        if jf.hallmarkNumber:
            hNum = str(jf.hallmarkNumber).strip()
            segments.append(hNum if hNum.startswith("BIS") else f"BIS Hallmark {hNum}")

    if getattr(listing, "apparelFacet", None) is not None:
        af = listing.apparelFacet
        segments.append(f"Size {af.size}")
        if af.color:
            segments.append(af.color)
        if af.fabric:
            fab = ", ".join(af.fabric) if isinstance(af.fabric, list) else str(af.fabric)
            segments.append(f"Fabric: {fab}")

    if getattr(listing, "pharmaFacet", None) is not None:
        pf = listing.pharmaFacet
        segments.append(f"Active: {pf.activeSalt}")
        if pf.schedule:
            sched = pf.schedule.strip()
            segments.append(sched if sched.lower().startswith("schedule") else f"Schedule {sched}")

    if getattr(listing, "fmcgFacet", None) is not None:
        ff = listing.fmcgFacet
        if ff.allergens:
            allg = ", ".join(ff.allergens) if isinstance(ff.allergens, list) else str(ff.allergens)
            segments.append(f"Allergens: {allg}")
        if ff.isVeg:
            segments.append("Veg")

    return segments


def synthesizeFacetDescription(listing: UniversalProductListing) -> str:
    """Synthesizes structured category facets and product metadata into rich semantic text."""
    segments: List[str] = []

    if listing.category:
        segments.append(listing.category.strip())

    brand = getattr(listing, "brand", None) or ""
    title = listing.title.strip() if listing.title else ""
    if brand and brand.lower() not in title.lower():
        segments.append(f"{brand} {title}")
    elif title:
        segments.append(title)

    segments.extend(_extractFacetedSegments(listing))

    facetsDict = getattr(listing, "facets", None)
    if isinstance(facetsDict, dict):
        for key, val in facetsDict.items():
            formatted = _formatFacetEntry(key, val)
            if formatted and formatted not in segments:
                segments.append(formatted)

    if listing.hsnCode:
        segments.append(f"HSN {listing.hsnCode}")

    return " | ".join(segments)


class _EmbeddingEngine:
    """Provides 384-dimensional dense vector embeddings with fallback."""

    def __init__(self, modelName: str = modelNameMiniLm) -> None:
        self.modelName = modelName
        self._cache: Dict[str, List[float]] = {}
        self._fastembedModel: Optional[object] = None
        self._isInitialized = False

    def _normalize(self, vector: List[float]) -> List[float]:
        normSq = sum(v * v for v in vector)
        if normSq == 0.0:
            return vector
        mag = math.sqrt(normSq)
        return [v / mag for v in vector]

    def _initModel(self) -> None:
        if self._isInitialized:
            return
        self._isInitialized = True
        try:
            from fastembed import TextEmbedding  # type: ignore

            self._fastembedModel = TextEmbedding(model_name=self.modelName)
        except Exception:
            self._fastembedModel = None

    def embed(self, text: str) -> List[float]:
        cleaned = text.strip().lower()
        if cleaned in self._cache:
            return self._cache[cleaned]

        self._initModel()
        if self._fastembedModel is not None:
            try:
                gen = self._fastembedModel.embed([text])  # type: ignore
                vec = list(next(iter(gen)))
                normalized = self._normalize(vec)
                self._cache[cleaned] = normalized
                return normalized
            except Exception:
                pass

        # Deterministic 384-dim pseudo-vector fallback for offline environments
        pseudo = [0.0] * defaultVectorDimension
        for idx, char in enumerate(cleaned):
            slot = (ord(char) * (idx + 1) * 31) % defaultVectorDimension
            pseudo[slot] += 1.0
        normalizedFallback = self._normalize(pseudo)
        self._cache[cleaned] = normalizedFallback
        return normalizedFallback


class AutoVectorizer:
    """Extracts facet-rich embeddings and maintains the Qdrant product vector index."""

    def __init__(
        self,
        qdrantClient: Any,
        collectionName: str = defaultCollectionName,
    ) -> None:
        self.qdrantClient = qdrantClient
        self.collectionName = collectionName
        self._engine = _EmbeddingEngine(modelName=modelNameMiniLm)

    async def upsertListing(self, listing: UniversalProductListing) -> None:
        """Embeds synthesized facet text and upserts vector and metadata into Qdrant."""
        if self.qdrantClient is None:
            return

        richText = synthesizeFacetDescription(listing)
        vector = self._engine.embed(richText)
        isAvailableFlag = getattr(listing, "isAvailable", True)
        isAvailable = isAvailableFlag and (listing.availableStock > 0)

        payload = {
            "skuId": listing.skuId,
            "merchantDid": listing.merchantDid,
            "title": listing.title,
            "category": listing.category,
            "brand": getattr(listing, "brand", None),
            "hsnCode": listing.hsnCode,
            "gstRatePercent": listing.gstRatePercent,
            "baseUnitPricePaise": listing.baseUnitPricePaise,
            "availableStock": listing.availableStock,
            "isAvailable": isAvailable,
            "currency": listing.currency,
            "description": listing.description,
        }

        if hasattr(self.qdrantClient, "upsert"):
            try:
                from qdrant_client import models

                points = [
                    models.PointStruct(
                        id=listing.skuId,
                        vector=vector,
                        payload=payload,
                    )
                ]
                res = self.qdrantClient.upsert(
                    collection_name=self.collectionName,
                    points=points,
                )
                if inspect.iscoroutine(res):
                    await res
                return
            except Exception:
                pass

        if hasattr(self.qdrantClient, "collections"):
            if self.collectionName not in self.qdrantClient.collections:
                self.qdrantClient.collections[self.collectionName] = []
            pointEntry = {"id": listing.skuId, "vector": vector, "payload": payload}
            existing = [
                p for p in self.qdrantClient.collections[self.collectionName]
                if (p.get("id") if isinstance(p, dict) else getattr(p, "id", None)) != listing.skuId
            ]
            existing.append(pointEntry)
            self.qdrantClient.collections[self.collectionName] = existing

    async def removeListing(self, skuId: str) -> None:
        """Deletes vector and metadata point from Qdrant by SKU identifier."""
        if self.qdrantClient is None:
            return

        if hasattr(self.qdrantClient, "delete"):
            try:
                from qdrant_client import models

                res = self.qdrantClient.delete(
                    collection_name=self.collectionName,
                    points_selector=models.PointIdsList(points=[skuId]),
                )
                if inspect.iscoroutine(res):
                    await res
                return
            except Exception:
                pass

        if hasattr(self.qdrantClient, "collections"):
            if self.collectionName in self.qdrantClient.collections:
                self.qdrantClient.collections[self.collectionName] = [
                    p for p in self.qdrantClient.collections[self.collectionName]
                    if (p.get("id") if isinstance(p, dict) else getattr(p, "id", None)) != skuId
                ]


__all__ = [
    "AutoVectorizer",
    "synthesizeFacetDescription",
]
