import json
import os
from typing import Any, AsyncGenerator, Dict, List
import pytest
import pytest_asyncio

from razoragentMesh.tests.mockInfraHelpers import (
    MockQdrantClient,
    MockRazorpayRouteClient,
    MockRedisAsync,
)

# Top-level camelCase constants
fixturesDirectory = os.path.join(os.path.dirname(__file__), "fixtures")


@pytest.fixture(scope="session")
def agentKeyFixtures() -> Dict[str, Any]:
    filePath = os.path.join(fixturesDirectory, "agentKeyFixtures.json")
    with open(filePath, "r", encoding="utf-8") as fileHandle:
        return json.load(fileHandle)


@pytest.fixture(scope="session")
def catalogFixtures() -> List[Dict[str, Any]]:
    filePath = os.path.join(fixturesDirectory, "catalogFixtures.json")
    with open(filePath, "r", encoding="utf-8") as fileHandle:
        return json.load(fileHandle)


@pytest.fixture(scope="session")
def razorpayMockResponses() -> Dict[str, Any]:
    filePath = os.path.join(fixturesDirectory, "razorpayMockResponses.json")
    with open(filePath, "r", encoding="utf-8") as fileHandle:
        return json.load(fileHandle)


@pytest_asyncio.fixture
async def mockRedisClient(
    catalogFixtures: List[Dict[str, Any]],
) -> AsyncGenerator[MockRedisAsync, None]:
    client = MockRedisAsync()
    for item in catalogFixtures:
        stockKey = f"sku:{item['skuId']}:stock"
        await client.set(stockKey, item["availableStock"])
    yield client
    await client.flushdb()


@pytest.fixture
def mockQdrantClient(catalogFixtures: List[Dict[str, Any]]) -> MockQdrantClient:
    client = MockQdrantClient()
    client.createCollection("merchantCatalog")
    points = [
        {
            "id": item["skuId"],
            "vector": item["embeddingVector"],
            "payload": {
                "skuId": item["skuId"],
                "title": item["title"],
                "category": item["category"],
                "brand": item["brand"],
                "hsnCode": item["hsnCode"],
                "gstRatePercent": item["gstRatePercent"],
                "baseUnitPricePaise": item["baseUnitPricePaise"],
                "availableStock": item["availableStock"],
                "attributes": item["attributes"],
            },
        }
        for item in catalogFixtures
    ]
    client.upsert("merchantCatalog", points)
    return client


@pytest.fixture
def mockRazorpayRouteClient(
    razorpayMockResponses: Dict[str, Any],
) -> MockRazorpayRouteClient:
    return MockRazorpayRouteClient(razorpayMockResponses)
