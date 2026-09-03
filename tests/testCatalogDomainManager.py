"""Unit test suite for merchantApi catalog manager, Qdrant patcher, and vectorizer."""

from typing import Any
from decimal import Decimal
import pytest
import pytest_asyncio

from razoragentMesh.packages.merchantApi import (
    ApparelFacet,
    AutoVectorizer,
    CatalogManager,
    FmcgFacet,
    JewelryFacet,
    PharmaFacet,
    QdrantPayloadPatcher,
    UniversalProductListing,
    synthesizeFacetDescription,
)
from razoragentMesh.packages.merchantApi.src.catalog.autoVectorizer import pointIdForSku
from razoragentMesh.tests.mockInfraHelpers import MockQdrantClient, MockRedisAsync


@pytest.fixture
def mockQdrant() -> MockQdrantClient:
    client = MockQdrantClient()
    client.createCollection("merchantCatalog")
    return client


@pytest_asyncio.fixture
async def mockRedis() -> MockRedisAsync:
    client = MockRedisAsync()
    yield client
    await client.flushdb()


@pytest.mark.asyncio
async def testCatalogManagerLifecycle(mockRedis: MockRedisAsync) -> None:
    manager = CatalogManager(redisClient=mockRedis)
    listing = UniversalProductListing(
        skuId="SKU-GOLD-RING-01", merchantDid="did:mesh:merchant_tanishq_01",
        title="22K Gold Floral Ring", description="Floral design 22K gold ring",
        category="Jewelry", hsnCode="71131900", gstRatePercent=3,
        baseUnitPricePaise=4500000, availableStock=10, originPincode="560001",
        jewelryFacet=JewelryFacet(purityCarat=22, grossWeightGrams=Decimal("5.4"), hallmarkNumber="916"),
    )
    await manager.upsertSku(listing)
    retrieved = await manager.getSku("SKU-GOLD-RING-01")
    assert retrieved is not None and retrieved.skuId == "SKU-GOLD-RING-01"
    assert retrieved.title == "22K Gold Floral Ring" and retrieved.gstRatePercent == 3

    merchantSkus = await manager.listMerchantSkus("did:mesh:merchant_tanishq_01")
    assert "SKU-GOLD-RING-01" in merchantSkus

    removed = await manager.removeSku("SKU-GOLD-RING-01", "did:mesh:merchant_tanishq_01")
    assert removed is True
    assert await manager.getSku("SKU-GOLD-RING-01") is None


@pytest.mark.asyncio
async def testQdrantPayloadPatcher(mockQdrant: MockQdrantClient) -> None:
    mockQdrant.upsert("merchantCatalog", [
        {"id": "SKU-RING-01", "vector": [0.1] * 384, "payload": {"skuId": "SKU-RING-01", "availableStock": 10}},
        {"id": "SKU-RING-02", "vector": [0.2] * 384, "payload": {"skuId": "SKU-RING-02", "availableStock": 10}},
    ])
    patcher = QdrantPayloadPatcher(qdrantClient=mockQdrant, collectionName="merchantCatalog")

    await patcher.setAvailableStock("SKU-RING-01", availableStock=0)
    pts = mockQdrant.collections["merchantCatalog"]
    pt1 = next(p for p in pts if p["id"] == "SKU-RING-01")
    assert pt1["payload"]["availableStock"] == 0

    await patcher.batchSetAvailableStock(["SKU-RING-01", "SKU-RING-02"], availableStock=15)
    assert pt1["payload"]["availableStock"] == 15
    assert next(p for p in pts if p["id"] == "SKU-RING-02")["payload"]["availableStock"] == 15


@pytest.mark.asyncio
async def testQdrantPayloadPatcherNativeClient() -> None:
    capturedCalls = []

    class NativeMockQdrantClient:
        def set_payload(self, collection_name: str, payload: dict, points: Any) -> bool:
            capturedCalls.append({
                "collection_name": collection_name,
                "payload": payload,
                "points": points,
            })
            return True

    nativeClient = NativeMockQdrantClient()
    patcher = QdrantPayloadPatcher(qdrantClient=nativeClient, collectionName="merchantCatalog")

    await patcher.setAvailableStock("SKU-NATIVE-01", availableStock=42)
    assert len(capturedCalls) == 1
    call1 = capturedCalls[0]
    assert call1["collection_name"] == "merchantCatalog"
    assert call1["payload"] == {"availableStock": 42}
    must1 = call1["points"].must[0]
    assert must1.key == "skuId" and must1.match.value == "SKU-NATIVE-01"

    await patcher.batchSetAvailableStock(["SKU-NATIVE-01", "SKU-NATIVE-02"], availableStock=99)
    assert len(capturedCalls) == 2
    call2 = capturedCalls[1]
    assert call2["collection_name"] == "merchantCatalog"
    assert call2["payload"] == {"availableStock": 99}
    must2 = call2["points"].must[0]
    assert must2.key == "skuId" and must2.match.any == ["SKU-NATIVE-01", "SKU-NATIVE-02"]

    # Negative stock clamping
    await patcher.setAvailableStock("SKU-NATIVE-01", availableStock=-10)
    assert capturedCalls[2]["payload"] == {"availableStock": 0}


def testQdrantPayloadPatcherFallbackAnnotations() -> None:
    """Verifies _getQdrantModels fallback provides valid models and types without NameError."""
    from razoragentMesh.packages.merchantApi.src.catalog.qdrantPayloadPatcher import _getQdrantModels
    models = _getQdrantModels()
    filt = models.Filter(must=[models.FieldCondition(key="skuId", match=models.MatchValue(value="SKU-1"))])
    assert len(filt.must) == 1
    assert filt.must[0].key == "skuId"
    assert filt.must[0].match.value == "SKU-1"


