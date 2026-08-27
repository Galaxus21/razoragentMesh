"""CSV Ingestion Adapter for parsing batch product catalogs into Universal Product Listings."""

import csv
from decimal import Decimal
import io
import json
import logging
from typing import Any, Optional

from ..constants.merchantConstants import (
    defaultGstRatePercent, defaultHsnCode, defaultOriginPincode,
    defaultVerticalGeneral, maxCsvRowsPerBatch,
)
from ..schemas.bulkIngestSchema import CsvIngestResult
from ..schemas.universalProductSchema import (
    ApparelFacet, FmcgFacet, JewelryFacet, PharmaFacet,
    ScheduledPromotionSchema, UniversalProductListing, VolumeTier,
)
from ..catalog.priceNormalizer import normalizeInrToPaise

logger = logging.getLogger(__name__)


def ingestCsvContent(
    csvContent: str, merchantDid: str,
) -> tuple[list[UniversalProductListing], CsvIngestResult]:
    """Parses raw CSV content string into listings and returns diagnostic result summary."""
    listings: list[UniversalProductListing] = []
    failedSkuIds: list[str] = []
    if not csvContent or not csvContent.strip():
        return [], CsvIngestResult(totalRowsProcessed=0, successCount=0, failureCount=0, failedSkuIds=[])

    reader = csv.DictReader(io.StringIO(csvContent.strip()))
    totalCount = 0
    for idx, row in enumerate(reader, start=1):
        if idx > maxCsvRowsPerBatch:
            break
        totalCount += 1
        listing = parseCsvRow(row, merchantDid, rowIdx=idx)
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


def parseCsvRow(
    row: dict[str, Any], merchantDid: str, rowIdx: int = 0
) -> Optional[UniversalProductListing]:
    """Maps a single raw CSV row dictionary to a UniversalProductListing."""
    try:
        skuId = str(row.get("skuId") or row.get("sku") or "").strip()
        title = str(row.get("title") or row.get("name") or "").strip()
        pricePaise = _extractRowPricePaise(row)
        if not skuId or not title or pricePaise is None:
            return None

        meta = _extractRowMetadata(row, title)
        tiers = _extractVolumeTiers(row.get("volumeTiersJson"), merchantDid, rowIdx)
        promos = _extractPromotions(row.get("promotionsJson") or row.get("promotions"))
        apFacet, fmFacet, jwFacet, phFacet = _extractFacets(row, merchantDid, rowIdx)

        return UniversalProductListing(
            skuId=skuId, merchantDid=merchantDid, title=title,
            description=meta["description"], category=meta["category"],
            hsnCode=meta["hsnCode"], gstRatePercent=meta["gstRate"],
            baseUnitPricePaise=pricePaise, availableStock=meta["stock"],
            originPincode=meta["originPincode"], volumeTiers=tiers,
            promotions=promos, apparelFacet=apFacet, fmcgFacet=fmFacet,
            jewelryFacet=jwFacet, pharmaFacet=phFacet,
        )
    except Exception as err:
        logger.warning(
            "CSV row parsing failed for merchant %s at line %d: %s",
            merchantDid, rowIdx, err, exc_info=True,
        )
        return None


def _extractRowPricePaise(row: dict[str, Any]) -> Optional[int]:
    """Extracts unit price in integer paise from raw CSV row."""
    rawPrice = row.get("basePriceInr") or row.get("price") or row.get("baseUnitPriceInr")
    if rawPrice is not None:
        return normalizeInrToPaise(str(rawPrice).strip())
    if row.get("baseUnitPricePaise") is not None:
        return int(row["baseUnitPricePaise"])
    return None


def _extractRowMetadata(row: dict[str, Any], title: str) -> dict[str, Any]:
    """Extracts stock, tax, location, category, and description metadata from CSV row."""
    rawStock = row.get("availableStock") or row.get("stock") or 0
    stock = int(float(str(rawStock).strip()))
    hsnCode = str(row.get("hsnCode") or defaultHsnCode).strip()
    gstRate = int(float(str(row.get("gstRatePercent") or row.get("gstRate") or defaultGstRatePercent)))
    originPincode = str(row.get("originPincode") or defaultOriginPincode).strip()
    category = str(row.get("category") or defaultVerticalGeneral).strip()
    description = str(row.get("description") or title).strip()
    return {
        "stock": stock,
        "hsnCode": hsnCode,
        "gstRate": gstRate,
        "originPincode": originPincode,
        "category": category,
        "description": description,
    }


