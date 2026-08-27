"""Merchant product catalog CRUD routes."""

from typing import Any
from fastapi import APIRouter, Depends, status

from ..catalog.catalogManager import catalogManager
from ..exceptions.merchantExceptions import CatalogNotFoundException
from ..schemas.universalProductSchema import UniversalProductListing
from .dependencies import getRedisClient

catalogRouter = APIRouter(prefix="/api/v1/merchant", tags=["merchant-catalog"])


@catalogRouter.post(
    "/{merchantDid}/catalog",
    status_code=status.HTTP_201_CREATED,
    summary="Create or upsert a SKU in the merchant catalog",
)
async def createSku(
    merchantDid: str,
    listing: UniversalProductListing,
    redis: Any = Depends(getRedisClient),
) -> dict[str, str]:
    """Upserts product listing into Redis catalog and syncs available inventory."""
    syncedListing = listing.model_copy(update={"merchantDid": merchantDid})
    await catalogManager.upsertListing(redis, syncedListing)
    return {
        "status": "created",
        "skuId": syncedListing.skuId,
        "merchantDid": merchantDid,
    }


@catalogRouter.get(
    "/{merchantDid}/catalog/{skuId}",
    response_model=UniversalProductListing,
    summary="Fetch SKU listing from merchant catalog",
)
async def getSku(
    merchantDid: str,
    skuId: str,
    redis: Any = Depends(getRedisClient),
) -> UniversalProductListing:
    """Retrieves a single product listing by merchant DID and SKU identifier."""
    listing = await catalogManager.getListing(redis, merchantDid, skuId)
    if listing is None:
        raise CatalogNotFoundException(f"SKU '{skuId}' not found for merchant '{merchantDid}'")
    return listing


@catalogRouter.put(
    "/{merchantDid}/catalog/{skuId}",
    summary="Update an existing SKU in the merchant catalog",
)
async def updateSku(
    merchantDid: str,
    skuId: str,
    listing: UniversalProductListing,
    redis: Any = Depends(getRedisClient),
) -> dict[str, str]:
    """Updates product attributes, inventory, and pricing in the catalog."""
    updatedListing = listing.model_copy(update={"merchantDid": merchantDid, "skuId": skuId})
    await catalogManager.upsertListing(redis, updatedListing)
    return {
        "status": "updated",
        "skuId": skuId,
        "merchantDid": merchantDid,
    }


@catalogRouter.delete(
    "/{merchantDid}/catalog/{skuId}",
    summary="Delete a SKU from the merchant catalog",
)
async def deleteSku(
    merchantDid: str,
    skuId: str,
    redis: Any = Depends(getRedisClient),
) -> dict[str, str]:
    """Deletes product listing and removes inventory stock keys."""
    listing = await catalogManager.getListing(redis, merchantDid, skuId)
    if listing is None:
        raise CatalogNotFoundException(f"SKU '{skuId}' not found for merchant '{merchantDid}'")
    await catalogManager.deleteListing(redis, merchantDid, skuId)
    return {
        "status": "deleted",
        "skuId": skuId,
        "merchantDid": merchantDid,
    }


__all__ = [
    "catalogRouter",
    "createSku",
    "deleteSku",
    "getSku",
    "updateSku",
]
