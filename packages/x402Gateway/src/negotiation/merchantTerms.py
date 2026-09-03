"""Resolves the terms the MERCHANT sets for a negotiation, from data only the merchant writes.

Why this exists: there is no merchant-side agent in this mesh, and until now nothing stood in
for one. `POST /api/v1/mesh/negotiate` took `sellerAskPaise` straight from the buyer's request
body, so the buyer played both roles: it proposed its own bid, proposed the seller's ask, and the
route checked only that neither moved the wrong way *relative to a previous turn in the same
session* -- which is vacuous on turn one. Verified against the running stack on 2026-09-03: a
buyer declared the seller's ask at 1 paise on a SKU listed at 420000 paise, converged
immediately, and received a compiled, hashed contract AST naming the merchant at that price.

The merchant's agent is their POLICY. The merchant writes two things and nothing else can forge
either: the SKU listing (which carries the list price and the owning merchantDid) and the
negotiation policy at `mesh:merchant:policy:{did}`. This module reads both and returns the band
the seller's ask must stay inside. The route then clamps to that band instead of believing the
buyer.

`merchantDid` deliberately comes from the LISTING, not from the request payload. The payload
field is buyer-supplied and optional, so honouring it would let a buyer point at whichever
merchant's policy suited them.
"""

import json
import logging
from typing import Any, Optional

from pydantic import BaseModel, ConfigDict, Field

from ..constants.negotiationConstants import basisPointsDivisor, maxNegotiationTurns

logger = logging.getLogger(__name__)

# Written by merchantApi's catalogManager (`redisCatalogHashKeyPrefix`) and policyRoute
# (`redisMerchantPolicyKeyPrefix`). Duplicated as literals because the gateway is a separate
# service and does not import merchantApi; a divergence here reads as "no merchant has opted in".
redisCatalogKeyPrefix: str = "mesh:catalog:"
redisMerchantPolicyKeyPrefix: str = "mesh:merchant:policy:"


class MerchantNegotiationTerms(BaseModel):
    """The band and turn budget the merchant's policy imposes on one negotiation."""

    model_config = ConfigDict(frozen=True, extra="forbid")

    negotiationEnabled: bool
    merchantDid: Optional[str] = None
    listPricePaise: Optional[int] = Field(default=None, ge=0)
    floorPricePaise: Optional[int] = Field(default=None, ge=0)
    maxTurns: int = Field(default=maxNegotiationTurns, ge=1)
    autoAcceptSpreadPaise: int = Field(default=0, ge=0)
    # Why negotiation is unavailable, phrased for the buyer agent that will read it. None when
    # it is available.
    refusalReason: Optional[str] = None


def clampSellerAskPaise(proposedAskPaise: int, terms: MerchantNegotiationTerms) -> int:
    """Holds the seller's ask inside the merchant's band.

    Clamped rather than rejected: a buyer proposing a price is not misbehaving, it is
    negotiating. What it may not do is decide the answer. The clamped value is what the route
    records and returns, so the buyer learns the merchant's real position from the step result
    instead of being told only that it was refused.
    """
    if terms.floorPricePaise is None or terms.listPricePaise is None:
        return proposedAskPaise
    bounded = max(proposedAskPaise, terms.floorPricePaise)
    return min(bounded, terms.listPricePaise)


def computeFloorPricePaise(listPricePaise: int, marginFloorBps: int) -> int:
    """The lowest unit price the merchant will accept, as a discount off their own list price.

    Integer paise throughout, floor-divided, so the result is never a fraction and never rounds
    in the buyer's favour past the merchant's stated margin.
    """
    if listPricePaise <= 0:
        return 0
    marginFloorBps = max(0, min(marginFloorBps, basisPointsDivisor))
    return (listPricePaise * (basisPointsDivisor - marginFloorBps)) // basisPointsDivisor


class _PolicyStoreUnavailable(RuntimeError):
    """Raised when the store could not be read at all, as opposed to holding nothing.

    These are different answers and the buyer agent needs to be able to tell them apart: "this
    merchant does not negotiate" is final, while "the gateway could not check" is a retry. Folding
    the second into the first is how an outage comes to be reported as an unlisted SKU.
    """


async def _readJsonKey(redisClient: Any, key: str) -> Optional[dict]:
    """Reads one JSON document. Absent and unparseable both read as None; a failed read raises."""
    if redisClient is None:
        raise _PolicyStoreUnavailable("no Redis client")
    try:
        raw = await redisClient.get(key)
    except Exception as err:
        logger.warning("Redis read failed for %s: %s", key, err)
        raise _PolicyStoreUnavailable(str(err)) from err
    if not raw:
        return None
    try:
        parsed = json.loads(raw) if isinstance(raw, (str, bytes)) else raw
    except (ValueError, TypeError):
        return None
    return parsed if isinstance(parsed, dict) else None


