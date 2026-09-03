"""Layer 0 Ingress Security Shield module.

Called from the merchant ingestion paths -- `parseCsvRow`, `mapShopifyVariantToSku` and the
Merchant Studio's `createSku` -- so that merchant-supplied title and description text is scrubbed
before it reaches the catalog, an embedding model, or an agent's context.

Removed from this surface, and why:

  * `MaliciousPayloadDetectedException` promised "active exploit patterns or forbidden characters
    are found". This module strips and validates; it has no detector, and the exception was never
    raised. A reader auditing Layer 0 counted a capability that did not exist.
  * `minSkuIdLength`, `maxSkuIdLength`, `minDescriptionLength` had no readers anywhere. SKU id
    length is governed entirely by `skuIdRegexPattern`.
"""

from .catalogSanitizer import (
    cleanAndTruncateText,
    sanitizeMerchantSkuQuote,
    stripAnsiEscapes,
    stripMarkdownAndHtml,
    stripZeroWidthCharacters,
)
from .ingressShieldExceptions import (
    ArithmeticDriftException,
    IngressSecurityException,
    InvalidSkuIdentifierException,
    SchemaSanitizationFailureException,
)
from .sanitizedSkuQuoteSchema import (
    SanitizedSkuQuote,
    TaxBreakdownSchema,
)
from .sanitizerConstants import (
    ansiEscapeRegexPattern,
    defaultCurrency,
    hsnCodeRegexPattern,
    htmlTagRegexPattern,
    markdownLinkRegexPattern,
    maxAllowedGstRate,
    maxDescriptionLength,
    maxTitleLength,
    minAllowedGstRate,
    minTitleLength,
    quoteHashLength,
    skuIdRegexPattern,
    unicodeFormatCategory,
    unicodeNormalizationForm,
    unicodeTagBlockEnd,
    unicodeTagBlockStart,
    zeroWidthCodePoints,
)

__all__ = [
    "ArithmeticDriftException",
    "IngressSecurityException",
    "InvalidSkuIdentifierException",
    "SchemaSanitizationFailureException",
    "SanitizedSkuQuote",
    "TaxBreakdownSchema",
    "cleanAndTruncateText",
    "sanitizeMerchantSkuQuote",
    "stripAnsiEscapes",
    "stripMarkdownAndHtml",
    "stripZeroWidthCharacters",
    "ansiEscapeRegexPattern",
    "defaultCurrency",
    "hsnCodeRegexPattern",
    "htmlTagRegexPattern",
    "markdownLinkRegexPattern",
    "maxAllowedGstRate",
    "maxDescriptionLength",
    "maxTitleLength",
    "minAllowedGstRate",
    "minTitleLength",
    "quoteHashLength",
    "skuIdRegexPattern",
    "unicodeFormatCategory",
    "unicodeNormalizationForm",
    "unicodeTagBlockEnd",
    "unicodeTagBlockStart",
    "zeroWidthCodePoints",
]
