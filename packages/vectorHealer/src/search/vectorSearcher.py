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
        """Queries the vector index, falling back to an in-memory cosine when it cannot.

        `query_points` is tried first because `QdrantClient.search` was REMOVED in qdrant-client
        1.19, which is the version the merchant API image installs. The old guard here was
        `hasattr(self._qdrant, "search")`, so against a modern client the whole Qdrant branch was
        skipped and every substitution search silently became the in-memory path -- a cosine over
        whatever `embeddingVector` happened to be in the Redis listing.

        That is why Layer 3 had never healed anything outside its own tests. Only
        `scripts/seedCatalog.py` writes `embeddingVector`, so the in-memory path could see 25 of
        47 listings and none of the SKUs a merchant publishes. Measured 2026-09-04:
        `SKU-TEST-DESK-OOS` returned no substitute at a 0.0 similarity floor and a 500% price
        band, while the index itself ranked `SKU-TEST-DESK-LASTONE` at cosine 0.8697 for it.

        The legacy `search` paths are kept below because the healer's own tests drive fakes that
        expose `search` and nothing else, and because a client older than 1.19 is still valid.
        """
        if self._qdrant is not None:
            points = self._queryPointsSearch(
                queryVector, hsnCode, excludeSkuId, limit, scoreThreshold
            )
            if points is not None:
                return points
            points = self._legacySearch(queryVector, hsnCode, excludeSkuId, limit, scoreThreshold)
            if points is not None:
                return points
        return self._inMemorySearch(queryVector, hsnCode, excludeSkuId, scoreThreshold, limit)

    def _buildQueryFilter(self, hsnCode: str, excludeSkuId: Optional[str]) -> Any:
        """In-stock, same HSN, and never the SKU that just failed."""
        models = _getQdrantModels()
        mustConditions: List[Any] = [
            models.FieldCondition(key="availableStock", range=models.Range(gte=1)),
        ]
        if hsnCode:
            mustConditions.append(
                models.FieldCondition(key="hsnCode", match=models.MatchValue(value=hsnCode))
            )
        mustNotConditions: List[Any] = []
        if excludeSkuId:
            mustNotConditions.append(
                models.FieldCondition(key="skuId", match=models.MatchValue(value=excludeSkuId))
            )
        return models.Filter(
            must=mustConditions,
            must_not=mustNotConditions if mustNotConditions else None,
        )

    def _queryPointsSearch(
        self,
        queryVector: List[float],
        hsnCode: str,
        excludeSkuId: Optional[str],
        limit: int,
        scoreThreshold: float,
    ) -> Optional[List[Any]]:
        """The current Qdrant API. None means "could not run", never "found nothing"."""
        if not hasattr(self._qdrant, "query_points") or not queryVector:
            return None
        try:
            response = self._qdrant.query_points(
                collection_name=qdrantCollectionName,
                query=queryVector,
                query_filter=self._buildQueryFilter(hsnCode, excludeSkuId),
                limit=limit,
                score_threshold=scoreThreshold,
                with_payload=True,
            )
        except Exception:
            return None
        points = getattr(response, "points", response)
        return list(points) if isinstance(points, (list, tuple)) else None

    def _legacySearch(
        self,
        queryVector: List[float],
        hsnCode: str,
        excludeSkuId: Optional[str],
        limit: int,
        scoreThreshold: float,
    ) -> Optional[List[Any]]:
        """qdrant-client < 1.19, and the test fakes that mimic it."""
        if not hasattr(self._qdrant, "search"):
            return None
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
                return self._qdrant.search(
                    collection_name=qdrantCollectionName,
                    query_vector=queryVector,
                    query_filter=self._buildQueryFilter(hsnCode, excludeSkuId),
                    limit=limit,
                    score_threshold=scoreThreshold,
                )
            except Exception:
                return None
        except Exception:
            return None

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
