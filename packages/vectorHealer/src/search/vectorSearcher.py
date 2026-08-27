"""Qdrant filtered vector similarity search client for substitute retrieval."""

from typing import Any, Dict, List, Optional
from pydantic import BaseModel, ConfigDict

from ..constants.healerConstants import (
    defaultMaxSearchCandidates,
    maxPriceDeltaPercent,
    minCosineSimilarity,
    qdrantCollectionName,
)
from .embeddingProvider import EmbeddingProvider


class ScoredPointCandidate(BaseModel):
    """Scored vector search candidate representing potential product substitute."""

    model_config = ConfigDict(frozen=True, extra="forbid")

    skuId: str
    score: float
    payload: Dict[str, Any]


def _getQdrantModels() -> Any:
    try:
        from qdrant_client import models
        return models
    except ImportError:
        class _MatchValue:
            def __init__(self, value: Any) -> None:
                self.value = value

        class _MatchAny:
            def __init__(self, any: List[Any]) -> None:
                self.any = any

        class _Range:
            def __init__(self, gte: Optional[float] = None, lte: Optional[float] = None) -> None:
                self.gte = gte
                self.lte = lte

        class _FieldCondition:
            def __init__(self, key: str, match: Optional[Any] = None, range: Optional[Any] = None) -> None:
                self.key = key
                self.match = match
                self.range = range

        class _Filter:
            def __init__(self, must: Optional[List[Any]] = None, must_not: Optional[List[Any]] = None) -> None:
                self.must = must or []
                self.must_not = must_not or []

        class _Models:
            MatchValue = _MatchValue
            MatchAny = _MatchAny
            Range = _Range
            FieldCondition = _FieldCondition
            Filter = _Filter

        return _Models


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
        rawPoints = self._executeRawVectorSearch(
            queryVector=queryVector,
            hsnCode=hsnCode,
            excludeSkuId=excludeSkuId,
            limit=limit,
            scoreThreshold=scoreThreshold,
        )
        qualified: List[ScoredPointCandidate] = []
        for pt in rawPoints:
            candidate = self._qualifyCandidate(
                pt=pt,
                originalPricePaise=originalPricePaise,
                requestedQuantity=requestedQuantity,
                maxPriceDeltaPct=maxPriceDeltaPct,
            )
            if candidate is not None:
                qualified.append(candidate)
        return qualified

    def _executeRawVectorSearch(
        self,
        queryVector: List[float],
        hsnCode: str,
        excludeSkuId: Optional[str],
        limit: int,
        scoreThreshold: float,
    ) -> List[Any]:
        """Executes search against Qdrant client if available, falling back to in-memory search."""
        if self._qdrant is not None and hasattr(self._qdrant, "search"):
            try:
                return self._qdrant.search(
                    collectionName=qdrantCollectionName,
                    queryVector=queryVector,
                    limit=limit,
                    scoreThreshold=scoreThreshold,
                    filterHsnCode=hsnCode,
                    excludeSkuId=excludeSkuId,
                )
            except TypeError:
                try:
                    models = _getQdrantModels()

                    mustConditions: List[Any] = [
                        models.FieldCondition(
                            key="availableStock",
                            range=models.Range(gte=1),
                        ),
                    ]
                    if hsnCode:
                        mustConditions.append(
                            models.FieldCondition(
                                key="hsnCode",
                                match=models.MatchValue(value=hsnCode),
                            )
                        )
                    mustNotConditions: List[Any] = []
                    if excludeSkuId:
                        mustNotConditions.append(
                            models.FieldCondition(
                                key="skuId",
                                match=models.MatchValue(value=excludeSkuId),
                            )
                        )
                    queryFilter = models.Filter(
                        must=mustConditions,
                        must_not=mustNotConditions if mustNotConditions else None,
                    )
                    return self._qdrant.search(
                        collection_name=qdrantCollectionName,
                        query_vector=queryVector,
                        query_filter=queryFilter,
                        limit=limit,
                        score_threshold=scoreThreshold,
                    )
                except Exception:
                    pass
            except Exception:
                pass
        return self._inMemorySearch(queryVector, hsnCode, excludeSkuId, scoreThreshold, limit)

    def _qualifyCandidate(
        self,
        pt: Any,
        originalPricePaise: int,
        requestedQuantity: int,
        maxPriceDeltaPct: float,
    ) -> Optional[ScoredPointCandidate]:
        """Validates inventory sufficiency and price delta threshold for candidate."""
        payload = (pt.payload if hasattr(pt, "payload") else pt.get("payload", {})) or {}
        rawScore = pt.score if hasattr(pt, "score") else pt.get("score", 0.0)
        score = float(rawScore) if rawScore is not None else 0.0
        candPrice = int(payload.get("baseUnitPricePaise", 0))
        candStock = int(payload.get("availableStock", 0))

        if candStock < requestedQuantity:
            return None

        if originalPricePaise <= 0:
            priceDeltaPct = 0.0 if candPrice == 0 else 100.0
        else:
            priceDeltaPct = abs(candPrice - originalPricePaise) / originalPricePaise * 100.0

        if priceDeltaPct > maxPriceDeltaPct:
            return None

        candidateSkuId = str(
            payload.get("skuId")
            or getattr(pt, "id", None)
            or getattr(pt, "skuId", None)
            or (pt.get("id") if isinstance(pt, dict) else "")
            or ""
        )
        return ScoredPointCandidate(skuId=candidateSkuId, score=score, payload=payload)

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


__all__ = [
    "ScoredPointCandidate",
    "VectorSearcher",
]