def _extractVolumeTiers(
    tiersRaw: Optional[str], merchantDid: str = "", rowIdx: int = 0
) -> list[VolumeTier]:
    """Parses volume tiers JSON array if provided."""
    if not tiersRaw or not str(tiersRaw).strip():
        return []
    try:
        parsed = json.loads(str(tiersRaw).strip())
        if not isinstance(parsed, list):
            return []
        return [VolumeTier(**tier) for tier in parsed]
    except Exception as err:
        logger.warning(
            "CSV row parsing failed for merchant %s at line %d: %s",
            merchantDid,
            rowIdx,
            err,
            exc_info=True,
        )
        return []


def _extractPromotions(promotionsRaw: Optional[str]) -> list[ScheduledPromotionSchema]:
    """Parses promotions JSON array with key normalization and schema validation."""
    if not promotionsRaw or not str(promotionsRaw).strip():
        return []
    rawList = _parsePromotionsJsonString(str(promotionsRaw))
    return [_parsePromotionItem(item) for item in rawList]


def _parsePromotionsJsonString(promotionsRaw: str) -> list[Any]:
    """Parses raw promotions JSON string with escaped-quotes recovery."""
    rawStr = promotionsRaw.strip()
    try:
        parsed = json.loads(rawStr)
    except Exception:
        if '\\"' in rawStr:
            try:
                parsed = json.loads(rawStr.replace('\\"', '"'))
            except Exception as err:
                raise ValueError(f"Malformed promotions JSON: {rawStr}") from err
        else:
            raise ValueError(f"Malformed promotions JSON: {rawStr}")
    if not isinstance(parsed, list):
        raise ValueError("Promotions JSON must be a list of promotion objects")
    return parsed


def _parsePromotionItem(item: Any) -> ScheduledPromotionSchema:
    """Validates and coerces a single promotion dictionary into ScheduledPromotionSchema."""
    if not isinstance(item, dict):
        raise ValueError("Promotion array entry must be an object")
    campaignId = str(item.get("campaignId") or item.get("campaign_id") or "PROMO_CAMPAIGN").strip()
    name = str(item.get("name") or item.get("campaign_name") or campaignId).strip()
    startsAt = int(item["startsAtUnix"]) if "startsAtUnix" in item and item["startsAtUnix"] is not None else int(item.get("starts_at_unix", 0))
    endsAt = int(item["endsAtUnix"]) if "endsAtUnix" in item and item["endsAtUnix"] is not None else int(item.get("ends_at_unix", 0))
    discountBps = int(item["discountBps"]) if "discountBps" in item and item["discountBps"] is not None else (int(item["discount_bps"]) if "discount_bps" in item and item["discount_bps"] is not None else None)
    discountPaise = int(item["discountPaise"]) if "discountPaise" in item and item["discountPaise"] is not None else (int(item["discount_paise"]) if "discount_paise" in item and item["discount_paise"] is not None else None)
    fixedPrice = int(item["fixedPricePaise"]) if "fixedPricePaise" in item and item["fixedPricePaise"] is not None else (int(item["fixed_price_paise"]) if "fixed_price_paise" in item and item["fixed_price_paise"] is not None else None)
    limitedStock = int(item["limitedStockAllocated"]) if "limitedStockAllocated" in item and item["limitedStockAllocated"] is not None else (int(item["limited_stock_allocated"]) if "limited_stock_allocated" in item and item["limited_stock_allocated"] is not None else None)

    return ScheduledPromotionSchema(
        campaignId=campaignId,
        name=name,
        startsAtUnix=startsAt,
        endsAtUnix=endsAt,
        discountBps=discountBps,
        discountPaise=discountPaise,
        fixedPricePaise=fixedPrice,
        limitedStockAllocated=limitedStock,
    )


