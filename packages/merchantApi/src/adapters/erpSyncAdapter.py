"""ERP batch inventory and pricing synchronization adapter."""

from dataclasses import dataclass
from typing import Any, Optional

from ..constants.merchantConstants import maxCsvRowsPerBatch
from ..schemas.bulkIngestSchema import (
    ErpBatchSyncRequest,
    ErpBatchSyncResult,
)


@dataclass(frozen=True)
class ErpDeltaResult:
    """Immutable result for individual ERP stock or price synchronization delta."""

    skuId: str
    applied: bool
    reason: Optional[str] = None


def processErpDelta(delta: dict[str, Any]) -> Optional[tuple[str, int, Optional[int]]]:
    """Parses and validates a single ERP inventory/price delta dictionary."""
    if not isinstance(delta, dict):
        return None

    skuId = delta.get("skuId")
    if not skuId or not isinstance(skuId, str) or not skuId.strip():
        return None

    stockDeltaRaw = delta.get("stockDelta")
    if stockDeltaRaw is None:
        return None

    try:
        stockDelta = int(stockDeltaRaw)
    except (ValueError, TypeError):
        return None

    newPriceRaw = delta.get("newPricePaise")
    newPricePaise: Optional[int] = None
    if newPriceRaw is not None:
        try:
            newPricePaise = int(newPriceRaw)
            if newPricePaise < 0:
                return None
        except (ValueError, TypeError):
            return None

    return skuId.strip(), stockDelta, newPricePaise


def processBatchSync(
    request: ErpBatchSyncRequest,
) -> tuple[list[ErpDeltaResult], ErpBatchSyncResult]:
    """Processes batch ERP sync request up to maximum allowed delta limits."""
    deltaResults: list[ErpDeltaResult] = []
    rejectedSkuIds: list[str] = []
    deltas = request.deltas[:maxCsvRowsPerBatch]
    appliedCount = 0
    rejectedCount = 0

    for delta in deltas:
        parsed = processErpDelta(delta) if isinstance(delta, dict) else None
        if parsed is None:
            rejectedCount += 1
            sku = str(delta.get("skuId", "unknown")) if isinstance(delta, dict) else "unknown"
            rejectedSkuIds.append(sku)
            deltaResults.append(
                ErpDeltaResult(skuId=sku, applied=False, reason="Invalid delta schema or price format")
            )
        else:
            appliedCount += 1
            skuId, _, _ = parsed
            deltaResults.append(ErpDeltaResult(skuId=skuId, applied=True, reason=None))

    syncResult = ErpBatchSyncResult(
        batchId=request.batchId,
        appliedCount=appliedCount,
        rejectedCount=rejectedCount,
        rejectedSkuIds=rejectedSkuIds,
    )
    return deltaResults, syncResult


__all__ = [
    "ErpDeltaResult",
    "processBatchSync",
    "processErpDelta",
]
