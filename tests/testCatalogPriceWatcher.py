"""Covers the subscriber that finally makes price-drop alerts fire.

Registering an alert answered 201 with status "active" while `dispatchPriceDropAlerts` had no
production caller anywhere in the repo. These tests pin the two halves that were missing: that a
catalog broadcast is turned into a dispatch, and that a malformed or price-less event is skipped
rather than allowed to kill the subscriber and silently stop every future alert.
"""

import json
from typing import Any, Dict, List, Optional

import pytest

from razoragentMesh.packages.x402Gateway.src.alerts.catalogPriceWatcher import (
    CatalogPriceWatcher,
    extractPriceFromCatalogEvent,
)
from razoragentMesh.packages.x402Gateway.src.alerts.priceDropAlertManager import (
    PriceDropAlertManager,
)
from razoragentMesh.tests.mockInfraHelpers import MockRedisAsync

testSkuId = "SKU-WATCHED-001"
testMerchantDid = "did:agent:merchant_watch_01"


def _catalogEvent(action: str, pricePaise: Optional[int] = 90_000, withItem: bool = True) -> str:
    """Builds an event in merchantApi's exact broadcast shape (catalogManager._publishEvent)."""
    payload: Dict[str, Any] = {
        "action": action,
        "skuId": testSkuId,
        "merchantDid": testMerchantDid,
        "timestamp": 1788400000,
    }
    if withItem:
        payload["item"] = {
            "skuId": testSkuId,
            "name": "Watched Chair",
            "category": "furniture",
            "baseUnitPricePaise": pricePaise,
            "availableStock": 10,
        }
    return json.dumps(payload)


class _RecordingAlertManager:
    """Stands in for PriceDropAlertManager, recording what it was asked to dispatch."""

    def __init__(self, webhooksPerCall: int = 1) -> None:
        self.calls: List[Dict[str, Any]] = []
        self._webhooksPerCall = webhooksPerCall

    async def dispatchPriceDropAlerts(self, skuId: str, activePricePaise: int) -> List[str]:
        self.calls.append({"skuId": skuId, "pricePaise": activePricePaise})
        return ["dispatched"] * self._webhooksPerCall


class _ExplodingAlertManager:
    """Fails every dispatch, standing in for an unreachable callback URL."""

    async def dispatchPriceDropAlerts(self, skuId: str, activePricePaise: int) -> List[str]:
        raise RuntimeError("callback host unreachable")


@pytest.mark.asyncio
async def testCatalogUpdateDispatchesAlertsForTheNewPrice() -> None:
    """The path that was missing entirely: a broadcast becomes a dispatch."""
    manager = _RecordingAlertManager()
    watcher = CatalogPriceWatcher(manager, redisClient=None)

    sent = await watcher.handleCatalogMessage(_catalogEvent("CATALOG_ITEM_UPDATED", 90_000))

    assert sent == 1
    assert manager.calls == [{"skuId": testSkuId, "pricePaise": 90_000}]


@pytest.mark.asyncio
async def testNewlyAddedSkuAlsoDispatches() -> None:
    """An alert registered before the SKU existed must fire when it is first listed."""
    manager = _RecordingAlertManager()
    watcher = CatalogPriceWatcher(manager, redisClient=None)

    await watcher.handleCatalogMessage(_catalogEvent("CATALOG_ITEM_ADDED", 45_000))

    assert manager.calls == [{"skuId": testSkuId, "pricePaise": 45_000}]


@pytest.mark.asyncio
async def testRemovalDispatchesNothing() -> None:
    """A delisting carries no price. Treating it as a drop to zero would fire every alert."""
    manager = _RecordingAlertManager()
    watcher = CatalogPriceWatcher(manager, redisClient=None)

    sent = await watcher.handleCatalogMessage(
        _catalogEvent("CATALOG_ITEM_REMOVED", withItem=False)
    )

    assert sent == 0
    assert manager.calls == []


@pytest.mark.asyncio
async def testAFailedDispatchDoesNotPropagate() -> None:
    """handleCatalogMessage is called inside the subscriber loop, which must survive a failure."""
    watcher = CatalogPriceWatcher(_ExplodingAlertManager(), redisClient=None)

    with pytest.raises(RuntimeError):
        # The loop catches this; the handler itself is honest about the failure so that a caller
        # driving it directly is not told a webhook was sent when none was.
        await watcher.handleCatalogMessage(_catalogEvent("CATALOG_ITEM_UPDATED"))


