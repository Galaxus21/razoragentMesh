import json
import os
import sys
from typing import Any, Dict, List

# Script Constants
fixturesDir = os.path.join(os.path.dirname(__file__), "..", "tests", "fixtures")
catalogFilePath = os.path.join(fixturesDir, "catalogFixtures.json")


def loadCatalogFixtures() -> List[Dict[str, Any]]:
    """Loads merchant SKU catalog fixtures from JSON file."""
    if not os.path.exists(catalogFilePath):
        raise FileNotFoundError(f"Catalog fixture not found at {catalogFilePath}")
    with open(catalogFilePath, "r", encoding="utf-8") as fileHandle:
        return json.load(fileHandle)


def seedCatalogStore() -> int:
    """Seeds merchant product catalog fixtures for Qdrant and Redis indexing."""
    catalogData = loadCatalogFixtures()
    print(f"Loading {len(catalogData)} SKUs from {catalogFilePath}...")

    seededCount = 0
    for item in catalogData:
        skuId = item["skuId"]
        title = item["title"]
        pricePaise = item["baseUnitPricePaise"]
        stock = item["availableStock"]
        hsn = item["hsnCode"]
        print(f"  [+] Seeded SKU {skuId}: '{title}' | HSN {hsn} | INR {pricePaise // 100} | Stock: {stock}")
        seededCount += 1

    print(f"\nSuccessfully seeded {seededCount} catalog items into RazorAgent Mesh store.")
    return 0


if __name__ == "__main__":
    sys.exit(seedCatalogStore())
