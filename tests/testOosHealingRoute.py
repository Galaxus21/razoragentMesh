"""Pins that Layer 3 is a running route, not a library nothing constructs.

The audit's first finding was that `OosInterceptor` had zero construction sites outside its own
tests: no FastAPI app, no dashboard route, no compose service built one, while README §"Layer 3",
GUIDE.md and the dashboard's `protocolLayerMap.ts` all named it as a live component. It was worse
than unconstructed -- no Dockerfile copied `packages/vectorHealer` into an image, so the code was
not even present in the running mesh.

These tests exercise the route through the real `createMerchantApp()` factory, so a regression
that unmounts the router, or an import error inside the healer, fails here.
"""

import json
from typing import Any, Dict, List

import pytest
from fastapi.testclient import TestClient

from razoragentMesh.packages.merchantApi.src.merchantApp import createMerchantApp
from razoragentMesh.packages.merchantApi.src.routes.oosHealingRoute import (
    noSubstituteReason,
    unknownSkuReason,
)

healEndpoint = "/api/v1/catalog/heal-oos"


class _StubVectorizer:
    """Stands in for the AutoVectorizer the app builds in its lifespan."""

    def __init__(self, qdrantClient: Any) -> None:
        self.qdrantClient = qdrantClient


@pytest.fixture()
def healingClient(
    catalogFixtures: List[Dict[str, Any]], mockQdrantClient: Any
) -> TestClient:
    """Builds the real app with the catalog in Redis and vectors in Qdrant."""
    from razoragentMesh.tests.mockInfraHelpers import MockRedisAsync

    app = createMerchantApp()
    redis = MockRedisAsync()
    for item in catalogFixtures:
        redis.store[f"mesh:catalog:{item['skuId']}"] = json.dumps(item)
    app.state.redis = redis
    app.state.vectorizer = _StubVectorizer(mockQdrantClient)
    return TestClient(app, raise_server_exceptions=False)


def testHealingRouteIsMountedOnTheRealApp(healingClient: TestClient) -> None:
    """The route exists on the app factory, not merely in a module.

    This is the assertion that would have failed for the entire life of the project before now.
    """
    # Read from the OpenAPI schema rather than app.routes: FastAPI 0.141 defers router
    # inclusion, so app.routes holds opaque _IncludedRouter objects until the app is built.
    schema = healingClient.get("/openapi.json").json()
    assert healEndpoint in schema["paths"], sorted(schema["paths"])


def testHealingFindsASubstituteForAnOutOfStockSku(healingClient: TestClient) -> None:
    """A real substitution search runs and returns a candidate with its cosine score."""
    response = healingClient.post(
        healEndpoint, json={"failedSkuId": "SKU-101", "requestedQuantity": 1}
    )
    assert response.status_code == 200, response.text
    body = response.json()
    assert body["healed"] is True, body
    assert body["substituteSkuId"] == "SKU-104"
    assert body["cosineScore"] >= 0.85
    assert body["substitutePayload"]["skuId"] == "SKU-104"


def testHealingDurationIsMeasuredNotConstant(healingClient: TestClient) -> None:
    """The reported latency comes from time.perf_counter, not from a literal.

    `scripts/seedTelemetryStream.py` used to emit `"healingDurationMs": 214` and was the only
    producer of healing telemetry in the repository, so the dashboard displayed 214ms under a
    "Sub-300ms Vector Self-Healing" heading no matter what any code did. Two identical requests
    returning byte-identical durations would mean a constant had crept back in.
    """
    durations = set()
    for _ in range(3):
        response = healingClient.post(
            healEndpoint, json={"failedSkuId": "SKU-101", "requestedQuantity": 1}
        )
        durations.add(response.json()["healingDurationMs"])

    assert len(durations) > 1, f"every run reported the same duration: {durations}"
    assert all(duration > 0 for duration in durations)
    assert 214 not in durations


