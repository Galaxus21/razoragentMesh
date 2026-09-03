"""Layer 3 out-of-stock substitution search.

This is the route that makes the vector healer a running component rather than a library.

`packages/vectorHealer` was written, tested, and named in the README architecture diagram, in
GUIDE.md, and in the dashboard's `protocolLayerMap.ts` as the implementation of Layer 3 -- and
nothing constructed `OosInterceptor` outside its own tests. It was not even shipped: no
Dockerfile copied the package into an image, so the code could not have run in the mesh at all.

Why the search half lives here and the signing half does not
------------------------------------------------------------
`OosInterceptor.healOutOfStock` does two things: it finds a substitute (Qdrant ANN plus the
negative-constraint AST), and it patches the cart into a dual-signed AmendmentMandate. The second
needs a buyer signer AND a merchant signer. The Merchant API holds neither, and it should not:
the buyer key belongs to the agent, and handing it to a merchant service would make the mandate
chain meaningless.

So the split follows the key boundary. This route answers "what should replace SKU X, how close
is it, and how long did that take" -- no keys involved, via `OosInterceptor.findSubstitute`. The
MCP server, which does hold the merchant key, signs any amendment afterwards.

That split is also what makes the latency number honest: what is timed is the vector search and
the constraint filter, which is exactly what the "sub-300ms Qdrant ANN cosine similarity" claim
is about. Mandate signing is not in the measurement.
"""

import json
import logging
import time
from typing import Any, Dict, List, Optional

from fastapi import APIRouter, Depends
from pydantic import BaseModel, ConfigDict, Field

from ..constants.merchantConstants import redisCatalogHashKeyPrefix
from .dependencies import getRedisClient, getVectorizer
from .healingTelemetry import publishOosHealed

logger = logging.getLogger(__name__)

oosHealingRouter = APIRouter(prefix="/api/v1/catalog", tags=["oos-healing"])

millisecondsPerSecond: float = 1000.0

# Kept in step with packages/vectorHealer/src/constants/healerConstants.py.
defaultSimilarityFloor: float = 0.85
defaultMaxPriceDeltaPercent: float = 15.0

substitutionUnavailableReason: str = "vector_healer_unavailable"
noSubstituteReason: str = "no_qualifying_substitute"
unknownSkuReason: str = "failed_sku_not_in_catalog"

embeddingModeUnavailable: str = "unavailable"


class OosHealingRequest(BaseModel):
    """Asks for a replacement for a SKU that could not be reserved."""

    model_config = ConfigDict(frozen=True, extra="forbid")

    failedSkuId: str = Field(min_length=1, description="SKU whose reservation failed")
    requestedQuantity: int = Field(gt=0, description="Units the buyer still wants")
    similarityFloor: float = Field(default=defaultSimilarityFloor, ge=0.0, le=1.0)
    maxPriceDeltaPercent: float = Field(default=defaultMaxPriceDeltaPercent, ge=0.0)


class OosHealingResponse(BaseModel):
    """A substitution candidate, with the evidence for it."""

    model_config = ConfigDict(frozen=True, extra="forbid")

    healed: bool = Field(description="True when a qualifying substitute was found")
    failedSkuId: str
    substituteSkuId: Optional[str] = None
    substitutePayload: Optional[Dict[str, Any]] = None
    cosineScore: Optional[float] = None
    # Measured with time.perf_counter around the search. The dashboard has been showing a
    # hardcoded 214 from scripts/seedTelemetryStream.py; this is the real figure.
    healingDurationMs: float = Field(description="Measured wall time of the substitution search")
    # 'model' when a real embedding produced the vectors, 'hash' when fastembed was unavailable
    # and the provider fell back to character-hash pseudo-vectors. A score computed in 'hash'
    # mode is not a semantic similarity and must not be presented as one.
    embeddingMode: str = Field(description="Which producer made the vectors: model | hash")
    reason: Optional[str] = Field(default=None, description="Why no substitute, when healed=false")


@oosHealingRouter.post(
    "/heal-oos",
    response_model=OosHealingResponse,
    summary="Find a substitute for an out-of-stock SKU (Layer 3)",
)
async def healOutOfStockSku(
    request: OosHealingRequest,
    redis: Any = Depends(getRedisClient),
    vectorizer: Any = Depends(getVectorizer),
) -> OosHealingResponse:
    """Runs the Layer 3 substitution search and reports how long it actually took."""
    startedAt = time.perf_counter()

    interceptorClass, noSubstituteException, embeddingMode = _loadHealer()
    if interceptorClass is None:
        # Reported rather than raised: the mesh quotes, locks and settles without Layer 3, and a
        # 500 here would make an optional capability look like an outage.
        return _failure(
            request, startedAt, embeddingModeUnavailable, substitutionUnavailableReason
        )

    catalogStore = await _loadCatalogStore(redis)
    if not any(entry.get("skuId") == request.failedSkuId for entry in catalogStore):
        return _failure(request, startedAt, embeddingMode, unknownSkuReason)

    # The real Layer 3 class, constructed against the live Qdrant client the Merchant API
    # already builds for its auto-vectorizer.
    interceptor = interceptorClass(
        qdrantClient=getattr(vectorizer, "qdrantClient", None),
        catalogStore=catalogStore,
    )
    try:
        payload, cosineScore, durationMs = interceptor.findSubstitute(
            failedSkuId=request.failedSkuId,
            requestedQuantity=request.requestedQuantity,
            scoreThreshold=request.similarityFloor,
            maxPriceDeltaPct=request.maxPriceDeltaPercent,
        )
    except noSubstituteException:
        return _failure(request, startedAt, embeddingMode, noSubstituteReason)

    # Best-effort and not awaited: a heal that happened is worth reporting, but a telemetry
    # bus that is down must not turn a successful substitution into a failed request.
    publishOosHealed(
        failedSkuId=request.failedSkuId,
        substitutePayload=payload,
        cosineScore=cosineScore,
        healingDurationMs=durationMs,
        embeddingMode=embeddingMode,
    )

    return OosHealingResponse(
        healed=True,
        failedSkuId=request.failedSkuId,
        substituteSkuId=str(payload.get("skuId", "")),
        substitutePayload=payload,
        cosineScore=cosineScore,
        healingDurationMs=durationMs,
        embeddingMode=embeddingMode,
    )


