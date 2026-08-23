"""Harmonized System of Nomenclature (HSN) code directory and GST rate resolver."""

# Default and Specific GST Percentages
defaultGstRatePercent: int = 18
zeroRatedGstPercent: int = 0
jewelryGstRatePercent: int = 3
hsnPrefixLength: int = 4

# HSN 4-Digit Chapter Prefix to GST Rate Mapping
hsnCodeDirectory: dict[str, int] = {
    "7113": 3,   # Precious jewelry (gold, silver, platinum)
    "7114": 3,   # Articles of goldsmith
    "7118": 3,   # Coins
    "9403": 18,  # Furniture
    "9401": 18,  # Seats/chairs
    "1508": 5,   # Ground-nut oil
    "1511": 5,   # Palm oil
    "1516": 5,   # Animal/vegetable fats
    "3004": 12,  # Pharmaceuticals/medicaments
    "3002": 5,   # Vaccines and blood products
    "6109": 5,   # T-shirts, vests (MRP <= 1000)
    "6110": 12,  # Jerseys, pullovers
    "6203": 12,  # Men's suits
    "8471": 18,  # Computers, laptops
    "8517": 18,  # Phones, routers
    "0401": 0,   # Milk (fresh)
    "0402": 5,   # Milk (powder)
    "1901": 18,  # Food preparations (branded cereals)
    "2106": 18,  # Food preparations NES
    "3401": 18,  # Soaps, detergents
    "3808": 18,  # Insecticides, pesticides
    "4820": 12,  # Registers, notebooks
    "4901": 0,   # Books, printed materials
    "9503": 12,  # Toys
    "6402": 18,  # Footwear (rubber/plastic)
    "6403": 18,  # Footwear (leather)
}

# Alias for legacy compatibility
hsnGstRateDirectory: dict[str, int] = hsnCodeDirectory


def resolveGstRate(hsnCode: str) -> int:
    """Resolve applicable GST rate percent from HSN code using 4-digit chapter prefix."""
    if not hsnCode or len(hsnCode) < hsnPrefixLength:
        return defaultGstRatePercent
    hsnPrefix = str(hsnCode)[:hsnPrefixLength]
    return hsnCodeDirectory.get(hsnPrefix, defaultGstRatePercent)


__all__ = [
    "defaultGstRatePercent",
    "hsnCodeDirectory",
    "hsnGstRateDirectory",
    "hsnPrefixLength",
    "jewelryGstRatePercent",
    "resolveGstRate",
    "zeroRatedGstPercent",
]