def testHealingReportsWhichProducerMadeTheVectors(healingClient: TestClient) -> None:
    """Every response says whether the score came from a model or a character hash.

    `embeddingProvider` silently returns hash pseudo-vectors when fastembed cannot load, which on
    an offline machine turns "cosine similarity" into character-code overlap with nothing in the
    output to distinguish the two. A score is only meaningful alongside its producer.
    """
    response = healingClient.post(
        healEndpoint, json={"failedSkuId": "SKU-101", "requestedQuantity": 1}
    )
    assert response.json()["embeddingMode"] in ("model", "hash")


def testUnknownSkuIsRefusedWithAReasonRatherThanAnError(healingClient: TestClient) -> None:
    """An unknown SKU is a answerable question, not a 500."""
    response = healingClient.post(
        healEndpoint, json={"failedSkuId": "SKU-NOT-REAL", "requestedQuantity": 1}
    )
    assert response.status_code == 200
    body = response.json()
    assert body["healed"] is False
    assert body["reason"] == unknownSkuReason
    assert body["healingDurationMs"] >= 0


def testNoQualifyingSubstituteIsDistinguishedFromAnUnknownSku(
    healingClient: TestClient,
) -> None:
    """"Nothing close enough" and "never heard of it" must not look the same.

    Collapsing them is how an agent concludes a product does not exist when in fact the vector
    store simply had no match above the similarity floor.
    """
    # A zero price-delta tolerance rejects every candidate at the healer's own qualification
    # step (SKU-104 is +Rs.50 on SKU-101), so this exercises the real filter rather than the
    # vector store's scoring.
    response = healingClient.post(
        healEndpoint,
        json={
            "failedSkuId": "SKU-101",
            "requestedQuantity": 1,
            "maxPriceDeltaPercent": 0.0,
        },
    )
    body = response.json()
    assert body["healed"] is False, body
    assert body["reason"] == noSubstituteReason
    assert body["reason"] != unknownSkuReason


def testASuccessfulHealPublishesMeasuredLiveTelemetry(
    healingClient: TestClient, monkeypatch: pytest.MonkeyPatch
) -> None:
    """A real heal reaches the dashboard's event stream stamped LIVE.

    OOS_HEALED had one producer before this: scripts/seedTelemetryStream.py, emitting a fixed
    214ms stamped SYNTHETIC. metricsBar.tsx now excludes SYNTHETIC from the latency average, so
    without a LIVE producer the tile reads "no measured heals yet" forever and Layer 3 stays
    invisible in the very dashboard that names it.
    """
    from razoragentMesh.packages.merchantApi.src.routes import healingTelemetry

    published: List[Dict[str, Any]] = []
    monkeypatch.setattr(healingTelemetry, "_fireAndForget", published.append)

    response = healingClient.post(
        healEndpoint, json={"failedSkuId": "SKU-101", "requestedQuantity": 1}
    )
    assert response.json()["healed"] is True

    assert len(published) == 1, published
    event = published[0]
    assert event["eventType"] == "OOS_HEALED"
    # UNKNOWN is TelemetryEventModel's default; only an explicit LIVE counts as measured.
    assert event["provenance"] == "LIVE"
    assert event["payload"]["originalSkuId"] == "SKU-101"
    assert event["payload"]["substituteSkuId"] == "SKU-104"
    assert event["payload"]["embeddingMode"] in ("model", "hash")
    # The measured figure the route returned, not a constant and not the seeder's 214.
    assert event["payload"]["healingDurationMs"] == response.json()["healingDurationMs"]
    assert event["payload"]["healingDurationMs"] != 214


def testADeadTelemetryBusDoesNotFailTheHeal(
    healingClient: TestClient, monkeypatch: pytest.MonkeyPatch
) -> None:
    """Telemetry is a view of the system, not part of it.

    The MCP server's publisher states this contract explicitly; this route has to honour it too,
    or an unreachable mandate engine turns every substitution into a 500.
    """
    from razoragentMesh.packages.merchantApi.src.routes import healingTelemetry

    def explode(_event: Dict[str, Any]) -> None:
        raise RuntimeError("telemetry bus is down")

    monkeypatch.setattr(healingTelemetry, "_fireAndForget", explode)

    response = healingClient.post(
        healEndpoint, json={"failedSkuId": "SKU-101", "requestedQuantity": 1}
    )
    assert response.status_code == 200, response.text
    assert response.json()["healed"] is True
