"""Facet-aware synthesizer turning a listing's domain facets into rich semantic text."""

from typing import Any, List, Optional

from ..schemas.universalProductSchema import UniversalProductListing


def synthesizeFacetDescription(listing: UniversalProductListing) -> str:
    """Synthesizes structured category facets and product metadata into rich semantic text."""
    segments: List[str] = []

    if listing.category:
        segments.append(listing.category.strip())

    brand = getattr(listing, "brand", None) or ""
    title = listing.title.strip() if listing.title else ""
    if brand and brand.lower() not in title.lower():
        segments.append(f"{brand} {title}")
    elif title:
        segments.append(title)

    segments.extend(_extractFacetedSegments(listing))

    facetsDict = getattr(listing, "facets", None)
    if isinstance(facetsDict, dict):
        for key, val in facetsDict.items():
            formatted = _formatFacetEntry(key, val)
            if formatted and formatted not in segments:
                segments.append(formatted)

    if listing.hsnCode:
        segments.append(f"HSN {listing.hsnCode}")

    return " | ".join(segments)


def _extractFacetedSegments(listing: UniversalProductListing) -> List[str]:
    """Extracts domain-specific facet fragments for jewelry, apparel, pharma, and FMCG."""
    return (
        _extractJewelrySegments(listing)
        + _extractApparelSegments(listing)
        + _extractPharmaSegments(listing)
        + _extractFmcgSegments(listing)
    )


def _extractJewelrySegments(listing: UniversalProductListing) -> List[str]:
    """Extracts gross weight and BIS hallmark description segments."""
    jf = getattr(listing, "jewelryFacet", None)
    if jf is None:
        return []
    hNum = str(jf.hallmarkNumber).strip() if jf.hallmarkNumber else ""
    hallmarkText = (hNum if hNum.startswith("BIS") else f"BIS Hallmark {hNum}") if hNum else None
    return [f"Gross {jf.grossWeightGrams}g"] + ([hallmarkText] if hallmarkText else [])


def _extractApparelSegments(listing: UniversalProductListing) -> List[str]:
    """Extracts size, color, fabric, fit, and gender apparel segments."""
    af = getattr(listing, "apparelFacet", None)
    if af is None:
        return []
    segments: List[str] = []
    if af.size:
        segments.append(f"Size {af.size}")
    if af.color:
        segments.append(af.color)
    if af.fabric:
        fab = ", ".join(af.fabric) if isinstance(af.fabric, list) else str(af.fabric)
        segments.append(f"Fabric: {fab}")
    if af.fitType:
        segments.append(f"{af.fitType} Fit")
    if af.gender:
        segments.append(f"{af.gender}")
    return segments


def _extractPharmaSegments(listing: UniversalProductListing) -> List[str]:
    """Extracts active salt and schedule pharma segments."""
    pf = getattr(listing, "pharmaFacet", None)
    if pf is None:
        return []
    segments = [f"Active: {pf.activeSalt}"]
    if pf.schedule:
        sched = pf.schedule.strip()
        segments.append(sched if sched.lower().startswith("schedule") else f"Schedule {sched}")
    return segments


def _extractFmcgSegments(listing: UniversalProductListing) -> List[str]:
    """Extracts allergens, veg indicator, and shelf life FMCG segments."""
    ff = getattr(listing, "fmcgFacet", None)
    if ff is None:
        return []
    segments: List[str] = []
    if ff.allergens:
        allg = ", ".join(ff.allergens) if isinstance(ff.allergens, list) else str(ff.allergens)
        segments.append(f"Allergens: {allg}")
    if ff.isVeg:
        segments.append("Veg")
    if ff.shelfLifeDays:
        segments.append(f"Shelf Life: {ff.shelfLifeDays} days")
    return segments


def _formatFacetEntry(key: str, value: Any) -> Optional[str]:
    """Formats an individual facet or attribute key-value pair into a normalized text fragment."""
    if isinstance(value, bool):
        return key if value else None
    if isinstance(value, (list, set, tuple)):
        return f"{key}: {', '.join(str(item) for item in value)}"
    strValue = str(value).strip()
    if not strValue:
        return None
    normalizedKey = key.lower()
    if normalizedKey in ("gross", "grossweight", "grossweightgrams"):
        return strValue if "gross" in strValue.lower() else f"Gross {strValue}"
    if normalizedKey == "size":
        return strValue if "size" in strValue.lower() else f"Size {strValue}"
    return strValue if (normalizedKey == "color" or normalizedKey in strValue.lower()) else f"{key}: {strValue}"


__all__ = [
    "synthesizeFacetDescription",
]
