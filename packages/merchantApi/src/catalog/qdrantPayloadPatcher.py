"""Qdrant vector metadata patcher for fast zero-re-embedding availability updates."""

import inspect
from typing import Any, List

from ..constants.merchantConstants import defaultCollectionName


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
        isAvailable: bool,
    ) -> bool:
        """Applies in-place payload updates to mock Qdrant collections."""
        if not hasattr(self.qdrantClient, "collections"):
            return False

        skuSet = set(targetSkuIds)
        points = self.qdrantClient.collections.get(self.collectionName, [])
        for pt in points:
            payload = pt.get("payload") if isinstance(pt, dict) else getattr(pt, "payload", None)
            if payload is not None and payload.get("skuId") in skuSet:
                payload["isAvailable"] = isAvailable
        return True

    async def setAvailability(self, skuId: str, isAvailable: bool) -> None:
        """Toggles SKU availability flag in Qdrant payload via single-point filter update."""
        if self.qdrantClient is None:
            return

        if hasattr(self.qdrantClient, "set_payload"):
            try:
                from qdrant_client import models

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
                    payload={"isAvailable": isAvailable},
                    points=filterCondition,
                )
                if inspect.iscoroutine(response):
                    await response
                return
            except Exception:
                pass

        self._patchInMemoryStore([skuId], isAvailable)

    async def batchSetAvailability(
        self,
        skuIds: List[str],
        isAvailable: bool,
    ) -> None:
        """Batch-updates availability status for multiple SKUs during flash-sale stockouts."""
        if not skuIds or self.qdrantClient is None:
            return

        if hasattr(self.qdrantClient, "set_payload"):
            try:
                from qdrant_client import models

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
                    payload={"isAvailable": isAvailable},
                    points=filterCondition,
                )
                if inspect.iscoroutine(response):
                    await response
                return
            except Exception:
                pass

        if self._patchInMemoryStore(skuIds, isAvailable):
            return

        for singleSkuId in skuIds:
            await self.setAvailability(singleSkuId, isAvailable)


__all__ = [
    "QdrantPayloadPatcher",
]