def _extractFacets(
    row: dict[str, Any], merchantDid: str = "", rowIdx: int = 0
) -> tuple[
    Optional[ApparelFacet],
    Optional[FmcgFacet],
    Optional[JewelryFacet],
    Optional[PharmaFacet],
]:
    """Extracts Apparel, FMCG, Jewelry, and Pharma domain facets from CSV dictionary."""
    return (
        _extractApparelFacet(row),
        _extractFmcgFacet(row),
        _extractJewelryFacet(row, merchantDid, rowIdx),
        _extractPharmaFacet(row, merchantDid, rowIdx),
    )


def _extractApparelFacet(row: dict[str, Any]) -> Optional[ApparelFacet]:
    """Extracts Apparel domain facet from CSV row."""
    size = row.get("size")
    color = row.get("color")
    fabricRaw = row.get("fabric") or row.get("material")
    fabric = [f.strip() for f in str(fabricRaw).split(",") if f.strip()] if fabricRaw else []
    if not (size or color or fabric):
        return None
    return ApparelFacet(
        size=str(size).strip() if size else None,
        color=str(color).strip() if color else None,
        fabric=fabric,
    )


def _extractFmcgFacet(row: dict[str, Any]) -> Optional[FmcgFacet]:
    """Extracts FMCG domain facet from CSV row."""
    allergens: list[str] = []
    rawAllergens = row.get("allergens")
    if rawAllergens:
        sep = ";" if ";" in str(rawAllergens) else ","
        allergens = [a.strip() for a in str(rawAllergens).split(sep) if a.strip()]

    if not (allergens or row.get("isVeg") is not None or row.get("fssaiNumber")):
        return None

    return FmcgFacet(
        allergens=allergens,
        isVeg=str(row.get("isVeg", "true")).lower() in ("true", "1", "yes"),
        fssaiNumber=str(row["fssaiNumber"]).strip() if row.get("fssaiNumber") else None,
    )


def _extractJewelryFacet(
    row: dict[str, Any], merchantDid: str = "", rowIdx: int = 0
) -> Optional[JewelryFacet]:
    """Extracts Jewelry domain facet from CSV row."""
    caratRaw = row.get("purityCarat") or row.get("carat")
    weightRaw = row.get("grossWeightGrams") or row.get("weightGrams")
    if not (caratRaw and weightRaw):
        return None
    try:
        caratVal = int(float(str(caratRaw).strip()))
        if caratVal in (18, 22, 24):
            return JewelryFacet(
                purityCarat=caratVal,  # type: ignore[arg-type]
                grossWeightGrams=Decimal(str(weightRaw).strip()),
                hallmarkNumber=str(row["hallmarkNumber"]).strip() if row.get("hallmarkNumber") else None,
            )
    except Exception as err:
        logger.warning(
            "CSV row parsing failed for merchant %s at line %d: %s",
            merchantDid,
            rowIdx,
            err,
            exc_info=True,
        )
    return None


def _extractPharmaFacet(
    row: dict[str, Any], merchantDid: str = "", rowIdx: int = 0
) -> Optional[PharmaFacet]:
    """Extracts Pharma domain facet from CSV row."""
    activeSalt = row.get("activeSalt") or row.get("salt")
    if not activeSalt:
        return None
    try:
        dosage = int(float(str(row.get("dosageMg") or 0).strip()))
        rxReq = str(row.get("prescriptionRequired", "false")).lower() in ("true", "1", "yes")
        return PharmaFacet(
            activeSalt=str(activeSalt).strip(),
            dosageMg=dosage,
            schedule=str(row["schedule"]).strip() if row.get("schedule") else None,
            prescriptionRequired=rxReq,
        )
    except Exception as err:
        logger.warning(
            "CSV row parsing failed for merchant %s at line %d: %s",
            merchantDid,
            rowIdx,
            err,
            exc_info=True,
        )
    return None


__all__ = [
    "ingestCsvContent",
    "normalizeInrToPaise",
    "parseCsvRow",
]
