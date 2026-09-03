import json
import math
import time
from typing import Any, Dict, List, Optional

defaultLockTtlSeconds: int = 60
defaultCosineThreshold: float = 0.85


class MockRedisAsync:
    """In-memory async Redis mock with atomic Lua inventory lock execution."""

    def __init__(self) -> None:
        self.store: Dict[str, Any] = {}
        self.expirations: Dict[str, float] = {}
        self.fencingCounters: Dict[str, int] = {}

    def _isExpired(self, key: str) -> bool:
        if key in self.expirations:
            if time.time() > self.expirations[key]:
                self.store.pop(key, None)
                self.expirations.pop(key, None)
                return True
        return False

    async def get(self, key: str) -> Optional[str]:
        if self._isExpired(key):
            return None
        value = self.store.get(key)
        return str(value) if value is not None else None

    async def set(
        self,
        key: str,
        value: Any,
        ex: Optional[int] = None,
        nx: bool = False,
    ) -> bool:
        self._isExpired(key)
        if nx and key in self.store:
            return False
        self.store[key] = value
        if ex is not None:
            self.expirations[key] = time.time() + ex
        else:
            self.expirations.pop(key, None)
        return True

    async def setnx(self, key: str, value: Any) -> bool:
        return await self.set(key, value, nx=True)

    async def decrby(self, key: str, amount: int) -> int:
        self._isExpired(key)
        currentValue = int(self.store.get(key, 0))
        newValue = currentValue - amount
        self.store[key] = newValue
        return newValue

    async def incr(self, key: str) -> int:
        self._isExpired(key)
        currentValue = int(self.store.get(key, 0))
        newValue = currentValue + 1
        self.store[key] = newValue
        return newValue

    async def expire(self, key: str, seconds: int) -> bool:
        if key not in self.store or self._isExpired(key):
            return False
        self.expirations[key] = time.time() + seconds
        return True

    async def rpush(self, key: str, *values: Any) -> int:
        self._isExpired(key)
        if key not in self.store or not isinstance(self.store[key], list):
            self.store[key] = []
        for val in values:
            self.store[key].append(val)
        return len(self.store[key])

    async def lpop(self, key: str) -> Optional[str]:
        if self._isExpired(key):
            return None
        lst = self.store.get(key)
        if isinstance(lst, list) and len(lst) > 0:
            val = lst.pop(0)
            return str(val) if val is not None else None
        return None

    async def llen(self, key: str) -> int:
        if self._isExpired(key):
            return 0
        lst = self.store.get(key)
        return len(lst) if isinstance(lst, list) else 0

    async def lrange(self, key: str, start: int, stop: int) -> List[str]:
        if self._isExpired(key):
            return []
        lst = self.store.get(key)
        if not isinstance(lst, list):
            return []
        end = None if stop == -1 else stop + 1
        sliceItems = lst[start:end]
        return [str(item) for item in sliceItems]

    async def delete(self, *keys: str) -> int:
        count = 0
        for key in keys:
            if key in self.store:
                self.store.pop(key, None)
                self.expirations.pop(key, None)
                count += 1
        return count

    async def flushdb(self) -> bool:
        self.store.clear()
        self.expirations.clear()
        self.fencingCounters.clear()
        return True

    async def eval(
        self,
        script: str,
        numkeys: int,
        *keysAndArgs: Any,
    ) -> Any:
        """Atomic Lua script executor for inventory locking and fencing."""
        keys = list(keysAndArgs[:numkeys])
        args = list(keysAndArgs[numkeys:])

        stockKey = str(keys[0])
        fencingKey = str(keys[1]) if len(keys) > 1 else f"{stockKey}:fence"
        requestedQty = int(args[0]) if len(args) > 0 else 1
        lockToken = str(args[1]) if len(args) > 1 else "default_token"
        lockTtl = int(args[2]) if len(args) > 2 else defaultLockTtlSeconds

        currentStock = int(self.store.get(stockKey, 0))
        if currentStock < requestedQty:
            return [-1, currentStock]

        newStock = currentStock - requestedQty
        self.store[stockKey] = newStock

        fenceCounter = self.fencingCounters.get(fencingKey, 0) + 1
        self.fencingCounters[fencingKey] = fenceCounter

        lockRecordKey = f"lock:{lockToken}"
        self.store[lockRecordKey] = {
            "skuId": stockKey.replace("sku:", "").replace(":stock", ""),
            "quantityLocked": requestedQty,
            "fencingToken": fenceCounter,
        }
        self.expirations[lockRecordKey] = time.time() + lockTtl
        return [1, fenceCounter]


class ScoredPoint:
    def __init__(self, pointId: str, score: float, payload: Dict[str, Any]) -> None:
        self.id = pointId
        self.score = score
        self.payload = payload


