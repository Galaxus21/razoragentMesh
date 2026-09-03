"""Covers merchant opt-in and merchant-side price authority on the x402-INR negotiate route.

Before this, `POST /api/v1/mesh/negotiate` accepted `sellerAskPaise` and `merchantDid` from the
buyer's own request body and checked only that neither moved the wrong way relative to a previous
turn in the same session -- which is vacuous on turn one. Measured against the running stack on
2026-09-03: a buyer declared the seller's ask at 1 paise on a SKU listed at 420000 paise,
converged on the first turn, and was handed a compiled, hashed contract AST naming the merchant at
that price. There was no merchant-side agent, and nothing stood in for one.

Two properties are pinned here, and both are things a demo audience will try:

  1. Negotiation is OPT-IN. Absent a listing, absent a policy, or a policy with the switch off,
     the route refuses and the buyer's escrow is not touched.
  2. When it is on, the price band and the merchant's identity come from merchant-written records,
     never from the request body.
"""

import json
from typing import Any, Dict, Optional, Tuple

import pytest
from httpx import ASGITransport, AsyncClient

from razoragentMesh.packages.x402Gateway.src.constants.negotiationConstants import (
    headerEscrowToken,
    headerPowChallenge,
    headerPowSolution,
    microFeePerTurnPaise,
)
from razoragentMesh.packages.x402Gateway.src.gatewayApp import createGatewayApp
from razoragentMesh.packages.x402Gateway.src.middleware.proofOfWorkMiddleware import (
    solvePoWChallenge,
)
from razoragentMesh.packages.x402Gateway.src.negotiation.merchantTerms import (
    MerchantNegotiationTerms,
    clampSellerAskPaise,
    computeFloorPricePaise,
    resolveMerchantNegotiationTerms,
)
from razoragentMesh.packages.x402Gateway.src.routes.negotiateRoute import activeNegotiators
from razoragentMesh.tests.mockInfraHelpers import MockRedisAsync, seedNegotiableMerchant

testSkuId: str = "SKU-OPTIN-CHAIR-001"
testMerchantDid: str = "did:agent:merchant_optin_01"
testListPricePaise: int = 420_000
# 420000 * (10000 - 1000) / 10000. The merchant's stated worst acceptable price.
testFloorPricePaise: int = 378_000
testEscrowHoldPaise: int = 10_000


def _buildApp(redisClient: Optional[Any]) -> Any:
    """A gateway whose only view of the world is the Redis contents a test seeds."""
    app = createGatewayApp()
    app.state.redis = redisClient
    return app


async def _openEscrow(client: AsyncClient, buyerDid: str) -> str:
    response = await client.post(
        "/api/v1/mesh/escrow",
        json={"buyerAgentDid": buyerDid, "initialHoldPaise": testEscrowHoldPaise},
    )
    assert response.status_code == 201, response.text
    return response.json()["sessionToken"]


async def _solvedHeaders(client: AsyncClient, escrowToken: str) -> Dict[str, str]:
    """A fresh PoW challenge and its solution. Each turn needs its own; they are single-use."""
    response = await client.get("/api/v1/mesh/challenge")
    assert response.status_code == 200
    body = response.json()
    nonce = solvePoWChallenge(body["challengeToken"], body["powDifficultyZeros"])
    return {
        headerPowChallenge: body["challengeToken"],
        headerPowSolution: str(nonce),
        headerEscrowToken: escrowToken,
    }


async def _negotiate(
    client: AsyncClient,
    escrowToken: str,
    buyerDid: str,
    buyerBidPaise: int,
    sellerAskPaise: int,
    turnNumber: int = 1,
    merchantDid: str = testMerchantDid,
    skuId: str = testSkuId,
) -> Any:
    headers = await _solvedHeaders(client, escrowToken)
    return await client.post(
        "/api/v1/mesh/negotiate",
        json={
            "skuId": skuId,
            "quantity": 1,
            "turnNumber": turnNumber,
            "buyerBidPaise": buyerBidPaise,
            "sellerAskPaise": sellerAskPaise,
            "buyerAgentDid": buyerDid,
            "merchantDid": merchantDid,
        },
        headers=headers,
    )


async def _release(client: AsyncClient, escrowToken: str) -> Tuple[int, int]:
    response = await client.post(
        "/api/v1/mesh/escrow/release", headers={headerEscrowToken: escrowToken}
    )
    assert response.status_code == 200, response.text
    body = response.json()
    return body["totalDebitedPaise"], body["refundedBalancePaise"]


