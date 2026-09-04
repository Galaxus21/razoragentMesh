"""Merchant product catalog CRUD routes."""

import logging
from typing import Any
from fastapi import APIRouter, Depends, status

from pydantic import BaseModel, ConfigDict, Field

from ..catalog.catalogManager import catalogManager
from ..exceptions.merchantExceptions import CatalogNotFoundException
from ..catalog.ingressSanitizer import sanitizeListingText
from ..schemas.universalProductSchema import UniversalProductListing
from .dependencies import getRedisClient, getVectorizer

# Imported rather than re-implemented on purpose. `mesh:catalog:*` holds four value shapes under
# one prefix -- the listing, its `{merchantDid}:{skuId}` duplicate, a bare stock integer -- and
# _loadCatalogStore is the one place that knows how to read past all of them. A second scan
# written here would be a second, quietly divergent definition of "the catalog", and the two
# would disagree the first time that keyspace changed.
from .oosHealingRoute import _loadCatalogStore

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




class CatalogSummaryItem(BaseModel):
    """A listing reduced to what a picker needs to show and to charge for."""

    model_config = ConfigDict(frozen=True, extra="forbid")

    skuId: str
    title: str
    baseUnitPricePaise: int = Field(ge=0)
    gstRatePercent: int = Field(ge=0)
    availableStock: int = Field(ge=0)


class CatalogSummaryResponse(BaseModel):
    """The merchant's published SKUs, newest-agnostic and ordered by skuId."""

    model_config = ConfigDict(frozen=True, extra="forbid")

    merchantDid: str
    items: list[CatalogSummaryItem]


@catalogRouter.get(
    "/{merchantDid}/catalog",
    response_model=CatalogSummaryResponse,
    summary="List every SKU this merchant has published to the mesh",
)
async def listSkus(
    merchantDid: str,
    redis: Any = Depends(getRedisClient),
) -> CatalogSummaryResponse:
    """Enumerates the merchant's catalog.

    Deliberately a summary rather than the full UniversalProductListing: this endpoint exists so
    a human checkout page can offer the SKUs a merchant just published, and returning the strict
    model would make one stale or partially-seeded record fail the whole listing with a 500. A
    record missing any of the five fields is skipped, so a bad row costs its own line and not
    the page.
    """
    entries = await _loadCatalogStore(redis)

    items: list[CatalogSummaryItem] = []
    for entry in entries:
        if entry.get("merchantDid") != merchantDid:
            continue
        try:
            items.append(
                CatalogSummaryItem(
                    skuId=entry["skuId"],
                    title=entry["title"],
                    baseUnitPricePaise=int(entry["baseUnitPricePaise"]),
                    gstRatePercent=int(entry["gstRatePercent"]),
                    availableStock=int(entry.get("availableStock", 0)),
                )
            )
        except (KeyError, TypeError, ValueError) as err:
            logger.warning("Skipping malformed catalog record for merchant %s: %s", merchantDid, err)

    items.sort(key=lambda item: item.skuId)
    return CatalogSummaryResponse(merchantDid=merchantDid, items=items)


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
