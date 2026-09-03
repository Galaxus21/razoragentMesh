import asyncio
import json
import os
import sys
import time
from typing import Any, Dict, List, Optional

# Constants
defaultRedisUrl = "redis://localhost:6379/0"

# docker-compose gates mcp-server and merchant-api on this script's exit code.
exitCodeSeedingSucceeded = 0
exitCodeSeedingFailed = 1
# Sentinel distinguishing 'Qdrant seeded nothing' from 'Qdrant could not be reached'.
qdrantSeedingFailed = -1
defaultQdrantHost = "localhost"
defaultQdrantPort = 6333
defaultCollectionName = "razoragent_catalog"
fixturesDir = os.path.join(os.path.dirname(__file__), "..", "tests", "fixtures")
catalogFilePath = os.path.join(fixturesDir, "catalogFixtures.json")

# The merchant these seeded SKUs are published as. The fixture JSON carries no merchantDid of its
# own, and mcpServer/src/catalog/fixtureIndexer.ts publishes the compiled office fixtures under
# this same DID -- so the whole demo catalog has one owner and one negotiation policy governs it.
#
# This is load-bearing, not cosmetic. The x402 gateway resolves a SKU's owning merchant from its
# listing and refuses to negotiate for a SKU that names none, so without this every seeded SKU
# would be permanently non-negotiable no matter what policy the merchant saved.
seedMerchantDid = "did:mesh:merchant_razoragent_demo_01"


def _buildDemoNegotiationPolicy() -> Dict[str, Any]:
    """The demo merchant's opt-in, seeded as data rather than defaulted in code.

    Negotiation is off for every merchant until a policy says otherwise, so without this a fresh
    `docker compose up` would answer DECLINED to every bid and the negotiation feature would look
    broken rather than declined. Seeding it here keeps the gateway's default honest -- it is still
    opt-in, this merchant has simply opted in -- and the Studio's Negotiation Policy panel can
    switch it back off live, which is the more interesting thing to show.

    The 12% margin floor means the demo merchant will go down to 88% of list and no further.
    """
    now = int(time.time())
    return {
        "merchantDid": seedMerchantDid,
        "negotiationEnabled": True,
        "marginFloorBps": 1200,
        "minimumOrderQuantity": 1,
        "autoAcceptSpreadPaise": 0,
        "maxNegotiationTurns": 5,
        "createdAtTimestamp": now,
        "updatedAtTimestamp": now,
    }


def loadCatalogFixtures() -> List[Dict[str, Any]]:
    """Loads merchant SKU catalog fixtures from JSON file."""
    if not os.path.exists(catalogFilePath):
        raise FileNotFoundError(f"Catalog fixture not found at {catalogFilePath}")
    with open(catalogFilePath, "r", encoding="utf-8") as fileHandle:
        return json.load(fileHandle)


async def seedRedisStore(catalogData: List[Dict[str, Any]], redisUrl: str) -> int:
    """Seeds SKU inventory stock and metadata into Redis key-value store."""
    try:
        import redis.asyncio as redisClient
        redisConnection = redisClient.from_url(redisUrl, decode_responses=True)
        await redisConnection.ping()
        print(f"Connected to Redis at {redisUrl}")

        pipe = redisConnection.pipeline()
        for item in catalogData:
            skuId = item["skuId"]
            stock = item.get("availableStock", 100)
            record = {"merchantDid": seedMerchantDid, **item}
            pipe.set(f"inventory:stock:{skuId}", str(stock))
            pipe.set(f"mesh:catalog:{skuId}", json.dumps(record))
        pipe.set(
            f"mesh:merchant:policy:{seedMerchantDid}",
            json.dumps(_buildDemoNegotiationPolicy()),
        )
        await pipe.execute()
        await redisConnection.aclose()
        print(f"Successfully seeded {len(catalogData)} SKUs and 1 negotiation policy into Redis store.")
        return len(catalogData)
    except Exception as redisError:
        # Not "skipped": failed. docker-compose gates mcp-server and merchant-api on this
        # container completing successfully, so swallowing this brings the whole mesh up
        # "healthy" against an unseeded store. The caller decides whether that is fatal.
        print(f"Redis seeding FAILED ({redisError}).")
        raise