def testSynthesizeJewelryAndApparelFacet() -> None:
    jewelryListing = UniversalProductListing(
        skuId="SKU-JEW-01", merchantDid="did:mesh:m1", title="Tanishq 22K Gold Ring",
        description="Authentic hallmark gold ring", category="Jewelry", hsnCode="7113",
        gstRatePercent=3, baseUnitPricePaise=3600000, availableStock=5, originPincode="560001",
        jewelryFacet=JewelryFacet(purityCarat=22, grossWeightGrams=Decimal("5.4"), hallmarkNumber="916"),
    )
    desc1 = synthesizeFacetDescription(jewelryListing)
    assert "Jewelry" in desc1 and "Tanishq 22K Gold Ring" in desc1 and "Gross 5.4g" in desc1
    assert "BIS Hallmark 916" in desc1 and "HSN 7113" in desc1

    apparelListing = UniversalProductListing(
        skuId="SKU-APP-01", merchantDid="did:mesh:m2", title="FabIndia Cotton Kurta",
        description="Pure cotton handcrafted kurta", category="Apparel", hsnCode="6109",
        gstRatePercent=5, baseUnitPricePaise=199900, availableStock=20, originPincode="110001",
        apparelFacet=ApparelFacet(size="M", color="Navy Blue", fabric=["Cotton"]),
    )
    assert synthesizeFacetDescription(apparelListing) == "Apparel | FabIndia Cotton Kurta | Size M | Navy Blue | Fabric: Cotton | HSN 6109"


def testSynthesizePharmaAndFmcgFacet() -> None:
    pharmaListing = UniversalProductListing(
        skuId="SKU-PHARM-01", merchantDid="did:mesh:m3", title="Crocin 500mg",
        description="Paracetamol tablet 500mg", category="Pharma", hsnCode="3004",
        gstRatePercent=12, baseUnitPricePaise=5000, availableStock=100, originPincode="400001",
        pharmaFacet=PharmaFacet(activeSalt="Paracetamol", dosageMg=500, schedule="Schedule H"),
    )
    assert synthesizeFacetDescription(pharmaListing) == "Pharma | Crocin 500mg | Active: Paracetamol | Schedule H | HSN 3004"

    fmcgListing = UniversalProductListing(
        skuId="SKU-OIL-01", merchantDid="did:mesh:m4", title="FarmPure Groundnut Oil 15L",
        description="Cold pressed virgin groundnut oil", category="FMCG", hsnCode="1508",
        gstRatePercent=5, baseUnitPricePaise=280000, availableStock=15, originPincode="380001",
        fmcgFacet=FmcgFacet(allergens=["Peanuts"], isVeg=True),
    )
    assert synthesizeFacetDescription(fmcgListing) == "FMCG | FarmPure Groundnut Oil 15L | Allergens: Peanuts | Veg | HSN 1508"


@pytest.mark.asyncio
async def testAutoVectorizerUpsertAndRemove(mockQdrant: MockQdrantClient) -> None:
    vectorizer = AutoVectorizer(qdrantClient=mockQdrant, collectionName="merchantCatalog")
    listing = UniversalProductListing(
        skuId="SKU-JEW-02", merchantDid="did:mesh:m1", title="MMTC-PAMP 24K Gold Coin 10g",
        description="999.9 pure gold coin", category="Jewelry", hsnCode="7114",
        gstRatePercent=3, baseUnitPricePaise=6800000, availableStock=8, originPincode="122001",
        jewelryFacet=JewelryFacet(purityCarat=24, grossWeightGrams=Decimal("10.0"), hallmarkNumber="9999"),
    )
    await vectorizer.upsertListing(listing)
    pts = mockQdrant.collections["merchantCatalog"]
    assert len(pts) == 1 and pts[0]["id"] == pointIdForSku("SKU-JEW-02")
    # The id is a derived UUID because Qdrant rejects arbitrary strings; the SKU stays
    # recoverable from the payload, which is what every read path actually uses.
    assert pts[0]["payload"]["skuId"] == "SKU-JEW-02" and pts[0]["payload"]["availableStock"] == 8

    await vectorizer.removeListing("SKU-JEW-02")
    assert len(mockQdrant.collections["merchantCatalog"]) == 0


@pytest.mark.asyncio
async def testAutoVectorizerNativeClientUpsertAndRemove() -> None:
    upsertCalls = []
    deleteCalls = []

    class NativeQdrantClientMock:
        def upsert(self, collection_name: str, points: Any) -> bool:
            upsertCalls.append({"collection_name": collection_name, "points": points})
            return True

        def delete(self, collection_name: str, points_selector: Any) -> bool:
            deleteCalls.append({"collection_name": collection_name, "points_selector": points_selector})
            return True

    nativeClient = NativeQdrantClientMock()
    vectorizer = AutoVectorizer(qdrantClient=nativeClient, collectionName="merchantCatalog")
    listing = UniversalProductListing(
        skuId="SKU-NAT-01", merchantDid="did:mesh:m1", title="MMTC Gold Bar",
        description="Fine gold", category="Jewelry", hsnCode="7114",
        gstRatePercent=3, baseUnitPricePaise=6800000, availableStock=12, originPincode="122001",
    )

    await vectorizer.upsertListing(listing)
    assert len(upsertCalls) == 1
    pt = upsertCalls[0]["points"][0]
    assert pt.id == pointIdForSku("SKU-NAT-01")
    assert pt.payload["availableStock"] == 12
    assert pt.payload["skuId"] == "SKU-NAT-01"

    await vectorizer.removeListing("SKU-NAT-01")
    assert len(deleteCalls) == 1
    assert deleteCalls[0]["points_selector"].points == [pointIdForSku("SKU-NAT-01")]

