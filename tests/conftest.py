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


@pytest.fixture(scope="session", autouse=True)
def allowClientServerTimeForDeterminism() -> Any:
    """Opens the documented `serverTime` test seam for the whole suite.

    Several settlement tests POST a fixed `serverTime` so that mandate expiry, the nonce drift
    window and the invoice date are deterministic rather than dependent on the wall clock. In a
    real deployment that override is refused unless it sits within the NTP drift window of the
    real clock -- an unbounded `serverTime` lets a caller settle an expired mandate and back-date
    a statutory invoice without breaking a signature.

    Enabling it here keeps those tests honest about what they are doing. The guard itself is
    tested with the flag explicitly off; see testServerTimeClockOverride.py.
    """
    previousValue = os.environ.get("ALLOW_CLIENT_SERVER_TIME")
    os.environ["ALLOW_CLIENT_SERVER_TIME"] = "true"
    yield
    if previousValue is None:
        os.environ.pop("ALLOW_CLIENT_SERVER_TIME", None)
    else:
        os.environ["ALLOW_CLIENT_SERVER_TIME"] = previousValue


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


# Imported rather than repeated: this fixture stands in for the collection the Merchant
# API actually writes, and a literal here let the healer's constant drift away from it
# undetected for the whole life of the package.
from razoragentMesh.packages.vectorHealer.src.constants.healerConstants import (
    qdrantCollectionName,
)


@pytest.fixture
def mockQdrantClient(catalogFixtures: List[Dict[str, Any]]) -> MockQdrantClient:
    client = MockQdrantClient()
    client.createCollection(qdrantCollectionName)
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
    client.upsert(qdrantCollectionName, points)
    return client


@pytest.fixture
def mockRazorpayRouteClient(
    razorpayMockResponses: Dict[str, Any],
) -> MockRazorpayRouteClient:
    return MockRazorpayRouteClient(razorpayMockResponses)