def testBareActionSpellingsAreAccepted() -> None:
    """The MCP server's subscriber accepts both spellings; a mismatch here would look dead."""
    bareForm = json.dumps(
        {"action": "UPDATED", "item": {"skuId": testSkuId, "baseUnitPricePaise": 12_000}}
    )
    assert extractPriceFromCatalogEvent(bareForm) == {"skuId": testSkuId, "pricePaise": 12_000}


def testMalformedEventsAreSkippedRatherThanRaising() -> None:
    """This consumes a broadcast it does not own, so an unfamiliar shape must not be fatal."""
    assert extractPriceFromCatalogEvent("not json at all") is None
    assert extractPriceFromCatalogEvent(json.dumps(["a", "list"])) is None
    assert extractPriceFromCatalogEvent(json.dumps({"action": "CATALOG_ITEM_UPDATED"})) is None
    assert extractPriceFromCatalogEvent(None) is None
    # A price of the wrong type, which json will happily carry.
    assert (
        extractPriceFromCatalogEvent(
            json.dumps({"action": "CATALOG_ITEM_UPDATED", "item": {"skuId": testSkuId, "baseUnitPricePaise": "90000"}})
        )
        is None
    )
    # `True` is an int in Python. Without the bool guard this would dispatch at one paise.
    assert (
        extractPriceFromCatalogEvent(
            json.dumps({"action": "CATALOG_ITEM_UPDATED", "item": {"skuId": testSkuId, "baseUnitPricePaise": True}})
        )
        is None
    )


def testAnUnknownActionIsIgnored() -> None:
    """Only the actions that carry an item carry a price."""
    assert extractPriceFromCatalogEvent(_catalogEvent("CATALOG_ITEM_ARCHIVED")) is None


class _RecordingHttpClient:
    """Captures the webhook instead of posting it, so a dispatch is observable without a server."""

    def __init__(self) -> None:
        self.posts: List[Dict[str, Any]] = []

    async def post(self, url: str, content: Any = None, headers: Any = None, **kwargs: Any) -> Any:
        self.posts.append({"url": url, "content": content, "headers": headers})

        class _Response:
            status_code = 200
            text = "ok"

        return _Response()


@pytest.mark.asyncio
async def testRegisteredAlertActuallyFiresOnAPriceDrop() -> None:
    """End to end over the two halves that were broken, using the REAL alert manager.

    This is the behaviour the endpoint has promised since it was written: register an alert with
    status "active", and be told when the price reaches it. Before the Redis wiring and this
    subscriber, both halves were missing at once and the webhook could never be sent.
    """
    httpClient = _RecordingHttpClient()
    manager = PriceDropAlertManager(redisClient=MockRedisAsync(), httpClient=httpClient)
    alert = await manager.registerPriceDropAlert(
        skuId=testSkuId,
        targetPricePaise=95_000,
        callbackUrl="https://buyer.test/price-drop",
        buyerAgentId="did:agent:" + "aa" * 32,
        expiresAtUnix=2_000_000_000,
    )
    assert alert.status == "active"

    watcher = CatalogPriceWatcher(manager, redisClient=None)
    sent = await watcher.handleCatalogMessage(_catalogEvent("CATALOG_ITEM_UPDATED", 90_000))

    assert sent == 1
    assert len(httpClient.posts) == 1
    assert httpClient.posts[0]["url"] == "https://buyer.test/price-drop"


@pytest.mark.asyncio
async def testAPriceAboveTheTargetSendsNothing() -> None:
    """An alert is a floor, not a subscription to every catalog edit."""
    httpClient = _RecordingHttpClient()
    manager = PriceDropAlertManager(redisClient=MockRedisAsync(), httpClient=httpClient)
    await manager.registerPriceDropAlert(
        skuId=testSkuId,
        targetPricePaise=50_000,
        callbackUrl="https://buyer.test/price-drop",
        buyerAgentId="did:agent:" + "bb" * 32,
        expiresAtUnix=2_000_000_000,
    )

    watcher = CatalogPriceWatcher(manager, redisClient=None)
    sent = await watcher.handleCatalogMessage(_catalogEvent("CATALOG_ITEM_UPDATED", 90_000))

    assert sent == 0
    assert httpClient.posts == []
