"""Constants for Layer 0 Ingress Security Shield."""

maxTitleLength: int = 80
minTitleLength: int = 1
maxDescriptionLength: int = 150
# minSkuIdLength / maxSkuIdLength / minDescriptionLength were removed: nothing read them.
# SKU id length is governed entirely by skuIdRegexPattern below, whose {3,32} bound implies
# 7..36 with the prefix, without reference to any constant.
quoteHashLength: int = 64

skuIdRegexPattern: str = r"^SKU-[A-Z0-9_-]{3,32}$"
hsnCodeRegexPattern: str = r"^[0-9]{4,8}$"
ansiEscapeRegexPattern: str = r"\x1b\[[0-9;]*[a-zA-Z]"
markdownLinkRegexPattern: str = r"\[([^\]]+)\]\([^\)]+\)"
markdownEmptyAltImageRegexPattern: str = r"!\s*\[\s*\]\s*\([^\)]*\)"
# Requires a plausible tag name rather than any run of non-">" characters. The old pattern,
# r"<[^>]+>", matched from the first "<" to the next ">" anywhere in the string, so a
# description reading "fits screens < 15in and > 10in" came out as "fits screens 10in" --
# silent data loss with no exception. This is not an HTML sanitizer and must not be
# described as one; it strips tags without eating prose.
htmlTagRegexPattern: str = r"</?[A-Za-z][^>]*>"

zeroWidthCodePoints: frozenset[int] = frozenset({
    0x200B,
    0x200C,
    0x200D,
    0xFEFF,
    0x200E,
    0x200F,
    0x202A,
    0x202B,
    0x202C,
    0x202D,
    0x202E,
})

defaultCurrency: str = "INR"
maxAllowedGstRate: int = 28
minAllowedGstRate: int = 0


# Unicode Tags block (U+E0000-U+E007F). Every code point here renders as nothing and survives a
# copy-paste, which is what makes it the standard way to hide instructions inside a product title
# where a human reviewer sees clean text and a model sees a directive.
unicodeTagBlockStart: int = 0xE0000
unicodeTagBlockEnd: int = 0xE007F

# Unicode general category for format characters: the class that covers zero-width joiners,
# directional isolates, the word joiner and the soft hyphen in one test.
unicodeFormatCategory: str = "Cf"

# NFC, per GUIDE.md's claim that catalog text is normalized. Composed form is the right choice
# for a catalog: it is what a keyboard produces and what most comparisons assume.
unicodeNormalizationForm: str = "NFC"
