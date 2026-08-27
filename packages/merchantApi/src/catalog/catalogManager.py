"""Catalog persistence manager with Redis storage and pub/sub broadcast."""

import json
import time
from typing import Any, List, Optional

from ..constants.merchantConstants import (
    catalogUpdateActionAdded,
    catalogUpdateActionRemoved,
    catalogUpdateActionUpdated,
    inventoryStockPrefix,
    redisCatalogHashKeyPrefix,
    redisCatalogKeyPrefix,
    redisCatalogUpdatesChannel,
    redisMerchantCatalogPrefix,
)
from ..schemas.universalProductSchema import UniversalProductListing


class CatalogManager:
    """Manages Redis hash lifecycle and event propagation for merchant product listings."""

    def __init__(self, redisClient: Any = None) -> None:
        self.redisClient = redisClient

    async def _publishEvent(
        self,
        action: str,
        skuId: str,
        merchantDid: str,
        item: Optional[dict[str, Any]] = None,
    ) -> None:
        """Emits catalog mutation notifications onto pub/sub channel for indexers."""
        if not hasattr(self.redisClient, "publish"):
            return
        payloadDict: dict[str, Any] = {
            "action": action,
            "skuId": skuId,
            "merchantDid": merchantDid,
            "timestamp": int(time.time()),
        }
        if item is not None:
            payloadDict["item"] = item
        eventPayload = json.dumps(payloadDict)
        await self.redisClient.publish(redisCatalogUpdatesChannel, eventPayload)

    async def upsertSku(self, listing: UniversalProductListing) -> None:
        """Stores or updates product listing JSON in Redis and publishes event."""
        key = f"{redisCatalogHashKeyPrefix}{listing.skuId}"
        existingRecord = await self.redisClient.get(key)
        action = (
            catalogUpdateActionUpdated
            if existingRecord is not None
            else catalogUpdateActionAdded
        )

        serializedListing = listing.model_dump_json()
        await self.redisClient.set(key, serializedListing)
        itemPayload = {
            "skuId": listing.skuId,
            "name": listing.title,
            "category": listing.category,
            "description": listing.description,
            "hsnCode": listing.hsnCode,
            "gstRatePercent": listing.gstRatePercent,
            "baseUnitPricePaise": listing.baseUnitPricePaise,
            "availableStock": listing.availableStock,
            "volumeTiers": [tier.model_dump() for tier in listing.volumeTiers],
            "originPincode": listing.originPincode,
        }
        await self._publishEvent(action, listing.skuId, listing.merchantDid, item=itemPayload)

    async def removeSku(self, skuId: str, merchantDid: str) -> bool:
        """Deletes SKU from Redis storage and publishes catalog removal event."""
        key = f"{redisCatalogHashKeyPrefix}{skuId}"
        existingRecord = await self.redisClient.get(key)
        if existingRecord is None:
            return False

        if hasattr(self.redisClient, "delete"):
            await self.redisClient.delete(key)
        elif hasattr(self.redisClient, "store") and isinstance(self.redisClient.store, dict):
            self.redisClient.store.pop(key, None)

        await self._publishEvent(catalogUpdateActionRemoved, skuId, merchantDid)
        return True

    async def getSku(self, skuId: str) -> Optional[UniversalProductListing]:
        """Fetches and deserializes product listing from Redis hash."""
        key = f"{redisCatalogHashKeyPrefix}{skuId}"
        rawPayload = await self.redisClient.get(key)
        if rawPayload is None:
            return None
        rawText = rawPayload.decode("utf-8") if isinstance(rawPayload, bytes) else str(rawPayload)
        return UniversalProductListing.model_validate_json(rawText)

    async def listMerchantSkus(self, merchantDid: str) -> List[str]:
        """Scans catalog keys and returns SKU identifiers belonging to the specified merchant."""
        candidateKeys: List[str] = []
        if hasattr(self.redisClient, "keys"):
            candidateKeys = await self.redisClient.keys(f"{redisCatalogHashKeyPrefix}*")
        elif hasattr(self.redisClient, "store") and isinstance(self.redisClient.store, dict):
            candidateKeys = [
                redisKey for redisKey in self.redisClient.store.keys()
                if redisKey.startswith(redisCatalogHashKeyPrefix)
            ]

        matchingSkus: List[str] = []
        for key in candidateKeys:
            rawPayload = await self.redisClient.get(key)
            if rawPayload is None:
                continue
            rawText = rawPayload.decode("utf-8") if isinstance(rawPayload, bytes) else str(rawPayload)
            itemData = json.loads(rawText)
            if itemData.get("merchantDid") == merchantDid:
                skuId = itemData.get("skuId", key.replace(redisCatalogHashKeyPrefix, ""))
                matchingSkus.append(skuId)

        return matchingSkus

    @staticmethod
    async def upsertListing(redisClient: Any, listing: UniversalProductListing) -> None:
        """Static helper to persist a universal product listing and synchronize inventory."""
        manager = CatalogManager(redisClient=redisClient)
        await manager.upsertSku(listing)
        merchantKey = f"{redisMerchantCatalogPrefix}{listing.merchantDid}:{listing.skuId}"
        stockKey = f"{redisCatalogKeyPrefix}{listing.skuId}:stock"
        inventoryStockKey = f"{inventoryStockPrefix}{listing.skuId}"
        await redisClient.set(merchantKey, listing.model_dump_json())
        await redisClient.set(stockKey, str(listing.availableStock))
        await redisClient.set(inventoryStockKey, str(listing.availableStock))

    @staticmethod
    async def getListing(
        redisClient: Any,
        merchantDid: str,
        skuId: str,
    ) -> Optional[UniversalProductListing]:
        """Static helper to retrieve a product listing by merchant DID and SKU identifier."""
        manager = CatalogManager(redisClient=redisClient)
        result = await manager.getSku(skuId)
        if result is not None:
            return result
        merchantKey = f"{redisMerchantCatalogPrefix}{merchantDid}:{skuId}"
        raw = await redisClient.get(merchantKey)
        if not raw:
            return None
        rawText = raw.decode("utf-8") if isinstance(raw, bytes) else str(raw)
        return UniversalProductListing.model_validate_json(rawText)

    @staticmethod
    async def deleteListing(
        redisClient: Any,
        merchantDid: str,
        skuId: str,
    ) -> bool:
        """Static helper to remove SKU listing and related stock keys from Redis store."""
        manager = CatalogManager(redisClient=redisClient)
        removed = await manager.removeSku(skuId, merchantDid)
        merchantKey = f"{redisMerchantCatalogPrefix}{merchantDid}:{skuId}"
        stockKey = f"{redisCatalogKeyPrefix}{skuId}:stock"
        inventoryStockKey = f"{inventoryStockPrefix}{skuId}"
        if hasattr(redisClient, "delete"):
            await redisClient.delete(merchantKey, stockKey, inventoryStockKey)
        elif hasattr(redisClient, "store") and isinstance(redisClient.store, dict):
            redisClient.store.pop(merchantKey, None)
            redisClient.store.pop(stockKey, None)
            redisClient.store.pop(inventoryStockKey, None)
        return removed

    @staticmethod
    async def applyStockPriceDelta(
        redisClient: Any,
        skuId: str,
        stockDelta: int,
        newPricePaise: Optional[int] = None,
    ) -> bool:
        """Applies inventory quantity adjustments and updates price in place."""
        manager = CatalogManager(redisClient=redisClient)
        listing = await manager.getSku(skuId)
        if not listing:
            return False

        updatedStock = max(0, listing.availableStock + stockDelta)
        updatedPrice = newPricePaise if newPricePaise is not None else listing.baseUnitPricePaise

        updatedListing = listing.model_copy(
            update={
                "availableStock": updatedStock,
                "baseUnitPricePaise": updatedPrice,
            }
        )
        await CatalogManager.upsertListing(redisClient, updatedListing)
        return True


catalogManager = CatalogManager()

__all__ = [
    "CatalogManager",
    "catalogManager",
]