@pytest.fixture(autouse=True)
def _isolateNegotiatorState() -> Any:
    """`activeNegotiators` is a process-local dict keyed by buyer+SKU, so it leaks across tests."""
    activeNegotiators.clear()
    yield
    activeNegotiators.clear()


# --------------------------------------------------------------------------------------------
# Opt-in
# --------------------------------------------------------------------------------------------


@pytest.mark.asyncio
async def testMerchantWithNoPolicyRefusesToNegotiate() -> None:
    """The default. A merchant who has configured nothing sells at their listed price."""
    redis = MockRedisAsync()
    await redis.set(
        f"mesh:catalog:{testSkuId}",
        json.dumps(
            {
                "skuId": testSkuId,
                "merchantDid": testMerchantDid,
                "baseUnitPricePaise": testListPricePaise,
            }
        ),
    )
    transport = ASGITransport(app=_buildApp(redis))
    async with AsyncClient(transport=transport, base_url="http://testserver") as client:
        buyerDid = "did:agent:buyer_no_policy"
        escrowToken = await _openEscrow(client, buyerDid)

        response = await _negotiate(client, escrowToken, buyerDid, 400_000, 410_000)

        assert response.status_code == 403
        assert "not enabled negotiation" in response.json()["detail"]
        # The refusal is free. Charging the per-turn micro-fee for a negotiation the merchant
        # never agreed to hold would make probing merchants cost money.
        assert await _release(client, escrowToken) == (0, testEscrowHoldPaise)


@pytest.mark.asyncio
async def testPolicyWithNegotiationSwitchedOffRefuses() -> None:
    """A merchant may configure margins and turns and still decline to negotiate at all."""
    redis = MockRedisAsync()
    await seedNegotiableMerchant(
        redis,
        skuId=testSkuId,
        merchantDid=testMerchantDid,
        listPricePaise=testListPricePaise,
        negotiationEnabled=False,
    )
    transport = ASGITransport(app=_buildApp(redis))
    async with AsyncClient(transport=transport, base_url="http://testserver") as client:
        buyerDid = "did:agent:buyer_switched_off"
        escrowToken = await _openEscrow(client, buyerDid)

        response = await _negotiate(client, escrowToken, buyerDid, 400_000, 410_000)

        assert response.status_code == 403
        assert "switched off" in response.json()["detail"]
        assert await _release(client, escrowToken) == (0, testEscrowHoldPaise)


@pytest.mark.asyncio
async def testUnlistedSkuRefusesRatherThanInventingAPrice() -> None:
    """With no listing there is no list price and no owning merchant to bound the bargain."""
    redis = MockRedisAsync()
    transport = ASGITransport(app=_buildApp(redis))
    async with AsyncClient(transport=transport, base_url="http://testserver") as client:
        buyerDid = "did:agent:buyer_unlisted"
        escrowToken = await _openEscrow(client, buyerDid)

        response = await _negotiate(
            client, escrowToken, buyerDid, 1, 1, skuId="SKU-DOES-NOT-EXIST"
        )

        assert response.status_code == 403
        assert "not a listed SKU" in response.json()["detail"]


class _UnreachableRedis:
    """Every read raises, standing in for a Redis that is configured but down."""

    async def get(self, key: str) -> Any:
        raise ConnectionError("connection refused")


@pytest.mark.asyncio
async def testAnUnreachablePolicyStoreFailsClosedAndSaysSo() -> None:
    """An outage must not be reported as "this SKU is not listed" -- one is a retry, one is not."""
    transport = ASGITransport(app=_buildApp(_UnreachableRedis()))
    async with AsyncClient(transport=transport, base_url="http://testserver") as client:
        buyerDid = "did:agent:buyer_no_store"
        escrowToken = await _openEscrow(client, buyerDid)

        response = await _negotiate(client, escrowToken, buyerDid, 400_000, 410_000)

        assert response.status_code == 403
        assert "cannot reach its policy store" in response.json()["detail"]


@pytest.mark.asyncio
async def testMissingX402HeadersStillAnswer402BeforeThePolicyCheck() -> None:
    """The protocol's own gate stays first, so an unpaid caller is told what it is missing."""
    redis = MockRedisAsync()
    await seedNegotiableMerchant(
        redis, testSkuId, testMerchantDid, testListPricePaise, negotiationEnabled=False
    )
    transport = ASGITransport(app=_buildApp(redis))
    async with AsyncClient(transport=transport, base_url="http://testserver") as client:
        response = await client.post(
            "/api/v1/mesh/negotiate",
            json={
                "skuId": testSkuId,
                "quantity": 1,
                "turnNumber": 1,
                "buyerBidPaise": 400_000,
                "sellerAskPaise": 410_000,
                "buyerAgentDid": "did:agent:buyer_unpaid",
            },
        )
        assert response.status_code == 402


