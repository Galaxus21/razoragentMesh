"""Schemas for CSV catalog ingestion, Shopify webhook processing, and ERP batch sync."""

from typing import Any, Optional
from pydantic import BaseModel, ConfigDict

# Ingestion Defaults
defaultMoq: int = 1
defaultShopifyTags: str = ""


class CsvIngestRow(BaseModel):
    """Single row schema parsed from merchant catalog CSV upload."""

    model_config = ConfigDict(extra="forbid")

    skuId: str
    title: str
    category: str
    description: str
    hsnCode: str
    basePriceInr: str
    availableStock: int
    moq: int = defaultMoq
    volumeTiersJson: Optional[str] = None
    allergens: Optional[str] = None
    brand: Optional[str] = None
    weightGrams: Optional[int] = None
    originPincode: str


class CsvRowFailure(BaseModel):
    """Detailed error record for a failed CSV row ingestion."""

    model_config = ConfigDict(frozen=True, extra="forbid")

    rowIndex: int
    skuId: Optional[str] = None
    reason: str


class CsvIngestResult(BaseModel):
    """Aggregate result from processing a CSV catalog upload batch."""

    model_config = ConfigDict(frozen=True, extra="forbid")

    totalRowsProcessed: int
    successCount: int
    failureCount: int
    failedSkuIds: list[str]


class ShopifyWebhookPayload(BaseModel):
    """Payload schema for inbound Shopify product webhook notifications."""

    # Note: extra="allow" and body_html match Shopify external webhook contracts
    model_config = ConfigDict(extra="allow")

    id: int
    title: str
    body_html: Optional[str] = None
    variants: list[dict[str, Any]]
    tags: str = defaultShopifyTags


class ErpBatchSyncRequest(BaseModel):
    """Request schema for batch synchronization of inventory and prices from ERP."""

    model_config = ConfigDict(frozen=True, extra="forbid")

    merchantDid: str
    batchId: str
    deltas: list[dict[str, Any]]


class ErpBatchSyncResult(BaseModel):
    """Result summary for an ERP inventory/price batch synchronization run."""

    model_config = ConfigDict(frozen=True, extra="forbid")

    batchId: str
    appliedCount: int
    rejectedCount: int
    rejectedSkuIds: list[str]


__all__ = [
    "CsvIngestResult",
    "CsvIngestRow",
    "CsvRowFailure",
    "ErpBatchSyncRequest",
    "ErpBatchSyncResult",
    "ShopifyWebhookPayload",
    "defaultMoq",
    "defaultShopifyTags",
]
