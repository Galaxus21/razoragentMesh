"""Bulk ingestion routes supporting CSV files, Shopify webhooks, and ERP syncs."""

from typing import Any
from fastapi import APIRouter, Depends, File, UploadFile

from ..adapters.csvIngestionAdapter import ingestCsvContent
from ..adapters.erpSyncAdapter import (
    processBatchSync,
    processErpDelta,
)
from ..adapters.shopifyStoreAdapter import processShopifyWebhook
from ..catalog.catalogManager import catalogManager
from ..schemas.bulkIngestSchema import (
    CsvIngestResult,
    ErpBatchSyncRequest,
    ErpBatchSyncResult,
    ShopifyWebhookPayload,
)
from .catalogRoute import _indexListing
from .dependencies import getRedisClient, getVectorizer

bulkIngestRouter = APIRouter(prefix="/api/v1/merchant", tags=["bulk-ingest"])


@bulkIngestRouter.post(
    "/{merchantDid}/bulk-csv",
    response_model=CsvIngestResult,
    summary="Upload and ingest bulk catalog CSV file",
)
async def ingestCsvBulk(
    merchantDid: str,
    file: UploadFile = File(...),
    redis: Any = Depends(getRedisClient),
    vectorizer: Any = Depends(getVectorizer),
) -> CsvIngestResult:
    """Reads CSV file upload, validates catalog rows, and indexes valid SKUs into Redis."""
    rawBytes = await file.read()
    csvText = rawBytes.decode("utf-8", errors="replace")

    listings, result = ingestCsvContent(csvText, merchantDid)
    for listing in listings:
        await catalogManager.upsertListing(redis, listing)
        # Without this a bulk-ingested SKU is quotable by id but invisible to search_catalog,
        # which is the same defect the compiled fixtures had. Best effort, as on the single-SKU
        # route: the listing is already written and published.
        await _indexListing(vectorizer, listing)

    return result


@bulkIngestRouter.post(
    "/{merchantDid}/shopify-sync",
    summary="Handle incoming Shopify product update webhooks",
)
async def shopifyWebhookSync(
    merchantDid: str,
    payload: ShopifyWebhookPayload,
    redis: Any = Depends(getRedisClient),
    vectorizer: Any = Depends(getVectorizer),
) -> dict[str, Any]:
    """Ingests Shopify product payload across all variants into merchant catalog."""
    listings = processShopifyWebhook(payload, merchantDid)
    for listing in listings:
        await catalogManager.upsertListing(redis, listing)
        await _indexListing(vectorizer, listing)

    return {
        "status": "synchronized",
        "count": len(listings),
        "skuIds": [listing.skuId for listing in listings],
    }


@bulkIngestRouter.post(
    "/{merchantDid}/erp-sync",
    response_model=ErpBatchSyncResult,
    summary="Process batch ERP inventory and price synchronization deltas",
)
async def erpBatchSync(
    merchantDid: str,
    request: ErpBatchSyncRequest,
    redis: Any = Depends(getRedisClient),
) -> ErpBatchSyncResult:
    """Applies batch ERP inventory and pricing deltas against active catalog."""
    _, syncResult = processBatchSync(request)

    for delta in request.deltas:
        if isinstance(delta, dict):
            parsed = processErpDelta(delta)
            if parsed is not None:
                skuId, stockDelta, newPricePaise = parsed
                await catalogManager.applyStockPriceDelta(redis, skuId, stockDelta, newPricePaise)

    return syncResult


__all__ = [
    "bulkIngestRouter",
    "erpBatchSync",
    "ingestCsvBulk",
    "shopifyWebhookSync",
]