# --------------------------------------------------------------------------------------------
# Merchant-side price authority
# --------------------------------------------------------------------------------------------


@pytest.mark.asyncio
async def testBuyerCannotDeclareTheSellersAskAtOnePaise() -> None:
    """The exact forgery measured live on 2026-09-03, now bounded by the merchant's floor.

    The buyer still proposes an ask -- that is what a negotiating party does -- but the ask that
    is recorded, that convergence is tested against, and that any contract is compiled at, is the
    merchant's.
    """
    redis = MockRedisAsync()
    await seedNegotiableMerchant(redis, testSkuId, testMerchantDid, testListPricePaise)
    transport = ASGITransport(app=_buildApp(redis))
    async with AsyncClient(transport=transport, base_url="http://testserver") as client:
        buyerDid = "did:agent:buyer_forger"
        escrowToken = await _openEscrow(client, buyerDid)

        response = await _negotiate(client, escrowToken, buyerDid, 1, 1)

        assert response.status_code == 200, response.text
        body = response.json()
        assert body["stepResult"]["sellerAskPaise"] == testFloorPricePaise
        # A one-paise bid is nowhere near the floor, so nothing is agreed and no contract exists.
        assert body["stepResult"]["isConverged"] is False
        assert body["contractAst"] is None
        assert body["contractAstHash"] is None


@pytest.mark.asyncio
async def testAConvergedContractIsCompiledAtTheMerchantsPriceNotTheBuyersClaim() -> None:
    """Convergence is still possible -- it just happens at a price the merchant's policy allows."""
    redis = MockRedisAsync()
    await seedNegotiableMerchant(redis, testSkuId, testMerchantDid, testListPricePaise)
    transport = ASGITransport(app=_buildApp(redis))
    async with AsyncClient(transport=transport, base_url="http://testserver") as client:
        buyerDid = "did:agent:buyer_crossing"
        escrowToken = await _openEscrow(client, buyerDid)

        response = await _negotiate(client, escrowToken, buyerDid, 380_000, 1)

        assert response.status_code == 200, response.text
        body = response.json()
        assert body["stepResult"]["isConverged"] is True
        assert body["contractAst"]["agreedUnitPricePaise"] == testFloorPricePaise
        assert body["contractAst"]["agreedUnitPricePaise"] != 1


@pytest.mark.asyncio
async def testTheContractNamesTheMerchantWhoOwnsTheListing() -> None:
    """`merchantDid` in the body is buyer-supplied, so honouring it lets a buyer pick the victim."""
    redis = MockRedisAsync()
    await seedNegotiableMerchant(redis, testSkuId, testMerchantDid, testListPricePaise)
    transport = ASGITransport(app=_buildApp(redis))
    async with AsyncClient(transport=transport, base_url="http://testserver") as client:
        buyerDid = "did:agent:buyer_impersonator"
        escrowToken = await _openEscrow(client, buyerDid)

        response = await _negotiate(
            client,
            escrowToken,
            buyerDid,
            420_000,
            420_000,
            merchantDid="did:agent:some_other_merchant",
        )

        assert response.status_code == 200, response.text
        ast = response.json()["contractAst"]
        assert ast is not None
        assert ast["merchantDid"] == testMerchantDid


@pytest.mark.asyncio
async def testAskIsHeldAtOrBelowTheListPrice() -> None:
    """A merchant does not sell above their own listed price because a buyer offered more."""
    redis = MockRedisAsync()
    await seedNegotiableMerchant(redis, testSkuId, testMerchantDid, testListPricePaise)
    transport = ASGITransport(app=_buildApp(redis))
    async with AsyncClient(transport=transport, base_url="http://testserver") as client:
        buyerDid = "did:agent:buyer_overpaying"
        escrowToken = await _openEscrow(client, buyerDid)

        response = await _negotiate(client, escrowToken, buyerDid, 900_000, 900_000)

        assert response.status_code == 200, response.text
        assert response.json()["stepResult"]["sellerAskPaise"] == testListPricePaise


