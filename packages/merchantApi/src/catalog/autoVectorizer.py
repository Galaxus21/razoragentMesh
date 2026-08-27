"""Facet-aware text synthesizer and 384-dimensional vector catalog indexer."""

import inspect
import logging
import math
from typing import Any, Dict, List, Optional

from ..constants.merchantConstants import (
    defaultCollectionName, defaultVectorDimension, modelNameMiniLm,
)
from ..schemas.universalProductSchema import UniversalProductListing

logger = logging.getLogger(__name__)


def _getQdrantModels() -> Any:
    try:
        from qdrant_client import models
        return models
    except ImportError:
        class _PointStruct:
            def __init__(self, id: Any, vector: List[float], payload: Optional[dict] = None) -> None:
                self.id = id
                self.vector = vector
                self.payload = payload or {}

        class _PointIdsList:
            def __init__(self, points: List[Any]) -> None:
                self.points = points

        class _Models:
            PointStruct = _PointStruct
            PointIdsList = _PointIdsList

        return _Models


class AutoVectorizer:
    """Extracts facet-rich embeddings and maintains the Qdrant product vector index."""

    def __init__(self, qdrantClient: Any, collectionName: str = defaultCollectionName) -> None:
        self.qdrantClient = qdrantClient
        self.collectionName = collectionName
        self._engine = _EmbeddingEngine(modelName=modelNameMiniLm)

    async def upsertListing(self, listing: UniversalProductListing) -> None:
        """Embeds synthesized facet text and upserts vector and metadata into Qdrant."""
        if self.qdrantClient is None:
            return

        richText = synthesizeFacetDescription(listing)
        vector = self._engine.embed(richText)
        payload = _buildQdrantPayload(listing)

        dispatched = await _dispatchQdrantClientUpsert(
            self.qdrantClient, self.collectionName, listing.skuId, vector, payload
        )
        if not dispatched:
            pointEntry = {"id": listing.skuId, "vector": vector, "payload": payload}
            _upsertToMemoryCollection(self.qdrantClient, self.collectionName, pointEntry, listing.skuId)

    async def removeListing(self, skuId: str) -> None:
        """Deletes vector and metadata point from Qdrant by SKU identifier."""
        if self.qdrantClient is None:
            return

        if hasattr(self.qdrantClient, "delete"):
            try:
                models = _getQdrantModels()

                res = self.qdrantClient.delete(
                    collection_name=self.collectionName,
                    points_selector=models.PointIdsList(points=[skuId]),
                )
                if inspect.iscoroutine(res):
                    await res
                return
            except Exception as err:
                logger.info("Qdrant unavailable, activating memory vector index fallback: %s", err)

        if hasattr(self.qdrantClient, "collections") and self.collectionName in self.qdrantClient.collections:
            self.qdrantClient.collections[self.collectionName] = [
                p for p in self.qdrantClient.collections[self.collectionName]
                if (p.get("id") if isinstance(p, dict) else getattr(p, "id", None)) != skuId
            ]


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


def _buildQdrantPayload(listing: UniversalProductListing) -> dict[str, Any]:
    """Constructs dictionary payload for Qdrant point from UniversalProductListing."""
    return {
        "skuId": listing.skuId,
        "merchantDid": listing.merchantDid,
        "title": listing.title,
        "category": listing.category,
        "brand": getattr(listing, "brand", None),
        "hsnCode": listing.hsnCode,
        "gstRatePercent": listing.gstRatePercent,
        "baseUnitPricePaise": listing.baseUnitPricePaise,
        "availableStock": listing.availableStock,
        "currency": listing.currency,
        "description": listing.description,
        "apparelFacet": listing.apparelFacet.model_dump() if listing.apparelFacet else None,
        "fmcgFacet": listing.fmcgFacet.model_dump() if listing.fmcgFacet else None,
        "jewelryFacet": listing.jewelryFacet.model_dump(mode="json") if listing.jewelryFacet else None,
        "pharmaFacet": listing.pharmaFacet.model_dump() if listing.pharmaFacet else None,
    }


async def _dispatchQdrantClientUpsert(
    qdrantClient: Any,
    collectionName: str,
    pointId: str,
    vector: List[float],
    payload: dict[str, Any],
) -> bool:
    """Attempts native upsert on qdrantClient using PointStruct, returning True if dispatched."""
    if not hasattr(qdrantClient, "upsert"):
        return False
    try:
        models = _getQdrantModels()

        points = [models.PointStruct(id=pointId, vector=vector, payload=payload)]
        res = qdrantClient.upsert(collection_name=collectionName, points=points)
        if inspect.iscoroutine(res):
            await res
        return True
    except Exception as err:
        logger.info("Qdrant unavailable, activating memory vector index fallback: %s", err)
        return False


def _upsertToMemoryCollection(
    qdrantClient: Any,
    collectionName: str,
    pointEntry: dict[str, Any],
    skuId: str,
) -> None:
    """Fallback in-memory collection upsert replacing duplicate SKU entries."""
    if not hasattr(qdrantClient, "collections"):
        return
    if collectionName not in qdrantClient.collections:
        qdrantClient.collections[collectionName] = []
    existing = [
        p for p in qdrantClient.collections[collectionName]
        if (p.get("id") if isinstance(p, dict) else getattr(p, "id", None)) != skuId
    ]
    existing.append(pointEntry)
    qdrantClient.collections[collectionName] = existing


