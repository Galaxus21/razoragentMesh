"""CSV Ingestion Adapter for parsing batch product catalogs into Universal Product Listings."""

import csv
from decimal import Decimal
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
    JewelryFacet,
    PharmaFacet,
    ScheduledPromotionSchema,
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


def _extractPromotions(promotionsRaw: Optional[str]) -> list[ScheduledPromotionSchema]:
    """Parses promotions JSON array with key normalization and schema validation."""
    if not promotionsRaw or not str(promotionsRaw).strip():
        return []
    rawStr = str(promotionsRaw).strip()
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
    promotions: list[ScheduledPromotionSchema] = []
    for item in parsed:
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

        promo = ScheduledPromotionSchema(
            campaignId=campaignId,
            name=name,
            startsAtUnix=startsAt,
            endsAtUnix=endsAt,
            discountBps=discountBps,
            discountPaise=discountPaise,
            fixedPricePaise=fixedPrice,
            limitedStockAllocated=limitedStock,
        )
        promotions.append(promo)
    return promotions


def _extractFacets(
    row: dict[str, Any],
) -> tuple[
    Optional[ApparelFacet],
    Optional[FmcgFacet],
    Optional[JewelryFacet],
    Optional[PharmaFacet],
]:
    """Extracts Apparel, FMCG, Jewelry, and Pharma domain facets from CSV dictionary."""
    allergens: list[str] = []
    rawAllergens = row.get("allergens")
    if rawAllergens:
        sep = ";" if ";" in str(rawAllergens) else ","
        allergens = [a.strip() for a in str(rawAllergens).split(sep) if a.strip()]

    apparel = None
    size = row.get("size")
    color = row.get("color")
    fabricRaw = row.get("fabric") or row.get("material")
    fabric = [f.strip() for f in str(fabricRaw).split(",") if f.strip()] if fabricRaw else []
    if size or color or fabric:
        apparel = ApparelFacet(
            size=str(size).strip() if size else None,
            color=str(color).strip() if color else None,
            fabric=fabric,
        )

    fmcg = None
    if allergens or row.get("isVeg") is not None or row.get("fssaiNumber"):
        fmcg = FmcgFacet(
            allergens=allergens,
            isVeg=str(row.get("isVeg", "true")).lower() in ("true", "1", "yes"),
            fssaiNumber=str(row["fssaiNumber"]).strip() if row.get("fssaiNumber") else None,
        )

    jewelry = None
    caratRaw = row.get("purityCarat") or row.get("carat")
    weightRaw = row.get("grossWeightGrams") or row.get("weightGrams")
    if caratRaw and weightRaw:
        try:
            caratVal = int(float(str(caratRaw).strip()))
            if caratVal in (18, 22, 24):
                jewelry = JewelryFacet(
                    purityCarat=caratVal,  # type: ignore[arg-type]
                    grossWeightGrams=Decimal(str(weightRaw).strip()),
                    hallmarkNumber=str(row["hallmarkNumber"]).strip() if row.get("hallmarkNumber") else None,
                )
        except Exception:
            pass

    pharma = None
    activeSalt = row.get("activeSalt") or row.get("salt")
    if activeSalt:
        try:
            dosage = int(float(str(row.get("dosageMg") or 0).strip()))
            rxReq = str(row.get("prescriptionRequired", "false")).lower() in ("true", "1", "yes")
            pharma = PharmaFacet(
                activeSalt=str(activeSalt).strip(),
                dosageMg=dosage,
                schedule=str(row["schedule"]).strip() if row.get("schedule") else None,
                prescriptionRequired=rxReq,
            )
        except Exception:
            pass

    return apparel, fmcg, jewelry, pharma


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
        promotions = _extractPromotions(row.get("promotionsJson") or row.get("promotions"))
        apparelFacet, fmcgFacet, jewelryFacet, pharmaFacet = _extractFacets(row)

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
            promotions=promotions,
            apparelFacet=apparelFacet,
            fmcgFacet=fmcgFacet,
            jewelryFacet=jewelryFacet,
            pharmaFacet=pharmaFacet,
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
