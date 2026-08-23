"""Ingress Security Shield: merchant catalog sanitizer and normalizer."""

import re
from typing import Any
from pydantic import ValidationError

from razoragentMesh.packages.catalogSanitizer.ingressShieldExceptions import (
    InvalidSkuIdentifierException,
    SchemaSanitizationFailureException,
)
from razoragentMesh.packages.catalogSanitizer.sanitizerConstants import (
    ansiEscapeRegexPattern,
    htmlTagRegexPattern,
    markdownEmptyAltImageRegexPattern,
    markdownLinkRegexPattern,
    maxDescriptionLength,
    maxTitleLength,
    skuIdRegexPattern,
    zeroWidthCodePoints,
)
from razoragentMesh.packages.catalogSanitizer.sanitizedSkuQuoteSchema import (
    SanitizedSkuQuote,
    TaxBreakdownSchema,
)
from razoragentMesh.packages.mandateEngine.settlement.settlementExceptions import (
    ArithmeticDriftException,
)


def stripZeroWidthCharacters(inputString: str) -> str:
    """Removes hidden zero-width and directional override Unicode code points."""
    if not inputString:
        return ""
    filteredChars = [
        char for char in inputString if ord(char) not in zeroWidthCodePoints
    ]
    return "".join(filteredChars)


def stripAnsiEscapes(inputString: str) -> str:
    """Removes ANSI terminal escape sequences."""
    if not inputString:
        return ""
    return re.sub(ansiEscapeRegexPattern, "", inputString)


def stripMarkdownAndHtml(inputString: str) -> str:
    """Strips HTML tags, empty-alt images, and flattens Markdown link syntax to anchor text."""
    if not inputString:
        return ""
    textWithoutEmptyImages = re.sub(markdownEmptyAltImageRegexPattern, "", inputString)
    textWithoutLinks = re.sub(markdownLinkRegexPattern, r"\1", textWithoutEmptyImages)
    return re.sub(htmlTagRegexPattern, "", textWithoutLinks)


def cleanAndTruncateText(rawText: str, maxLength: int) -> str:
    """Applies zero-width, ANSI, and markup stripping, then normalizes whitespace."""
    if not rawText:
        return ""
    cleaned = stripZeroWidthCharacters(rawText)
    cleaned = stripAnsiEscapes(cleaned)
    cleaned = stripMarkdownAndHtml(cleaned)
    normalized = " ".join(cleaned.split())
    if len(normalized) <= maxLength:
        return normalized
    return normalized[:maxLength].rstrip()


def _extractFieldValue(rawQuote: dict[str, Any], camelKey: str, snakeKey: str) -> Any:
    """Extracts field supporting both camelCase and snake_case representations."""
    if camelKey in rawQuote:
        return rawQuote[camelKey]
    if snakeKey in rawQuote:
        return rawQuote[snakeKey]
    return None


def _validateStrictInteger(value: Any, fieldName: str) -> int:
    """Ensures numerical field is strictly an integer and not a float or boolean."""
    if isinstance(value, bool) or not isinstance(value, int):
        raise SchemaSanitizationFailureException(
            f"Field {fieldName} must be an integer, got {type(value).__name__}"
        )
    return value