def _buildQdrantPoints(catalogData: List[Dict[str, Any]], pointStructCls: Any) -> List[Any]:
    points = []
    for index, item in enumerate(catalogData):
        vector = item.get("embeddingVector")
        if vector and len(vector) == 384:
            points.append(
                pointStructCls(
                    id=index + 1,
                    vector=vector,
                    payload={
                        "skuId": item["skuId"],
                        "title": item["title"],
                        "brand": item.get("brand", "Generic"),
                        "category": item.get("category", "General"),
                        "baseUnitPricePaise": item.get("baseUnitPricePaise", 0),
                        "availableStock": item.get("availableStock", 100),
                        "hsnCode": item.get("hsnCode", "99"),
                    },
                )
            )
    return points


def seedQdrantCollection(catalogData: List[Dict[str, Any]], qdrantHost: str, qdrantPort: int) -> int:
    """Seeds vector embeddings and payloads into Qdrant collection if reachable."""
    try:
        from qdrant_client import QdrantClient
        from qdrant_client.models import PointStruct, VectorParams, Distance

        client = QdrantClient(host=qdrantHost, port=qdrantPort, timeout=3.0)
        collections = [c.name for c in client.get_collections().collections]
        if defaultCollectionName not in collections:
            client.create_collection(
                collection_name=defaultCollectionName,
                vectors_config=VectorParams(size=384, distance=Distance.COSINE),
            )
            print(f"Created Qdrant collection '{defaultCollectionName}'.")

        points = _buildQdrantPoints(catalogData, PointStruct)
        if points:
            client.upsert(collection_name=defaultCollectionName, points=points)
            print(f"Successfully upserted {len(points)} vector points into Qdrant.")
            return len(points)
        return 0
    except Exception as qdrantError:
        # Qdrant is genuinely optional: the mesh quotes, locks and settles without a vector
        # index -- only the Layer 3 substitution search needs one. So this stays non-fatal, but
        # it must not read as a transient hiccup when it is a service that never came up.
        print(
            f"Qdrant seeding FAILED ({qdrantError}). Continuing without a vector index: "
            "quoting and settlement work, out-of-stock substitution will find no candidates."
        )
        return qdrantSeedingFailed


async def seedCatalogStore() -> int:
    """Seeds merchant product catalog fixtures for Qdrant and Redis indexing.

    The exit code is load-bearing. docker-compose.yml gates both `mcp-server` and `merchant-api`
    on `catalog-seeder: service_completed_successfully`, so exiting 0 after a total seeding
    failure brings the mesh up looking healthy with nothing in the stores -- and the first
    symptom is a SKU that cannot be quoted, several layers away from the cause.

    Redis is required: the MCP server hydrates its catalog from `mesh:catalog:*` at boot, so an
    unseeded Redis means an empty catalog. Qdrant is not required, and is reported rather than
    treated as fatal -- quoting, locking and settlement all work without a vector index.
    """
    catalogData = loadCatalogFixtures()
    print(f"Loading {len(catalogData)} SKUs from {catalogFilePath}...")

    redisUrl = os.environ.get("REDIS_URL", defaultRedisUrl)
    qdrantHost = os.environ.get("QDRANT_HOST", defaultQdrantHost)
    qdrantPort = int(os.environ.get("QDRANT_PORT", defaultQdrantPort))

    try:
        seededCount = await seedRedisStore(catalogData, redisUrl)
    except Exception as redisError:
        print(
            "\nCatalog seeding aborted: Redis is required and could not be seeded "
            f"({redisError}). Services that depend on this seeder will not start."
        )
        return exitCodeSeedingFailed

    if not seededCount:
        print("\nCatalog seeding aborted: Redis reported zero SKUs written.")
        return exitCodeSeedingFailed

    qdrantResult = seedQdrantCollection(catalogData, qdrantHost, qdrantPort)
    if qdrantResult == qdrantSeedingFailed:
        print("Vector index unavailable; continuing because Qdrant is not required to settle.")

    print(f"\nCatalog seeding completed for {len(catalogData)} items.")
    return exitCodeSeedingSucceeded


if __name__ == "__main__":
    sys.exit(asyncio.run(seedCatalogStore()))