class MockQdrantClient:
    """In-memory vector database mock with cosine similarity search and payload filtering."""

    def __init__(self) -> None:
        self.collections: Dict[str, List[Dict[str, Any]]] = {}

    def createCollection(self, collectionName: str) -> None:
        if collectionName not in self.collections:
            self.collections[collectionName] = []

    def upsert(self, collectionName: str, points: List[Dict[str, Any]]) -> None:
        if collectionName not in self.collections:
            self.collections[collectionName] = []
        existingIds = {p["id"] for p in self.collections[collectionName]}
        for point in points:
            if point["id"] in existingIds:
                self.collections[collectionName] = [
                    p for p in self.collections[collectionName] if p["id"] != point["id"]
                ]
            self.collections[collectionName].append(point)

    def _computeCosineSimilarity(
        self, vecA: List[float], vecB: List[float]
    ) -> float:
        dotProduct = sum(a * b for a, b in zip(vecA, vecB))
        normA = math.sqrt(sum(a * a for a in vecA))
        normB = math.sqrt(sum(b * b for b in vecB))
        if normA == 0.0 or normB == 0.0:
            return 0.0
        return dotProduct / (normA * normB)

    def search(
        self,
        collectionName: str,
        queryVector: List[float],
        limit: int = 5,
        scoreThreshold: float = defaultCosineThreshold,
        filterHsnCode: Optional[str] = None,
        excludeSkuId: Optional[str] = None,
    ) -> List[ScoredPoint]:
        points = self.collections.get(collectionName, [])
        scoredResults: List[ScoredPoint] = []

        for point in points:
            skuId = point["payload"].get("skuId")
            if excludeSkuId and skuId == excludeSkuId:
                continue
            if filterHsnCode and point["payload"].get("hsnCode") != filterHsnCode:
                continue

            similarity = self._computeCosineSimilarity(
                queryVector, point["vector"]
            )
            if similarity >= scoreThreshold:
                scoredResults.append(
                    ScoredPoint(point["id"], similarity, point["payload"])
                )

        scoredResults.sort(key=lambda item: item.score, reverse=True)
        return scoredResults[:limit]


class MockRazorpayRouteClient:
    """Mock Razorpay Route and payment clearing client with failure simulation."""

    def __init__(self, responses: Dict[str, Any]) -> None:
        self.responses = responses
        self.transfersCreated: List[Dict[str, Any]] = []
        self.reversalsCreated: List[Dict[str, Any]] = []
        self.paymentsCaptured: List[Dict[str, Any]] = []
        self.simulateSecondaryTransferFailure = False

    async def createTransfer(
        self,
        recipientAccountId: str,
        amountPaise: int,
        currency: str = "INR",
        notes: Optional[Dict[str, Any]] = None,
    ) -> Dict[str, Any]:
        if not isinstance(amountPaise, int):
            raise ValueError("Transfer amount must be integer paise")

        if self.simulateSecondaryTransferFailure and len(self.transfersCreated) >= 1:
            raise RuntimeError("Route transfer dispatch failed: Secondary split error")

        transferRecord = {
            "id": f"trf_mock_{len(self.transfersCreated) + 1}",
            "entity": "transfer",
            "status": "processed",
            "recipient": recipientAccountId,
            "amount": amountPaise,
            "currency": currency,
            "notes": notes or {},
            "created_at": int(time.time()),
        }
        self.transfersCreated.append(transferRecord)
        return transferRecord

    async def reverseTransfer(
        self,
        transferId: str,
        amountPaise: Optional[int] = None,
    ) -> Dict[str, Any]:
        reversalRecord = {
            "id": f"rtrn_mock_{len(self.reversalsCreated) + 1}",
            "entity": "reversal",
            "transfer_id": transferId,
            "amount": amountPaise,
            "currency": "INR",
            "status": "processed",
            "created_at": int(time.time()),
        }
        self.reversalsCreated.append(reversalRecord)
        return reversalRecord

    async def capturePayment(
        self,
        paymentId: str,
        amountPaise: int,
        currency: str = "INR",
    ) -> Dict[str, Any]:
        if not isinstance(amountPaise, int):
            raise ValueError("Capture amount must be integer paise")
        captureRecord = {
            "id": paymentId,
            "entity": "payment",
            "amount": amountPaise,
            "currency": currency,
            "status": "captured",
            "created_at": int(time.time()),
        }
        self.paymentsCaptured.append(captureRecord)
        return captureRecord


async def seedNegotiableMerchant(
    redisClient: Any,
    skuId: str,
    merchantDid: str,
    listPricePaise: int,
    marginFloorBps: int = 1000,
    negotiationEnabled: bool = True,
    maxNegotiationTurns: int = 5,
) -> None:
    """Writes the two merchant-owned records the x402 gateway needs to allow a negotiation.

    Negotiation is opt-in: `resolveMerchantNegotiationTerms` refuses unless BOTH the SKU listing
    (which supplies the authoritative list price and owning merchant) and a policy with
    `negotiationEnabled` are present. Seeding only one of the two is the most likely way to write
    a test that fails for the wrong reason, so both live in one helper.
    """
    await redisClient.set(
        f"mesh:catalog:{skuId}",
        json.dumps(
            {
                "skuId": skuId,
                "merchantDid": merchantDid,
                "title": "Seeded Negotiable SKU",
                "baseUnitPricePaise": listPricePaise,
                "availableStock": 100,
            }
        ),
    )
    await redisClient.set(
        f"mesh:merchant:policy:{merchantDid}",
        json.dumps(
            {
                "merchantDid": merchantDid,
                "negotiationEnabled": negotiationEnabled,
                "marginFloorBps": marginFloorBps,
                "minimumOrderQuantity": 1,
                "autoAcceptSpreadPaise": 0,
                "maxNegotiationTurns": maxNegotiationTurns,
                "createdAtTimestamp": 1788400000,
                "updatedAtTimestamp": 1788400000,
            }
        ),
    )
