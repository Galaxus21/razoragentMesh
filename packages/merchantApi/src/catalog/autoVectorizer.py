"""384-dimensional vector catalog indexer maintaining the Qdrant product index."""

import inspect
import logging
from typing import Any, Dict, List

from ..constants.merchantConstants import (
    defaultCollectionName, embeddingModeHash, modelNameMiniLm,
)
from ..schemas.universalProductSchema import UniversalProductListing
from .embeddingEngine import _EmbeddingEngine
from .facetTextSynthesizer import synthesizeFacetDescription
from .qdrantPointDispatch import (
    _buildQdrantPayload,
    _dispatchQdrantClientUpsert,
    _getQdrantModels,
    _upsertToMemoryCollection,
    pointIdForSku,
)

logger = logging.getLogger(__name__)


class AutoVectorizer:
    """Extracts facet-rich embeddings and maintains the Qdrant product vector index."""

    def __init__(self, qdrantClient: Any, collectionName: str = defaultCollectionName) -> None:
        self.qdrantClient = qdrantClient
        self.collectionName = collectionName
        self._engine = _EmbeddingEngine(modelName=modelNameMiniLm)

    async def searchListings(self, queryText: str, limit: int) -> tuple[List[Dict[str, Any]], str]:
        """Ranks catalog entries against a natural-language query.

        Returns the hits and the embedding mode that produced them. The mode is returned rather
        than logged because a caller showing these results to a person has to be able to say
        whether they came from a language model or from a character hash -- cosine over the
        latter ranks by incidental character overlap, not meaning.
        """
        queryVector, mode = self._engine.embedWithMode(queryText)
        if self.qdrantClient is None:
            return [], mode

        try:
            res = self.qdrantClient.query_points(
                collection_name=self.collectionName,
                query=queryVector,
                limit=limit,
                with_payload=True,
            )
            if inspect.iscoroutine(res):
                res = await res
            points = getattr(res, "points", res)
            return [_describeSearchHit(point) for point in points], mode
        except Exception as err:
            # Reported, not swallowed into an empty result: "no matches" and "the vector store
            # is down" look identical to a caller otherwise, and an agent would conclude the
            # product does not exist.
            logger.warning("Qdrant search failed on collection '%s': %s", self.collectionName, err)
            raise

    async def upsertListing(self, listing: UniversalProductListing) -> None:
        """Embeds synthesized facet text and upserts vector and metadata into Qdrant."""
        if self.qdrantClient is None:
            return

        richText = synthesizeFacetDescription(listing)
        vector, mode = self._engine.embedWithMode(richText)
        if mode == embeddingModeHash:
            logger.warning(
                "Indexing SKU '%s' with a character-hash pseudo-vector: semantic search over "
                "this entry will not be meaningful.",
                listing.skuId,
            )
        payload = _buildQdrantPayload(listing)

        pointId = pointIdForSku(listing.skuId)
        dispatched = await _dispatchQdrantClientUpsert(
            self.qdrantClient, self.collectionName, pointId, vector, payload
        )
        if not dispatched:
            pointEntry = {"id": pointId, "vector": vector, "payload": payload}
            _upsertToMemoryCollection(self.qdrantClient, self.collectionName, pointEntry, pointId)

    async def removeListing(self, skuId: str) -> None:
        """Deletes vector and metadata point from Qdrant by SKU identifier."""
        if self.qdrantClient is None:
            return

        if hasattr(self.qdrantClient, "delete"):
            try:
                models = _getQdrantModels()

                res = self.qdrantClient.delete(
                    collection_name=self.collectionName,
                    points_selector=models.PointIdsList(points=[pointIdForSku(skuId)]),
                )
                if inspect.iscoroutine(res):
                    await res
                return
            except Exception as err:
                logger.warning("Qdrant delete failed for SKU '%s': %s", skuId, err)

        if hasattr(self.qdrantClient, "collections") and self.collectionName in self.qdrantClient.collections:
            pointId = pointIdForSku(skuId)
            self.qdrantClient.collections[self.collectionName] = [
                p for p in self.qdrantClient.collections[self.collectionName]
                if (p.get("id") if isinstance(p, dict) else getattr(p, "id", None)) != pointId
            ]


def _describeSearchHit(point: Any) -> Dict[str, Any]:
    """Flattens one Qdrant hit into a plain dict an agent can act on.

    Tolerates both the object form the real client returns and the dict form the in-memory
    fallback stores, so a caller does not have to know which produced the hit.
    """
    if isinstance(point, dict):
        payload = point.get("payload") or {}
        identifier = point.get("id")
        score = point.get("score")
    else:
        payload = getattr(point, "payload", None) or {}
        identifier = getattr(point, "id", None)
        score = getattr(point, "score", None)

    return {
        "skuId": payload.get("skuId") or identifier,
        "title": payload.get("title"),
        "category": payload.get("category"),
        "baseUnitPricePaise": payload.get("baseUnitPricePaise"),
        "availableStock": payload.get("availableStock"),
        "gstRatePercent": payload.get("gstRatePercent"),
        "hsnCode": payload.get("hsnCode"),
        "merchantDid": payload.get("merchantDid"),
        "score": score,
    }


__all__ = [
    "AutoVectorizer",
    "synthesizeFacetDescription",
]