def _extractFacetedSegments(listing: UniversalProductListing) -> List[str]:
    """Extracts domain-specific facet fragments for jewelry, apparel, pharma, and FMCG."""
    return (
        _extractJewelrySegments(listing)
        + _extractApparelSegments(listing)
        + _extractPharmaSegments(listing)
        + _extractFmcgSegments(listing)
    )


def _extractJewelrySegments(listing: UniversalProductListing) -> List[str]:
    """Extracts gross weight and BIS hallmark description segments."""
    jf = getattr(listing, "jewelryFacet", None)
    if jf is None:
        return []
    hNum = str(jf.hallmarkNumber).strip() if jf.hallmarkNumber else ""
    hallmarkText = (hNum if hNum.startswith("BIS") else f"BIS Hallmark {hNum}") if hNum else None
    return [f"Gross {jf.grossWeightGrams}g"] + ([hallmarkText] if hallmarkText else [])


def _extractApparelSegments(listing: UniversalProductListing) -> List[str]:
    """Extracts size, color, fabric, fit, and gender apparel segments."""
    af = getattr(listing, "apparelFacet", None)
    if af is None:
        return []
    segments: List[str] = []
    if af.size:
        segments.append(f"Size {af.size}")
    if af.color:
        segments.append(af.color)
    if af.fabric:
        fab = ", ".join(af.fabric) if isinstance(af.fabric, list) else str(af.fabric)
        segments.append(f"Fabric: {fab}")
    if af.fitType:
        segments.append(f"{af.fitType} Fit")
    if af.gender:
        segments.append(f"{af.gender}")
    return segments


def _extractPharmaSegments(listing: UniversalProductListing) -> List[str]:
    """Extracts active salt and schedule pharma segments."""
    pf = getattr(listing, "pharmaFacet", None)
    if pf is None:
        return []
    segments = [f"Active: {pf.activeSalt}"]
    if pf.schedule:
        sched = pf.schedule.strip()
        segments.append(sched if sched.lower().startswith("schedule") else f"Schedule {sched}")
    return segments


def _extractFmcgSegments(listing: UniversalProductListing) -> List[str]:
    """Extracts allergens, veg indicator, and shelf life FMCG segments."""
    ff = getattr(listing, "fmcgFacet", None)
    if ff is None:
        return []
    segments: List[str] = []
    if ff.allergens:
        allg = ", ".join(ff.allergens) if isinstance(ff.allergens, list) else str(ff.allergens)
        segments.append(f"Allergens: {allg}")
    if ff.isVeg:
        segments.append("Veg")
    if ff.shelfLifeDays:
        segments.append(f"Shelf Life: {ff.shelfLifeDays} days")
    return segments


def _formatFacetEntry(key: str, value: Any) -> Optional[str]:
    """Formats an individual facet or attribute key-value pair into a normalized text fragment."""
    if isinstance(value, bool):
        return key if value else None
    if isinstance(value, (list, set, tuple)):
        return f"{key}: {', '.join(str(item) for item in value)}"
    strValue = str(value).strip()
    if not strValue:
        return None
    normalizedKey = key.lower()
    if normalizedKey in ("gross", "grossweight", "grossweightgrams"):
        return strValue if "gross" in strValue.lower() else f"Gross {strValue}"
    if normalizedKey == "size":
        return strValue if "size" in strValue.lower() else f"Size {strValue}"
    return strValue if (normalizedKey == "color" or normalizedKey in strValue.lower()) else f"{key}: {strValue}"


class _EmbeddingEngine:
    """Provides 384-dimensional dense vector embeddings with fallback."""

    def __init__(self, modelName: str = modelNameMiniLm) -> None:
        self.modelName = modelName
        self._cache: Dict[str, List[float]] = {}
        self._fastembedModel: Optional[object] = None
        self._isInitialized = False

    def _normalize(self, vector: List[float]) -> List[float]:
        normSq = sum(v * v for v in vector)
        return vector if normSq == 0.0 else [v / math.sqrt(normSq) for v in vector]

    def _initModel(self) -> None:
        if not self._isInitialized:
            self._isInitialized = True
            try:
                from fastembed import TextEmbedding  # type: ignore

                self._fastembedModel = TextEmbedding(model_name=self.modelName)
            except Exception as err:
                logger.info("Qdrant unavailable, activating memory vector index fallback: %s", err)
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
            except Exception as err:
                logger.info("Qdrant unavailable, activating memory vector index fallback: %s", err)

        # Deterministic 384-dim pseudo-vector fallback for offline environments
        pseudo = [0.0] * defaultVectorDimension
        for idx, char in enumerate(cleaned):
            slot = (ord(char) * (idx + 1) * 31) % defaultVectorDimension
            pseudo[slot] += 1.0
        normalizedFallback = self._normalize(pseudo)
        self._cache[cleaned] = normalizedFallback
        return normalizedFallback


__all__ = [
    "AutoVectorizer",
    "synthesizeFacetDescription",
]
