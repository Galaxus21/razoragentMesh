"""Covers what the catalog seeder writes about ownership and negotiation consent.

Found live, not by a unit test: the 25 seeded industrial SKUs carried no `merchantDid` at all.
Nothing noticed while the negotiate route took the merchant from the buyer's request body, but the
moment the gateway started resolving the owning merchant from the listing, every seeded SKU became
permanently non-negotiable -- refused with "names no owning merchant" no matter what policy a
merchant saved. SKU-001 is the SKU the demo negotiates over.

The seeder has had no test of any kind, and both facts it writes here are invisible to every other
suite: the rest of the tests construct listings directly.
"""

import importlib.util
import json
import os
from typing import Any, Dict, List

import pytest

seederPath = os.path.join(os.path.dirname(__file__), "..", "scripts", "seedCatalog.py")
_spec = importlib.util.spec_from_file_location("seedCatalogModule", seederPath)
assert _spec is not None and _spec.loader is not None
seedCatalogModule = importlib.util.module_from_spec(_spec)
_spec.loader.exec_module(seedCatalogModule)


class _RecordingPipeline:
    """Captures the writes the seeder pipelines rather than performing them."""

    def __init__(self) -> None:
        self.writes: Dict[str, str] = {}

    def set(self, key: str, value: str) -> None:
        self.writes[key] = value

    async def execute(self) -> List[Any]:
        return []


class _RecordingRedis:
    def __init__(self) -> None:
        self.pipelineObject = _RecordingPipeline()

    async def ping(self) -> bool:
        return True

    def pipeline(self) -> _RecordingPipeline:
        return self.pipelineObject

    async def aclose(self) -> None:
        return None


@pytest.fixture
def seededWrites(monkeypatch: pytest.MonkeyPatch) -> Dict[str, str]:
    """Runs the seeder against a recording client and returns every key it wrote."""
    recorder = _RecordingRedis()

    # `from_url` on the real module, rather than a stand-in module in sys.modules: redis.asyncio
    # is a subpackage the rest of redis imports from, so shadowing it breaks the real package's
    # own import chain and the failure looks like a broken environment.
    import asyncio

    import redis.asyncio

    monkeypatch.setattr(
        redis.asyncio, "from_url", lambda *args, **kwargs: recorder, raising=True
    )

    catalogData = seedCatalogModule.loadCatalogFixtures()
    asyncio.run(seedCatalogModule.seedRedisStore(catalogData, "redis://localhost:6379/0"))
    return recorder.pipelineObject.writes


def testEverySeededSkuNamesItsOwningMerchant(seededWrites: Dict[str, str]) -> None:
    """The gateway resolves a SKU's merchant from its listing; an unowned SKU cannot negotiate."""
    listings = {k: v for k, v in seededWrites.items() if k.startswith("mesh:catalog:")}
    assert listings, "the seeder wrote no catalog listings at all"

    for key, raw in listings.items():
        record = json.loads(raw)
        assert record.get("merchantDid") == seedCatalogModule.seedMerchantDid, (
            f"{key} names no owning merchant"
        )


def testTheFixtureItselfCarriesNoMerchantSoTheSeederMustAddOne() -> None:
    """Pins WHY the seeder stamps it: removing the stamp would silently break negotiation again."""
    for item in seedCatalogModule.loadCatalogFixtures():
        assert "merchantDid" not in item


def testSeededSkusKeepTheirOwnFields(seededWrites: Dict[str, str]) -> None:
    """The stamp is a prefix, not a replacement -- a fixture that declared one would still win."""
    record = json.loads(seededWrites["mesh:catalog:SKU-001"])
    assert record["baseUnitPricePaise"] > 0
    assert record["skuId"] == "SKU-001"
    assert seededWrites["inventory:stock:SKU-001"] == str(record["availableStock"])


def testTheDemoMerchantsNegotiationOptInIsSeeded(seededWrites: Dict[str, str]) -> None:
    """Seeded as data, so the gateway's default stays opt-in and this merchant has simply opted in.

    Without it a fresh `docker compose up` answers DECLINED to every bid, and the negotiation
    feature reads as broken rather than as declined.
    """
    key = f"mesh:merchant:policy:{seedCatalogModule.seedMerchantDid}"
    assert key in seededWrites, "no negotiation policy was seeded for the demo merchant"

    policy = json.loads(seededWrites[key])
    assert policy["negotiationEnabled"] is True
    assert policy["merchantDid"] == seedCatalogModule.seedMerchantDid
    assert 0 < policy["marginFloorBps"] < 10000
    assert policy["createdAtTimestamp"] > 0


def testTheSeededPolicyValidatesAgainstTheRealModel(seededWrites: Dict[str, str]) -> None:
    """NegotiationPolicy is extra="forbid", so a stray or missing key would 422 the GET route."""
    from razoragentMesh.packages.merchantApi.src.schemas.policySchema import NegotiationPolicy

    key = f"mesh:merchant:policy:{seedCatalogModule.seedMerchantDid}"
    parsed = NegotiationPolicy.model_validate_json(seededWrites[key])
    assert parsed.negotiationEnabled is True
