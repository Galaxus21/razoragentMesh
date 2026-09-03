"""Unit and integration tests for Layer 3 vectorHealer filtering and searching."""

from typing import Any, Dict, List
import pytest

from razoragentMesh.packages.vectorHealer.src.constants.healerConstants import (
    qdrantCollectionName,
)
from razoragentMesh.packages.vectorHealer.src.constraints import (
    NegativeConstraintFilter,
    NegativeConstraintManifest,
)
from razoragentMesh.packages.vectorHealer.src.healerExceptions import (
    EmbeddingInferenceException,
)
from razoragentMesh.packages.vectorHealer.src.search import (
    EmbeddingProvider,
    VectorSearcher,
)


def testEmbeddingProviderNormalizationAndCosine() -> None:
    """Verifies vector normalization and cosine similarity computation."""
    provider = EmbeddingProvider()
    vec1 = [1.0, 0.0, 0.0]
    vec2 = [1.0, 0.0, 0.0]
    vec3 = [0.0, 1.0, 0.0]

    assert pytest.approx(provider.computeCosineSimilarity(vec1, vec2), 1e-5) == 1.0
    assert pytest.approx(provider.computeCosineSimilarity(vec1, vec3), 1e-5) == 0.0

    provider.registerCachedVector("test_sku", [3.0, 4.0, 0.0])
    emb = provider.computeEmbedding("test_sku")
    assert pytest.approx(sum(x * x for x in emb), 1e-5) == 1.0

    with pytest.raises(EmbeddingInferenceException):
        provider.computeEmbedding("")


def testNegativeConstraintFilterEvaluation() -> None:
    """Verifies allergen, brand, physical, and SLA constraint filtering."""
    manifest = NegativeConstraintManifest(
        excludedAllergens=["peanut"], excludedBrands=["BadBrand"],
        maxWeightGrams=500, maxSlaHours=48,
    )
    filterEngine = NegativeConstraintFilter(manifest)

    itemAllergen = {"skuId": "SKU-01", "brand": "GoodBrand", "attributes": {"allergens": ["peanut_oil"], "weightGrams": 200, "slaHours": 24}}
    evalAllergen = filterEngine.evaluateCandidate(itemAllergen)
    assert not evalAllergen.isAllowed and "ALLERGEN_BREACH" in str(evalAllergen.rejectionReason)

    itemBrand = {"skuId": "SKU-02", "brand": "BadBrand", "attributes": {"allergens": [], "weightGrams": 200, "slaHours": 24}}
    evalBrand = filterEngine.evaluateCandidate(itemBrand)
    assert not evalBrand.isAllowed and "BRAND_EXCLUDED" in str(evalBrand.rejectionReason)

    itemWeight = {"skuId": "SKU-03", "brand": "GoodBrand", "attributes": {"allergens": [], "weightGrams": 600, "slaHours": 24}}
    evalWeight = filterEngine.evaluateCandidate(itemWeight)
    assert not evalWeight.isAllowed and "WEIGHT_LIMIT_EXCEEDED" in str(evalWeight.rejectionReason)

    itemValid = {"skuId": "SKU-04", "brand": "GoodBrand", "attributes": {"allergens": [], "weightGrams": 300, "slaHours": 24}}
    evalValid = filterEngine.evaluateCandidate(itemValid)
    assert evalValid.isAllowed and evalValid.rejectionReason is None


def testVectorSearcherPriceAndStockFiltering(catalogFixtures: List[Dict[str, Any]]) -> None:
    """Verifies vector searcher excludes candidates exceeding price delta or with insufficient stock."""
    searcher = VectorSearcher(catalogStore=catalogFixtures)
    origItem = next(s for s in catalogFixtures if s["skuId"] == "SKU-101")
    candidates = searcher.searchCandidates(
        queryVector=origItem["embeddingVector"], hsnCode=origItem["hsnCode"],
        originalPricePaise=origItem["baseUnitPricePaise"], requestedQuantity=1,
        excludeSkuId="SKU-101", scoreThreshold=0.85, maxPriceDeltaPct=5.0,
    )
    assert len(candidates) >= 1
    assert candidates[0].skuId == "SKU-104" and candidates[0].score >= 0.85


