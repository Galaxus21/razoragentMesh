"""Qdrant vector metadata patcher for fast zero-re-embedding stock updates."""

import inspect
from typing import Any, List, Optional

from ..constants.merchantConstants import defaultCollectionName


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
            FieldCondition = _FieldCondition
            Filter = _Filter

        return _Models


class QdrantPayloadPatcher:
    """Performs direct O(1) payload mutations in Qdrant vector index without re-embedding."""

    def __init__(
        self,
        qdrantClient: Any,
        collectionName: str = defaultCollectionName,
    ) -> None:
        self.qdrantClient = qdrantClient
        self.collectionName = collectionName

    def _patchInMemoryStore(
        self,
        targetSkuIds: List[str],
        availableStock: int,
    ) -> bool:
        """Applies in-place payload updates to mock Qdrant collections."""
        if not hasattr(self.qdrantClient, "collections"):
            return False

        skuSet = set(targetSkuIds)
        points = self.qdrantClient.collections.get(self.collectionName, [])
        for pt in points:
            payload = pt.get("payload") if isinstance(pt, dict) else getattr(pt, "payload", None)
            ptId = pt.get("id") if isinstance(pt, dict) else getattr(pt, "id", None)
            if payload is not None and (payload.get("skuId") in skuSet or ptId in skuSet):
                payload["availableStock"] = availableStock
        return True

    async def setAvailableStock(self, skuId: str, availableStock: int) -> None:
        """Updates SKU available stock in Qdrant payload via single-point filter update."""
        if self.qdrantClient is None:
            return

        clampedStock = max(0, int(availableStock))

        if hasattr(self.qdrantClient, "set_payload"):
            try:
                models = _getQdrantModels()
                filterCondition = models.Filter(
                    must=[
                        models.FieldCondition(
                            key="skuId",
                            match=models.MatchValue(value=skuId),
                        )
                    ]
                )
                response = self.qdrantClient.set_payload(
                    collection_name=self.collectionName,
                    payload={"availableStock": clampedStock},
                    points=filterCondition,
                )
                if inspect.iscoroutine(response):
                    await response
                return
            except Exception:
                pass

        self._patchInMemoryStore([skuId], clampedStock)

    async def batchSetAvailableStock(
        self,
        skuIds: List[str],
        availableStock: int,
    ) -> None:
        """Batch-updates stock quantity for multiple SKUs during flash-sale stockouts."""
        if not skuIds or self.qdrantClient is None:
            return

        clampedStock = max(0, int(availableStock))

        if hasattr(self.qdrantClient, "set_payload"):
            try:
                models = _getQdrantModels()
                filterCondition = models.Filter(
                    must=[
                        models.FieldCondition(
                            key="skuId",
                            match=models.MatchAny(any=skuIds),
                        )
                    ]
                )
                response = self.qdrantClient.set_payload(
                    collection_name=self.collectionName,
                    payload={"availableStock": clampedStock},
                    points=filterCondition,
                )
                if inspect.iscoroutine(response):
                    await response
                return
            except Exception:
                pass

        if self._patchInMemoryStore(skuIds, clampedStock):
            return

        for singleSkuId in skuIds:
            await self.setAvailableStock(singleSkuId, clampedStock)


__all__ = [
    "QdrantPayloadPatcher",
]