def _loadHealer() -> tuple:
    """Imports the healer lazily so a missing package degrades this route, not the service."""
    try:
        from razoragentMesh.packages.vectorHealer.src.healerExceptions import (
            NoSubstituteFoundException,
        )
        from razoragentMesh.packages.vectorHealer.src.interception.oosInterceptor import (
            OosInterceptor,
        )
        from razoragentMesh.packages.vectorHealer.src.search.embeddingProvider import (
            EmbeddingProvider,
            embeddingModeHash,
            embeddingModeModel,
        )
    except ImportError as importError:
        logger.warning("Layer 3 substitution unavailable: %s", importError)
        return None, None, embeddingModeUnavailable

    # Probing the provider is how the mode is known before a search runs. A hash-mode result is
    # still returned, but stamped, so the dashboard never renders a character-hash score as a
    # semantic similarity.
    provider = EmbeddingProvider()
    provider._lazyInitFastEmbed()
    mode = embeddingModeModel if provider._fastembedModel is not None else embeddingModeHash
    return OosInterceptor, NoSubstituteFoundException, mode


async def _loadCatalogStore(redis: Any) -> List[Dict[str, Any]]:
    """Reads the catalog the healer searches over.

    OosInterceptor takes the catalog as a list because it needs the failed SKU's own vector and
    price to bound the query; Qdrant holds the candidate vectors, Redis holds the listings. Read
    from the same `mesh:catalog:*` keyspace the seeder writes and the MCP server hydrates from,
    so all three agree on what "the catalog" means.
    """
    try:
        keys = await _scanCatalogKeys(redis)
    except Exception as loadError:
        logger.warning("Could not enumerate catalog for substitution: %s", loadError)
        return []

    # One glob, four value shapes. redisCatalogHashKeyPrefix, redisCatalogKeyPrefix and
    # redisMerchantCatalogPrefix are all the identical string "mesh:catalog:", so this scan also
    # returns the `{merchantDid}:{skuId}` duplicate of a listing and the bare `:stock` integer.
    # json.loads("25") is a valid parse returning 25, so before this guard an int entered a list
    # of dicts and the caller's `entry.get("skuId")` raised AttributeError outside every try --
    # a hard 500 on every request, from the first merchant publish onwards.
    listings: List[Dict[str, Any]] = []
    seenSkuIds: set[str] = set()
    for key in keys:
        try:
            raw = await redis.get(key)
        except Exception:
            continue
        if not raw:
            continue
        rawText = raw.decode("utf-8") if isinstance(raw, bytes) else str(raw)
        try:
            parsed = json.loads(rawText)
        except json.JSONDecodeError:
            continue
        if not isinstance(parsed, dict):
            continue
        # Deduplicate by skuId: the `{merchantDid}:{skuId}` record is a legitimate dict holding
        # the same listing, so without this every merchant-published SKU is handed to
        # OosInterceptor twice, skewing both the candidate set and the price bound.
        skuId = parsed.get("skuId")
        if isinstance(skuId, str):
            if skuId in seenSkuIds:
                continue
            seenSkuIds.add(skuId)
        listings.append(parsed)
    return listings


async def _scanCatalogKeys(redis: Any) -> List[str]:
    """Enumerates catalog keys, tolerating both a real Redis and the in-memory test double."""
    if hasattr(redis, "scan_iter"):
        collected: List[str] = []
        async for key in redis.scan_iter(match=f"{redisCatalogHashKeyPrefix}*"):
            collected.append(key.decode("utf-8") if isinstance(key, bytes) else str(key))
        return collected
    if hasattr(redis, "keys"):
        found = await redis.keys(f"{redisCatalogHashKeyPrefix}*")
        return [k.decode("utf-8") if isinstance(k, bytes) else str(k) for k in found]
    # The in-process double exposes its map directly and implements neither scan nor keys.
    # catalogManager.deleteListing already reaches for `.store` the same way.
    if hasattr(redis, "store") and isinstance(redis.store, dict):
        return [
            key
            for key in redis.store
            if str(key).startswith(redisCatalogHashKeyPrefix)
        ]
    return []


def _failure(
    request: OosHealingRequest, startedAt: float, embeddingMode: str, reason: str
) -> OosHealingResponse:
    """Builds a healed=false response carrying the measured elapsed time and the reason."""
    return OosHealingResponse(
        healed=False,
        failedSkuId=request.failedSkuId,
        healingDurationMs=(time.perf_counter() - startedAt) * millisecondsPerSecond,
        embeddingMode=embeddingMode,
        reason=reason,
    )


__all__ = ["oosHealingRouter", "OosHealingRequest", "OosHealingResponse"]
