import asyncio
import json
import os
import sys
from typing import Any, Dict, List, Optional

# Constants
defaultRedisUrl = "redis://localhost:6379/0"
defaultQdrantHost = "localhost"
defaultQdrantPort = 6333
defaultCollectionName = "razoragent_catalog"
fixturesDir = os.path.join(os.path.dirname(__file__), "..", "tests", "fixtures")
catalogFilePath = os.path.join(fixturesDir, "catalogFixtures.json")


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
            pipe.set(f"inventory:stock:{skuId}", str(stock))
            pipe.set(f"mesh:catalog:{skuId}", json.dumps(item))
        await pipe.execute()
        await redisConnection.aclose()
        print(f"Successfully seeded {len(catalogData)} SKUs into Redis store.")
        return len(catalogData)
    except Exception as redisError:
        print(f"Redis seeding skipped ({redisError}). Proceeding with mock validation.")
        return 0


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
        print(f"Qdrant seeding skipped ({qdrantError}). Proceeding.")
        return 0


async def seedCatalogStore() -> int:
    """Seeds merchant product catalog fixtures for Qdrant and Redis indexing."""
    catalogData = loadCatalogFixtures()
    print(f"Loading {len(catalogData)} SKUs from {catalogFilePath}...")

    redisUrl = os.environ.get("REDIS_URL", defaultRedisUrl)
    qdrantHost = os.environ.get("QDRANT_HOST", defaultQdrantHost)
    qdrantPort = int(os.environ.get("QDRANT_PORT", defaultQdrantPort))

    await seedRedisStore(catalogData, redisUrl)
    seedQdrantCollection(catalogData, qdrantHost, qdrantPort)

    print(f"\nCatalog inspection completed for {len(catalogData)} items.")
    return 0


if __name__ == "__main__":
    sys.exit(asyncio.run(seedCatalogStore()))