def testVectorSearcherNativeQdrantFilterQuery() -> None:
    """Verifies VectorSearcher constructs proper native Qdrant models.Filter with availableStock."""
    capturedCalls: List[Dict[str, Any]] = []

    class NativeMockPoint:
        def __init__(self, skuId: str, price: int, stock: int, score: float) -> None:
            self.score = score
            self.payload = {"skuId": skuId, "baseUnitPricePaise": price, "availableStock": stock, "hsnCode": "8471"}

    class NativeMockQdrant:
        def search(
            self,
            collection_name: str,
            query_vector: List[float],
            query_filter: Any,
            limit: int,
            score_threshold: float,
        ) -> List[NativeMockPoint]:
            capturedCalls.append({
                "collection_name": collection_name,
                "query_vector": query_vector,
                "query_filter": query_filter,
                "limit": limit,
                "score_threshold": score_threshold,
            })
            return [NativeMockPoint("SKU-NATIVE-1", 10000, 10, 0.95)]

    nativeClient = NativeMockQdrant()
    searcher = VectorSearcher(qdrantClient=nativeClient)
    candidates = searcher.searchCandidates(
        queryVector=[0.1] * 384,
        hsnCode="8471",
        originalPricePaise=10000,
        requestedQuantity=1,
        excludeSkuId="SKU-EXCLUDE",
    )

    assert len(candidates) == 1
    assert candidates[0].skuId == "SKU-NATIVE-1"
    assert len(capturedCalls) == 1
    call = capturedCalls[0]
    # The name the Merchant API indexes into, not a literal: the healer spent its whole life
    # querying "merchantCatalog", which nothing ever wrote, and this assertion pinned it.
    assert call["collection_name"] == qdrantCollectionName
    qFilter = call["query_filter"]
    assert qFilter is not None
    # Check must conditions contains availableStock FieldCondition
    mustConds = qFilter.must
    stockCond = next((c for c in mustConds if c.key == "availableStock"), None)
    assert stockCond is not None
    assert stockCond.range.gte == 1


def testVectorSearcherZeroAvailableStockExclusion() -> None:
    """Verifies VectorSearcher strictly excludes points when availableStock is 0."""
    catalog = [
        {
            "skuId": "SKU-OOS-01",
            "hsnCode": "8471",
            "baseUnitPricePaise": 10000,
            "availableStock": 0,
            "embeddingVector": [1.0, 0.0],
        }
    ]
    searcher = VectorSearcher(catalogStore=catalog)
    candidates = searcher.searchCandidates(
        queryVector=[1.0, 0.0],
        hsnCode="8471",
        originalPricePaise=10000,
        requestedQuantity=1,
    )
    assert len(candidates) == 0


def testVectorSearcherZeroPriceAndNonePayloadEdgeCases() -> None:
    """Verifies VectorSearcher does not divide by zero on 0-priced SKUs and handles empty payloads."""
    class MockPointWithNonePayload:
        def __init__(self, id: str) -> None:
            self.id = id
            self.score = 0.99
            self.payload = None

    class BrokenNativeClient:
        def search(self, *args: Any, **kwargs: Any) -> List[Any]:
            raise ConnectionError("Qdrant cluster temporarily unreachable")

    # In-memory fallback on client exception
    catalog = [
        {
            "skuId": "SKU-FREE-01",
            "hsnCode": "8471",
            "baseUnitPricePaise": 0,
            "availableStock": 10,
            "embeddingVector": [1.0, 0.0],
        }
    ]
    searcher = VectorSearcher(qdrantClient=BrokenNativeClient(), catalogStore=catalog)
    candidates = searcher.searchCandidates(
        queryVector=[1.0, 0.0],
        hsnCode="8471",
        originalPricePaise=0,
        requestedQuantity=1,
    )
    assert len(candidates) == 1
    assert candidates[0].skuId == "SKU-FREE-01"

    # Qualification with None payload object
    qualified = searcher._qualifyCandidate(
        pt=MockPointWithNonePayload("SKU-NONE"),
        originalPricePaise=1000,
        requestedQuantity=1,
        maxPriceDeltaPct=10.0,
    )
    assert qualified is None  # candStock is 0 < requestedQuantity 1