def _buildTaxBreakdown(rawTax: Any) -> TaxBreakdownSchema:
    """Coerces raw tax breakdown into frozen TaxBreakdownSchema."""
    if not isinstance(rawTax, dict):
        raise SchemaSanitizationFailureException("taxBreakdown must be a dictionary")

    cgst = _extractFieldValue(rawTax, "cgstPaise", "cgst_paise")
    sgst = _extractFieldValue(rawTax, "sgstPaise", "sgst_paise")
    igst = _extractFieldValue(rawTax, "igstPaise", "igst_paise")
    total = _extractFieldValue(rawTax, "totalTaxPaise", "total_tax_paise")

    cgstPaise = _validateStrictInteger(cgst or 0, "cgstPaise")
    sgstPaise = _validateStrictInteger(sgst or 0, "sgstPaise")
    igstPaise = _validateStrictInteger(igst or 0, "igstPaise")
    computedTotalTaxPaise = cgstPaise + sgstPaise + igstPaise
    totalTaxPaise = _validateStrictInteger(
        total if total is not None else computedTotalTaxPaise,
        "totalTaxPaise",
    )

    if totalTaxPaise != computedTotalTaxPaise:
        raise ArithmeticDriftException(
            f"Tax breakdown arithmetic drift: totalTaxPaise ({totalTaxPaise}) != "
            f"cgstPaise ({cgstPaise}) + sgstPaise ({sgstPaise}) + igstPaise ({igstPaise})"
        )

    return TaxBreakdownSchema(
        cgstPaise=cgstPaise,
        sgstPaise=sgstPaise,
        igstPaise=igstPaise,
        totalTaxPaise=totalTaxPaise,
    )


def _extractNumericFields(rawQuote: dict[str, Any]) -> dict[str, int]:
    """Extracts and validates all monetary and integer metrics."""
    return {
        "stock": _validateStrictInteger(_extractFieldValue(rawQuote, "availableStock", "available_stock"), "availableStock"),
        "basePrice": _validateStrictInteger(_extractFieldValue(rawQuote, "baseUnitPricePaise", "base_unit_price_paise"), "baseUnitPricePaise"),
        "offeredPrice": _validateStrictInteger(_extractFieldValue(rawQuote, "offeredUnitPricePaise", "offered_unit_price_paise"), "offeredUnitPricePaise"),
        "gstRate": _validateStrictInteger(_extractFieldValue(rawQuote, "gstRatePercent", "gst_rate_percent"), "gstRatePercent"),
        "expiry": _validateStrictInteger(_extractFieldValue(rawQuote, "quoteExpiryTimestamp", "quote_expiry_timestamp"), "quoteExpiryTimestamp"),
    }


def sanitizeMerchantSkuQuote(rawQuote: dict[str, Any]) -> SanitizedSkuQuote:
    """Sanitizes raw merchant catalog payload into strict SanitizedSkuQuote."""
    if not isinstance(rawQuote, dict):
        raise SchemaSanitizationFailureException("rawQuote must be a dictionary")

    skuId = _extractFieldValue(rawQuote, "skuId", "sku_id")
    if not isinstance(skuId, str) or not re.match(skuIdRegexPattern, skuId):
        raise InvalidSkuIdentifierException(f"Invalid SKU ID format: {skuId}")

    rawTitle = _extractFieldValue(rawQuote, "title", "title") or skuId
    rawDesc = _extractFieldValue(rawQuote, "description", "description") or ""
    nums = _extractNumericFields(rawQuote)

    hsn = str(_extractFieldValue(rawQuote, "hsnCode", "hsn_code") or "")
    qHash = str(_extractFieldValue(rawQuote, "quoteHash", "quote_hash") or "")
    taxBreakdown = _buildTaxBreakdown(_extractFieldValue(rawQuote, "taxBreakdown", "tax_breakdown"))

    try:
        return SanitizedSkuQuote(
            skuId=skuId,
            title=cleanAndTruncateText(str(rawTitle), maxTitleLength),
            description=cleanAndTruncateText(str(rawDesc), maxDescriptionLength),
            availableStock=nums["stock"],
            baseUnitPricePaise=nums["basePrice"],
            offeredUnitPricePaise=nums["offeredPrice"],
            currency="INR",
            hsnCode=hsn,
            gstRatePercent=nums["gstRate"],
            taxBreakdown=taxBreakdown,
            quoteExpiryTimestamp=nums["expiry"],
            quoteHash=qHash,
        )
    except ValidationError as err:
        raise SchemaSanitizationFailureException(f"Validation failed: {str(err)}") from err
