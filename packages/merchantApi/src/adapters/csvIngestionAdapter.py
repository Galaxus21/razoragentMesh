"""CSV Ingestion Adapter for parsing batch product catalogs into Universal Product Listings."""

import csv
import io
import json
from typing import Any, Optional

from ..constants.merchantConstants import (
    defaultGstRatePercent,
    defaultHsnCode,
    defaultOriginPincode,
    maxCsvRowsPerBatch,
)
from ..schemas.bulkIngestSchema import (
    CsvIngestResult,
)
from ..schemas.universalProductSchema import (
    ApparelFacet,
    FmcgFacet,
    UniversalProductListing,
    VolumeTier,
)
from ..catalog.priceNormalizer import normalizeInrToPaise


def _extractVolumeTiers(tiersRaw: Optional[str]) -> list[VolumeTier]:
    """Parses volume tiers JSON array if provided."""
    if not tiersRaw or not str(tiersRaw).strip():
        return []
    try:
        parsed = json.loads(str(tiersRaw).strip())
        if not isinstance(parsed, list):
            return []
        return [VolumeTier(**tier) for tier in parsed]
    except Exception:
        return []


def _extractFacets(row: dict[str, Any]) -> tuple[Optional[ApparelFacet], Optional[FmcgFacet]]:
    """Extracts Apparel and FMCG domain facets from CSV dictionary."""
    allergens: list[str] = []
    rawAllergens = row.get("allergens")
    if rawAllergens:
        sep = ";" if ";" in str(rawAllergens) else ","
        allergens = [a.strip() for a in str(rawAllergens).split(sep) if a.strip()]

    apparel = None
    size = row.get("size")
    color = row.get("color")
    if size:
        apparel = ApparelFacet(
            size=str(size).strip(),
            color=str(color).strip() if color else None,
        )

    fmcg = None
    if allergens or row.get("isVeg") is not None:
        fmcg = FmcgFacet(allergens=allergens)

    return apparel, fmcg


def parseCsvRow(row: dict[str, Any], merchantDid: str) -> Optional[UniversalProductListing]:
    """Maps a single raw CSV row dictionary to a UniversalProductListing."""
    try:
        skuId = str(row.get("skuId") or row.get("sku") or "").strip()
        title = str(row.get("title") or row.get("name") or "").strip()
        if not skuId or not title:
            return None

        rawPrice = row.get("basePriceInr") or row.get("price") or row.get("baseUnitPriceInr")
        if rawPrice is not None:
            pricePaise = normalizeInrToPaise(str(rawPrice).strip())
        elif row.get("baseUnitPricePaise") is not None:
            pricePaise = int(row["baseUnitPricePaise"])
        else:
            return None

        rawStock = row.get("availableStock") or row.get("stock") or 0
        stock = int(float(str(rawStock).strip()))
        hsnCode = str(row.get("hsnCode") or defaultHsnCode).strip()
        gstRate = int(float(str(row.get("gstRatePercent") or row.get("gstRate") or defaultGstRatePercent)))
        originPincode = str(row.get("originPincode") or defaultOriginPincode).strip()
        category = str(row.get("category") or "general").strip()
        description = str(row.get("description") or title).strip()

        volumeTiers = _extractVolumeTiers(row.get("volumeTiersJson"))
        apparelFacet, fmcgFacet = _extractFacets(row)

        return UniversalProductListing(
            skuId=skuId,
            merchantDid=merchantDid,
            title=title,
            description=description,
            category=category,
            hsnCode=hsnCode,
            gstRatePercent=gstRate,
            baseUnitPricePaise=pricePaise,
            availableStock=stock,
            originPincode=originPincode,
            volumeTiers=volumeTiers,
            apparelFacet=apparelFacet,
            fmcgFacet=fmcgFacet,
        )
    except Exception:
        return None


def ingestCsvContent(
    csvContent: str,
    merchantDid: str,
) -> tuple[list[UniversalProductListing], CsvIngestResult]:
    """Parses raw CSV content string into listings and returns diagnostic result summary."""
    listings: list[UniversalProductListing] = []
    failedSkuIds: list[str] = []

    if not csvContent or not csvContent.strip():
        emptyResult = CsvIngestResult(
            totalRowsProcessed=0,
            successCount=0,
            failureCount=0,
            failedSkuIds=[],
        )
        return [], emptyResult

    reader = csv.DictReader(io.StringIO(csvContent.strip()))
    totalCount = 0

    for idx, row in enumerate(reader, start=1):
        if idx > maxCsvRowsPerBatch:
            break
        totalCount += 1
        listing = parseCsvRow(row, merchantDid)
        if listing is not None:
            listings.append(listing)
        else:
            sku = str(row.get("skuId") or row.get("sku") or f"row-{idx}")
            failedSkuIds.append(sku)

    result = CsvIngestResult(
        totalRowsProcessed=totalCount,
        successCount=len(listings),
        failureCount=len(failedSkuIds),
        failedSkuIds=failedSkuIds,
    )
    return listings, result


__all__ = [
    "ingestCsvContent",
    "normalizeInrToPaise",
    "parseCsvRow",
]
