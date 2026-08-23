"""Unit tests for Layer 0 Ingress Security Shield."""

import pytest
from razoragentMesh.packages.catalogSanitizer import (
    InvalidSkuIdentifierException,
    SanitizedSkuQuote,
    SchemaSanitizationFailureException,
    cleanAndTruncateText,
    sanitizeMerchantSkuQuote,
    stripAnsiEscapes,
    stripMarkdownAndHtml,
    stripZeroWidthCharacters,
)


def testStripZeroWidthCharacters() -> None:
    """Verifies removal of hidden Unicode zero-width and directional override code points."""
    maliciousText = "Safe\u200bText\u200cWith\u200dHidden\ufeffChars\u202eReversed"
    cleaned = stripZeroWidthCharacters(maliciousText)
    assert cleaned == "SafeTextWithHiddenCharsReversed"
    assert "\u200b" not in cleaned
    assert "\ufeff" not in cleaned


def testStripAnsiEscapes() -> None:
    """Verifies stripping of terminal color codes and escape sequences."""
    ansiText = "\x1b[31mRed Alert\x1b[0m Standard \x1b[1;32mBold Green\x1b[0m"
    cleaned = stripAnsiEscapes(ansiText)
    assert cleaned == "Red Alert Standard Bold Green"


def testStripMarkdownAndHtml() -> None:
    """Verifies flattening of markdown links and stripping of raw HTML tags."""
    markupText = "Check [Official Spec](https://example.com/exploit) <script>alert(1)</script>"
    cleaned = stripMarkdownAndHtml(markupText)
    assert cleaned == "Check Official Spec alert(1)"


def testCleanAndTruncateText() -> None:
    """Verifies whitespace normalization and length truncation."""
    rawLongText = "   " + "Word " * 50 + "   "
    truncated = cleanAndTruncateText(rawLongText, maxLength=30)
    assert len(truncated) <= 30
    assert not truncated.startswith(" ")
    assert not truncated.endswith(" ")


def testSanitizeMerchantSkuQuoteValid() -> None:
    """Verifies complete valid catalog quote parsing and schema construction."""
    rawPayload = {
        "sku_id": "SKU-TEST-001",
        "title": "Industrial \u200bBearing\u200c",
        "description": "High precision \x1b[32msteel\x1b[0m bearing for heavy machinery.",
        "available_stock": 200,
        "base_unit_price_paise": 150000,
        "offered_unit_price_paise": 142500,
        "hsn_code": "84821010",
        "gst_rate_percent": 18,
        "tax_breakdown": {
            "cgst_paise": 12825,
            "sgst_paise": 12825,
            "igst_paise": 0,
            "total_tax_paise": 25650,
        },
        "quote_expiry_timestamp": 1780000000,
        "quote_hash": "a" * 64,
    }
    quote = sanitizeMerchantSkuQuote(rawPayload)
    assert isinstance(quote, SanitizedSkuQuote)
    assert quote.skuId == "SKU-TEST-001"
    assert quote.title == "Industrial Bearing"
    assert "\u200b" not in quote.title
    assert "\x1b" not in quote.description
    assert quote.offeredUnitPricePaise == 142500
    assert quote.taxBreakdown.cgstPaise == 12825


def testSanitizeMerchantSkuQuoteRejectsFloat() -> None:
    """Verifies that floating point values in financial fields trigger sanitization error."""
    rawPayload = {
        "skuId": "SKU-TEST-002",
        "title": "Floating Point Test",
        "description": "Attempting floating point injection",
        "availableStock": 10,
        "baseUnitPricePaise": 100.50,  # Float prohibited
        "offeredUnitPricePaise": 95,
        "hsnCode": "84821010",
        "gstRatePercent": 18,
        "taxBreakdown": {"cgstPaise": 8, "sgstPaise": 8, "igstPaise": 0, "totalTaxPaise": 16},
        "quoteExpiryTimestamp": 1780000000,
        "quoteHash": "b" * 64,
    }
    with pytest.raises(SchemaSanitizationFailureException):
        sanitizeMerchantSkuQuote(rawPayload)


def testSanitizeMerchantSkuQuoteRejectsInvalidSkuId() -> None:
    """Verifies that invalid SKU ID formats are rejected."""
    rawPayload = {
        "skuId": "BAD_SKU_NO_PREFIX",
        "title": "Invalid SKU",
        "description": "Desc",
        "availableStock": 10,
        "baseUnitPricePaise": 1000,
        "offeredUnitPricePaise": 950,
        "hsnCode": "84821010",
        "gstRatePercent": 18,
        "taxBreakdown": {"cgstPaise": 85, "sgstPaise": 85, "igstPaise": 0, "totalTaxPaise": 170},
        "quoteExpiryTimestamp": 1780000000,
        "quoteHash": "c" * 64,
    }
    with pytest.raises(InvalidSkuIdentifierException):
        sanitizeMerchantSkuQuote(rawPayload)
