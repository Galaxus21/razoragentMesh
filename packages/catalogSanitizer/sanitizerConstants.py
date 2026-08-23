"""Constants for Layer 0 Ingress Security Shield."""

maxTitleLength: int = 80
minTitleLength: int = 1
maxDescriptionLength: int = 150
minDescriptionLength: int = 0
minSkuIdLength: int = 7
maxSkuIdLength: int = 36
quoteHashLength: int = 64

skuIdRegexPattern: str = r"^SKU-[A-Z0-9_-]{3,32}$"
hsnCodeRegexPattern: str = r"^[0-9]{4,8}$"
ansiEscapeRegexPattern: str = r"\x1b\[[0-9;]*[a-zA-Z]"
markdownLinkRegexPattern: str = r"\[([^\]]+)\]\([^\)]+\)"
markdownEmptyAltImageRegexPattern: str = r"!\s*\[\s*\]\s*\([^\)]*\)"
htmlTagRegexPattern: str = r"<[^>]+>"

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