async def resolveMerchantNegotiationTerms(
    skuId: str,
    redisClient: Any,
) -> MerchantNegotiationTerms:
    """Looks up whether this SKU's merchant negotiates, and inside what band.

    Fails CLOSED at every step. Opt-in means a merchant who has configured nothing is not
    negotiating, so an unreachable store, a missing listing and an absent policy all refuse -- but
    each says which it was, because "the merchant does not negotiate" is final and "the gateway
    could not check" is worth retrying, and an agent deciding what to do next needs to tell them
    apart.
    """
    try:
        listing = await _readJsonKey(redisClient, f"{redisCatalogKeyPrefix}{skuId}")
    except _PolicyStoreUnavailable:
        return MerchantNegotiationTerms(
            negotiationEnabled=False,
            refusalReason=(
                "Negotiation is unavailable: this gateway cannot reach its policy store, so it "
                "cannot confirm the merchant opted in. Buy at the listed price instead."
            ),
        )
    if listing is None:
        return MerchantNegotiationTerms(
            negotiationEnabled=False,
            refusalReason=(
                f"Negotiation is unavailable: '{skuId}' is not a listed SKU, so there is no "
                "merchant policy or list price to negotiate against."
            ),
        )

    merchantDid = listing.get("merchantDid")
    listPricePaise = listing.get("baseUnitPricePaise")
    if not isinstance(merchantDid, str) or not merchantDid:
        return MerchantNegotiationTerms(
            negotiationEnabled=False,
            refusalReason=f"Negotiation is unavailable: '{skuId}' names no owning merchant.",
        )
    if not isinstance(listPricePaise, int) or isinstance(listPricePaise, bool) or listPricePaise <= 0:
        return MerchantNegotiationTerms(
            negotiationEnabled=False,
            merchantDid=merchantDid,
            refusalReason=f"Negotiation is unavailable: '{skuId}' has no usable list price.",
        )

    try:
        policy = await _readJsonKey(redisClient, f"{redisMerchantPolicyKeyPrefix}{merchantDid}")
    except _PolicyStoreUnavailable:
        policy = None
    if policy is None:
        return MerchantNegotiationTerms(
            negotiationEnabled=False,
            merchantDid=merchantDid,
            listPricePaise=listPricePaise,
            refusalReason=(
                "This merchant has not enabled negotiation. Their listed price is firm -- call "
                "get_live_sku_quote and buy at it."
            ),
        )
    if not bool(policy.get("negotiationEnabled", False)):
        return MerchantNegotiationTerms(
            negotiationEnabled=False,
            merchantDid=merchantDid,
            listPricePaise=listPricePaise,
            refusalReason=(
                "This merchant has negotiation switched off. Their listed price is firm -- call "
                "get_live_sku_quote and buy at it."
            ),
        )

    marginFloorBps = policy.get("marginFloorBps", 0)
    if not isinstance(marginFloorBps, int) or isinstance(marginFloorBps, bool):
        marginFloorBps = 0
    policyTurns = policy.get("maxNegotiationTurns", maxNegotiationTurns)
    if not isinstance(policyTurns, int) or isinstance(policyTurns, bool) or policyTurns < 1:
        policyTurns = maxNegotiationTurns
    autoAccept = policy.get("autoAcceptSpreadPaise", 0)
    if not isinstance(autoAccept, int) or isinstance(autoAccept, bool) or autoAccept < 0:
        autoAccept = 0

    return MerchantNegotiationTerms(
        negotiationEnabled=True,
        merchantDid=merchantDid,
        listPricePaise=listPricePaise,
        floorPricePaise=computeFloorPricePaise(listPricePaise, marginFloorBps),
        # The gateway's own ceiling still applies: a merchant may shorten the negotiation but
        # not extend it past what the protocol's escrow and turn accounting are sized for.
        maxTurns=min(policyTurns, maxNegotiationTurns),
        autoAcceptSpreadPaise=autoAccept,
    )


__all__ = [
    "MerchantNegotiationTerms",
    "clampSellerAskPaise",
    "computeFloorPricePaise",
    "redisCatalogKeyPrefix",
    "redisMerchantPolicyKeyPrefix",
    "resolveMerchantNegotiationTerms",
]
