"""Qdrant filtered vector similarity search client for substitute retrieval."""

import math
from typing import Any, Dict, List, Optional
from pydantic import BaseModel, ConfigDict, Field

from razoragentMesh.packages.vectorHealer.embeddingProvider import EmbeddingProvider
from razoragentMesh.packages.vectorHealer.healerConstants import (
    defaultMaxSearchCandidates,
    maxPriceDeltaPercent,
    minCosineSimilarity,
    qdrantCollectionName,
)


class ScoredPointCandidate(BaseModel):
    """Scored vector search candidate representing potential product substitute."""

    model_config = ConfigDict(frozen=True, extra="forbid")

    skuId: str
    score: float
    payload: Dict[str, Any]


class VectorSearcher:
    """Performs filtered approximate nearest neighbor (ANN) search on product embeddings."""

    def __init__(
        self,
        qdrantClient: Optional[Any] = None,
        catalogStore: Optional[List[Dict[str, Any]]] = None,
    ) -> None:
        self._qdrant = qdrantClient
        self._catalog = {s["skuId"]: s for s in (catalogStore or [])}
        self._embeddingProvider = EmbeddingProvider()

    def _inMemorySearch(
        self,
        queryVector: List[float],
        hsnCode: str,
        excludeSkuId: Optional[str],
        scoreThreshold: float,
        limit: int,
    ) -> List[ScoredPointCandidate]:
        """Fallback in-memory cosine search over catalog fixtures."""
        candidates: List[ScoredPointCandidate] = []
        for skuId, item in self._catalog.items():
            if excludeSkuId and skuId == excludeSkuId:
                continue
            if item.get("hsnCode") != hsnCode:
                continue
            itemVector = item.get("embeddingVector")
            if not itemVector:
                continue
            sim = self._embeddingProvider.computeCosineSimilarity(queryVector, itemVector)
            if sim >= scoreThreshold:
                candidates.append(ScoredPointCandidate(skuId=skuId, score=sim, payload=item))
        candidates.sort(key=lambda c: c.score, reverse=True)
        return candidates[:limit]

    def searchCandidates(
        self,
        queryVector: List[float],
        hsnCode: str,
        originalPricePaise: int,
        requestedQuantity: int,
        excludeSkuId: Optional[str] = None,
        limit: int = defaultMaxSearchCandidates,
        scoreThreshold: float = minCosineSimilarity,
        maxPriceDeltaPct: float = maxPriceDeltaPercent,
    ) -> List[ScoredPointCandidate]:
        """Queries vector index with HSN, stock, and price-delta filters."""
        rawPoints: List[Any] = []
        if self._qdrant is not None and hasattr(self._qdrant, "search"):
            rawPoints = self._qdrant.search(
                collectionName=qdrantCollectionName,
                queryVector=queryVector,
                limit=limit,
                scoreThreshold=scoreThreshold,
                filterHsnCode=hsnCode,
                excludeSkuId=excludeSkuId,
            )
        else:
            rawPoints = self._inMemorySearch(queryVector, hsnCode, excludeSkuId, scoreThreshold, limit)

        qualified: List[ScoredPointCandidate] = []
        for pt in rawPoints:
            payload = pt.payload if hasattr(pt, "payload") else pt.get("payload", {})
            score = pt.score if hasattr(pt, "score") else pt.get("score", 0.0)
            candPrice = payload.get("baseUnitPricePaise", 0)
            candStock = payload.get("availableStock", 0)

            if candStock < requestedQuantity:
                continue

            priceDeltaPct = abs(candPrice - originalPricePaise) / originalPricePaise * 100.0
            if priceDeltaPct > maxPriceDeltaPct:
                continue

            candidateSkuId = payload.get("skuId", "")
            qualified.append(ScoredPointCandidate(skuId=candidateSkuId, score=score, payload=payload))

        return qualified
