"""Qdrant point identity, payload construction, and upsert dispatch with in-memory fallback."""

import inspect
import logging
import uuid
from typing import Any, List, Optional

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


def pointIdForSku(skuId: str) -> str:
    """Maps a SKU id onto a Qdrant point id.

    Qdrant accepts only unsigned integers or UUIDs as point ids and rejects a bare SKU string
    outright ("not a valid point ID"). Passing skuId directly meant every upsert failed, was
    caught, logged at INFO as "Qdrant unavailable", and fell through to an in-memory path that
    a real client does not have -- so indexing silently did nothing.

    uuid5 keeps the mapping deterministic, so re-publishing a SKU updates its point instead of
    creating a duplicate, and removeListing can find the same point again. The SKU id itself
    stays in the payload, which is what search results are read from.
    """
    return str(uuid.uuid5(uuid.NAMESPACE_URL, skuId))


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
        # WARNING, not INFO: for a real QdrantClient the in-memory fallback below is a no-op
        # (it has no .collections attribute), so this line is the only trace that a listing
        # never became searchable. At INFO it sat below uvicorn's default level and an upsert
        # that rejected every point looked exactly like one that worked.
        logger.warning(
            "Qdrant upsert failed for collection '%s'; the listing is NOT searchable: %s",
            collectionName,
            err,
        )
        return False


def _upsertToMemoryCollection(
    qdrantClient: Any,
    collectionName: str,
    pointEntry: dict[str, Any],
    pointId: str,
) -> None:
    """Fallback in-memory collection upsert replacing the existing point with this id."""
    if not hasattr(qdrantClient, "collections"):
        return
    if collectionName not in qdrantClient.collections:
        qdrantClient.collections[collectionName] = []
    # Must compare against the derived point id, not the SKU id. Points are stored under
    # pointIdForSku(), so matching on the raw SKU never hit and every re-upsert appended a
    # duplicate rather than replacing the previous vector.
    existing = [
        p for p in qdrantClient.collections[collectionName]
        if (p.get("id") if isinstance(p, dict) else getattr(p, "id", None)) != pointId
    ]
    existing.append(pointEntry)
    qdrantClient.collections[collectionName] = existing


__all__ = [
    "pointIdForSku",
]
