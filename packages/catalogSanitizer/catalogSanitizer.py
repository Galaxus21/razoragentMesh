"""Ingress Security Shield: merchant catalog sanitizer and normalizer."""

import re
import unicodedata
from typing import Any
from pydantic import ValidationError

from .ingressShieldExceptions import (
    ArithmeticDriftException,
    InvalidSkuIdentifierException,
    SchemaSanitizationFailureException,
)
from .sanitizerConstants import (
    ansiEscapeRegexPattern,
    defaultCurrency,
    htmlTagRegexPattern,
    markdownEmptyAltImageRegexPattern,
    markdownLinkRegexPattern,
    maxDescriptionLength,
    maxTitleLength,
    skuIdRegexPattern,
    unicodeFormatCategory,
    unicodeNormalizationForm,
    unicodeTagBlockEnd,
    unicodeTagBlockStart,
    zeroWidthCodePoints,
)
from .sanitizedSkuQuoteSchema import (
    SanitizedSkuQuote,
    TaxBreakdownSchema,
)



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
            currency=defaultCurrency,
            hsnCode=hsn,
            gstRatePercent=nums["gstRate"],
            taxBreakdown=taxBreakdown,
            quoteExpiryTimestamp=nums["expiry"],
            quoteHash=qHash,
        )
    except ValidationError as err:
        raise SchemaSanitizationFailureException(f"Validation failed: {str(err)}") from err


def cleanAndTruncateText(rawText: str, maxLength: int) -> str:
    """Strips hidden characters, ANSI escapes and markup, then normalizes to NFC.

    NFC is not decoration in a catalog. Two SKU titles that render identically but differ in
    Unicode composition hash differently, sort differently, and embed to different vectors -- so
    "cafe" + U+0301 and "caf\u00e9" become two products. GUIDE.md has always claimed this module
    produced "strict UTF-8 NFC text"; until this line existed, it did not.

    Order matters. Normalization runs last so that it also composes any sequence left behind by
    the stripping passes.
    """
    if not rawText:
        return ""
    cleaned = stripZeroWidthCharacters(rawText)
    cleaned = stripAnsiEscapes(cleaned)
    cleaned = stripMarkdownAndHtml(cleaned)
    normalized = " ".join(cleaned.split())
    normalized = unicodedata.normalize(unicodeNormalizationForm, normalized)
    if len(normalized) <= maxLength:
        return normalized
    return normalized[:maxLength].rstrip()


def stripZeroWidthCharacters(inputString: str) -> str:
    """Removes invisible formatting characters, including the Unicode Tags block.

    Tested by category rather than against a list of code points. The previous eleven-point
    denylist (U+200B-200F, U+202A-202E, U+FEFF) covered the 2001-era invisibles and missed the
    ones an agent mesh actually faces:

      * U+E0000-E007F  Unicode Tags -- the canonical channel for smuggling instructions that are
                       invisible to a human reviewing the catalog and legible to a model reading
                       it. This is the one that matters here: the text this function guards is
                       what reaches an embedding model and an agent's context.
      * U+2066-2069    directional isolates, Unicode 6.3's replacements for the U+202A-202E
                       embeddings the old list did cover
      * U+2060         word joiner, zero-width, same class as the U+200B that was covered
      * U+00AD         soft hyphen, invisible until line-break
      * U+180E         Mongolian vowel separator, zero-width since Unicode 6.3

    Category `Cf` (format) covers every one of those except the tag block, which is `Cf` in
    recent Unicode but was not always, so it is named explicitly and the two are unioned. A
    denylist has to be extended each time Unicode adds to the class; this does not.

    Note what is deliberately NOT stripped: `Cc` (control) characters other than those handled by
    the ANSI pass, and ordinary whitespace, which the caller collapses.
    """
    if not inputString:
        return ""
    filteredChars = [
        char
        for char in inputString
        if not _isInvisibleFormattingCharacter(char)
    ]
    return "".join(filteredChars)


def _isInvisibleFormattingCharacter(char: str) -> bool:
    """True for Unicode format characters and anything in the Tags block."""
    codePoint = ord(char)
    if unicodeTagBlockStart <= codePoint <= unicodeTagBlockEnd:
        return True
    if codePoint in zeroWidthCodePoints:
        return True
    return unicodedata.category(char) == unicodeFormatCategory


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

    # `or 0` here would coerce every falsy value -- 0.0, False, "" -- to int 0 *before* the guard
    # ran, so the one check that exists to keep floats and booleans out of a financial payload
    # never saw them. Absent keys are handled explicitly instead, matching the shape totalTaxPaise
    # already used four lines below.
    cgstPaise = _validateStrictInteger(cgst if cgst is not None else 0, "cgstPaise")
    sgstPaise = _validateStrictInteger(sgst if sgst is not None else 0, "sgstPaise")
    igstPaise = _validateStrictInteger(igst if igst is not None else 0, "igstPaise")
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


__all__ = [
    "cleanAndTruncateText",
    "sanitizeMerchantSkuQuote",
    "stripAnsiEscapes",
    "stripMarkdownAndHtml",
    "stripZeroWidthCharacters",
]
