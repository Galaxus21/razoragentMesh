"""Merchant product catalog CRUD routes."""

import logging
from typing import Any
from fastapi import APIRouter, Depends, status

from ..catalog.catalogManager import catalogManager
from ..exceptions.merchantExceptions import CatalogNotFoundException
from ..catalog.ingressSanitizer import sanitizeListingText
from ..schemas.universalProductSchema import UniversalProductListing
from .dependencies import getRedisClient, getVectorizer

catalogRouter = APIRouter(prefix="/api/v1/merchant", tags=["merchant-catalog"])

logger = logging.getLogger(__name__)


async def _indexListing(vectorizer: Any, listing: UniversalProductListing) -> None:
    """Adds the listing to the vector index, best effort.

    A vector-index failure must not fail the write: the listing is already in Redis and has
    already been published to the mesh, so raising here would report a completed publish as
    an error. Semantic discovery degrades; the listing is still quotable by id.
    """
    if vectorizer is None:
        return
    try:
        await vectorizer.upsertListing(listing)
    except Exception as err:
        logger.warning("Vector indexing failed for SKU '%s': %s", listing.skuId, err)


async def _deindexListing(vectorizer: Any, skuId: str) -> None:
    """Removes the listing from the vector index, best effort."""
    if vectorizer is None:
        return
    try:
        await vectorizer.removeListing(skuId)
    except Exception as err:
        logger.warning("Vector de-indexing failed for SKU '%s': %s", skuId, err)




@catalogRouter.post(
    "/{merchantDid}/catalog",
    status_code=status.HTTP_201_CREATED,
    summary="Create or upsert a SKU in the merchant catalog",
)
async def createSku(
    merchantDid: str,
    listing: UniversalProductListing,
    redis: Any = Depends(getRedisClient),
    vectorizer: Any = Depends(getVectorizer),
) -> dict[str, str]:
    """Upserts product listing into Redis catalog and syncs available inventory."""
    # The Merchant Studio path took a fully-formed listing as the request body and wrote it
    # unscrubbed, so a zero-width or Unicode Tags payload in a title landed in the catalog
    # having passed no shield at all.
    syncedListing = sanitizeListingText(
        listing.model_copy(update={"merchantDid": merchantDid})
    )
    await catalogManager.upsertListing(redis, syncedListing)
    await _indexListing(vectorizer, syncedListing)
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
    vectorizer: Any = Depends(getVectorizer),
) -> dict[str, str]:
    """Updates product attributes, inventory, and pricing in the catalog."""
    updatedListing = listing.model_copy(update={"merchantDid": merchantDid, "skuId": skuId})
    await catalogManager.upsertListing(redis, updatedListing)
    await _indexListing(vectorizer, updatedListing)
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
    vectorizer: Any = Depends(getVectorizer),
) -> dict[str, str]:
    """Deletes product listing and removes inventory stock keys."""
    listing = await catalogManager.getListing(redis, merchantDid, skuId)
    if listing is None:
        raise CatalogNotFoundException(f"SKU '{skuId}' not found for merchant '{merchantDid}'")
    await catalogManager.deleteListing(redis, merchantDid, skuId)
    await _deindexListing(vectorizer, skuId)
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