@pytest.mark.asyncio
async def testAMerchantCanShortenTheNegotiation() -> None:
    """maxNegotiationTurns was stored and never consulted; a turn past it is now refused."""
    redis = MockRedisAsync()
    await seedNegotiableMerchant(
        redis, testSkuId, testMerchantDid, testListPricePaise, maxNegotiationTurns=2
    )
    transport = ASGITransport(app=_buildApp(redis))
    async with AsyncClient(transport=transport, base_url="http://testserver") as client:
        buyerDid = "did:agent:buyer_persistent"
        escrowToken = await _openEscrow(client, buyerDid)

        first = await _negotiate(client, escrowToken, buyerDid, 100_000, 420_000, turnNumber=1)
        assert first.status_code == 200, first.text

        third = await _negotiate(client, escrowToken, buyerDid, 200_000, 400_000, turnNumber=3)
        assert third.status_code == 409
        assert "2 negotiation turns" in third.json()["detail"]

        # Turn 1 was held and charged; the refused turn 3 was not.
        assert await _release(client, escrowToken) == (
            microFeePerTurnPaise,
            testEscrowHoldPaise - microFeePerTurnPaise,
        )


# --------------------------------------------------------------------------------------------
# The resolver itself
# --------------------------------------------------------------------------------------------


def testFloorIsADiscountOffTheMerchantsOwnListPrice() -> None:
    """Integer paise, floor-divided, so it never rounds past what the merchant agreed to."""
    assert computeFloorPricePaise(420_000, 1000) == 378_000
    assert computeFloorPricePaise(420_000, 0) == 420_000
    assert computeFloorPricePaise(420_000, 10_000) == 0
    # 99999 * 9999 // 10000 rounds down, toward the merchant.
    assert computeFloorPricePaise(99_999, 1) == 99_989
    assert computeFloorPricePaise(0, 1000) == 0


def testClampIsInertWhenTheBandIsUnknown() -> None:
    """A refusal carries no band, so nothing downstream can silently clamp against None."""
    terms = MerchantNegotiationTerms(negotiationEnabled=False, refusalReason="nope")
    assert clampSellerAskPaise(1, terms) == 1


@pytest.mark.asyncio
async def testResolverReadsTheBandFromMerchantWrittenRecords() -> None:
    redis = MockRedisAsync()
    await seedNegotiableMerchant(
        redis, testSkuId, testMerchantDid, testListPricePaise, marginFloorBps=1500
    )

    terms = await resolveMerchantNegotiationTerms(testSkuId, redis)

    assert terms.negotiationEnabled is True
    assert terms.merchantDid == testMerchantDid
    assert terms.listPricePaise == testListPricePaise
    assert terms.floorPricePaise == 357_000
    assert terms.refusalReason is None


@pytest.mark.asyncio
async def testAMerchantCannotBuyMoreTurnsThanTheProtocolAllows() -> None:
    """The policy's ceiling is 10, the protocol's escrow and turn accounting are sized for 5."""
    redis = MockRedisAsync()
    await seedNegotiableMerchant(
        redis, testSkuId, testMerchantDid, testListPricePaise, maxNegotiationTurns=10
    )

    terms = await resolveMerchantNegotiationTerms(testSkuId, redis)

    assert terms.maxTurns == 5


@pytest.mark.asyncio
async def testAMalformedListingOrPolicyIsTreatedAsNoConsent() -> None:
    """This reads records another service writes, so an unfamiliar shape must not open the gate."""
    redis = MockRedisAsync()

    await redis.set(f"mesh:catalog:{testSkuId}", "not json at all")
    assert (await resolveMerchantNegotiationTerms(testSkuId, redis)).negotiationEnabled is False

    # A stock key: a bare integer under the same `mesh:catalog:` prefix. Parsing succeeds and
    # yields an int, which is exactly the collision that used to 500 the OOS healer.
    await redis.set(f"mesh:catalog:{testSkuId}", "25")
    assert (await resolveMerchantNegotiationTerms(testSkuId, redis)).negotiationEnabled is False

    # `True` is an int in Python; without the bool guard this would list at one paise.
    await redis.set(
        f"mesh:catalog:{testSkuId}",
        json.dumps({"skuId": testSkuId, "merchantDid": testMerchantDid, "baseUnitPricePaise": True}),
    )
    terms = await resolveMerchantNegotiationTerms(testSkuId, redis)
    assert terms.negotiationEnabled is False
    assert "no usable list price" in (terms.refusalReason or "")
