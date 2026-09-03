"""Covers merchant-authored offers on the listing schema and the catalog broadcast.

A quote stacks four discount types and only one of them was ever the merchant's. Volume tiers
came from the listing; the campaign percentage, the UPI cashback and the promo code were global
constants in the MCP server -- the same 10% festive discount, the same cashback and the same
CORP_5PCT code on every SKU in the mesh, unwritable by any merchant and impossible to switch off.

Two things are pinned here. First that the schema accepts a merchant's own offers and refuses the
shapes the pricing engine could not act on. Second that `upsertSku` puts them on the pub/sub
broadcast -- the MCP server's catalogStore FULL-REPLACES a SKU from that payload, so a field
omitted from the broadcast is a field the live catalog loses on the merchant's next edit, quietly
and only until someone notices the discount stopped applying. That is exactly how scheduled
promotions were being erased before commit b1256e9.
"""

import json
from typing import Any, Dict

import pytest
from pydantic import ValidationError

from razoragentMesh.packages.merchantApi.src.catalog.catalogManager import CatalogManager
from razoragentMesh.packages.merchantApi.src.schemas.universalProductSchema import (
    MerchantAuthoredOffers,
    UniversalProductListing,
)
from razoragentMesh.tests.mockInfraHelpers import MockRedisAsync

testSkuId: str = "SKU-OFFERS-001"
testMerchantDid: str = "did:agent:merchant_offers_01"


def buildListing(**overrides: Any) -> UniversalProductListing:
    payload: Dict[str, Any] = {
        "skuId": testSkuId,
        "merchantDid": testMerchantDid,
        "title": "Ergonomic Chair With Offers",
        "description": "A chair carrying the merchant's own campaign and codes.",
        "category": "furniture",
        "hsnCode": "9401",
        "gstRatePercent": 18,
        "baseUnitPricePaise": 100_000,
        "availableStock": 25,
        "originPincode": "560001",
    }
    payload.update(overrides)
    return UniversalProductListing(**payload)


class _RecordingRedis(MockRedisAsync):
    """MockRedisAsync plus the publish() catalogManager calls, so the broadcast is observable."""

    def __init__(self) -> None:
        super().__init__()
        self.published: list[tuple[str, str]] = []

    async def publish(self, channel: str, message: str) -> int:
        self.published.append((channel, message))
        return 1


def testAListingNeedsNoOffersAndKeepsTheMeshDefaults() -> None:
    """The compatibility guarantee: every listing published before this field existed lands here."""
    listing = buildListing()
    assert listing.merchantOffers is None


def testAMerchantCanAuthorACampaignCashbackAndCodes() -> None:
    listing = buildListing(
        merchantOffers={
            "campaign": {"label": "Monsoon Clearance", "discountBps": 2000, "capPaise": 15_000},
            "paymentRailCashbackPaise": 250,
            "promoCodes": [{"code": "MONSOON15", "discountBps": 1500, "label": "Monsoon Code"}],
        }
    )

    offers = listing.merchantOffers
    assert offers is not None
    assert offers.campaign is not None
    assert offers.campaign.discountBps == 2000
    assert offers.campaign.capPaise == 15_000
    assert offers.paymentRailCashbackPaise == 250
    assert offers.promoCodes[0].code == "MONSOON15"


def testAnEmptyOffersObjectMeansNoOffersRatherThanDefaults() -> None:
    """Presence is the statement. This is how a merchant says "my price is my price"."""
    offers = MerchantAuthoredOffers()
    assert offers.campaign is None
    assert offers.paymentRailCashbackPaise is None
    assert offers.promoCodes == []


def testAnUncappedCampaignIsDistinctFromACapOfZero() -> None:
    """A cap of 0 discounts nothing; no cap discounts the full percentage. Not interchangeable."""
    uncapped = MerchantAuthoredOffers(campaign={"discountBps": 2000})
    assert uncapped.campaign is not None and uncapped.campaign.capPaise is None

    cappedAtZero = MerchantAuthoredOffers(campaign={"discountBps": 2000, "capPaise": 0})
    assert cappedAtZero.campaign is not None and cappedAtZero.campaign.capPaise == 0


def testDuplicatePromoCodesAreRefused() -> None:
    """The second row would be unreachable, so the form would look broken rather than wrong."""
    with pytest.raises(ValidationError, match="distinct"):
        MerchantAuthoredOffers(
            promoCodes=[
                {"code": "SAVE10", "discountBps": 1000},
                {"code": "save10", "discountBps": 1200},
            ]
        )


def testDiscountBoundsAndUnknownKeysAreRefused() -> None:
    with pytest.raises(ValidationError):
        MerchantAuthoredOffers(campaign={"discountBps": 10_001})
    with pytest.raises(ValidationError):
        MerchantAuthoredOffers(campaign={"discountBps": -1})
    with pytest.raises(ValidationError):
        MerchantAuthoredOffers(paymentRailCashbackPaise=-1)
    # extra="forbid": a stray key is a 422 the merchant sees as an opaque publish failure, so it
    # is worth knowing the model really does reject one.
    with pytest.raises(ValidationError):
        MerchantAuthoredOffers(campaign={"discountBps": 500, "discountPaise": 100})


def testTooManyPromoCodesAreRefused() -> None:
    with pytest.raises(ValidationError):
        MerchantAuthoredOffers(
            promoCodes=[{"code": f"CODE{idx}", "discountBps": 500} for idx in range(11)]
        )


@pytest.mark.asyncio
async def testUpsertBroadcastsTheAuthoredOffers() -> None:
    """The MCP server full-replaces a SKU from this payload, so an omitted field is a lost field."""
    redis = _RecordingRedis()
    manager = CatalogManager(redisClient=redis)

    await manager.upsertSku(
        buildListing(
            merchantOffers={
                "campaign": {"discountBps": 800, "capPaise": 4_000},
                "promoCodes": [{"code": "SAVE8", "discountBps": 800}],
            }
        )
    )

    assert len(redis.published) == 1
    event = json.loads(redis.published[0][1])
    offers = event["item"]["merchantOffers"]
    assert offers["campaign"]["discountBps"] == 800
    assert offers["campaign"]["capPaise"] == 4_000
    assert offers["promoCodes"][0]["code"] == "SAVE8"


@pytest.mark.asyncio
async def testUpsertBroadcastsNullForASkuWithNoOffers() -> None:
    """The key is always present, so the MCP subscriber can tell "none" from "not sent"."""
    redis = _RecordingRedis()
    manager = CatalogManager(redisClient=redis)

    await manager.upsertSku(buildListing())

    event = json.loads(redis.published[0][1])
    assert "merchantOffers" in event["item"]
    assert event["item"]["merchantOffers"] is None


@pytest.mark.asyncio
async def testAuthoredOffersSurviveAnEdit() -> None:
    """The failure mode this guards: a second publish quietly dropping the merchant's offers."""
    redis = _RecordingRedis()
    manager = CatalogManager(redisClient=redis)
    offers = {"campaign": {"discountBps": 800}, "promoCodes": [{"code": "SAVE8", "discountBps": 800}]}

    await manager.upsertSku(buildListing(merchantOffers=offers))
    await manager.upsertSku(buildListing(availableStock=10, merchantOffers=offers))

    stored = json.loads(await redis.get(f"mesh:catalog:{testSkuId}"))
    assert stored["merchantOffers"]["campaign"]["discountBps"] == 800
    secondEvent = json.loads(redis.published[1][1])
    assert secondEvent["action"] == "CATALOG_ITEM_UPDATED"
    assert secondEvent["item"]["merchantOffers"]["promoCodes"][0]["code"] == "SAVE8"
