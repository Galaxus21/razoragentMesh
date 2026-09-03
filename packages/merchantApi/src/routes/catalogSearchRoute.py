"""Natural-language catalog search over the product vector index.

Why this exists: the mesh had no discovery primitive. An agent could quote a SKU id it had
already been given, but nothing could answer "find me an office chair" -- VectorSearcher in
the healer package is substitution-shaped and requires an hsnCode and an originating price,
so it cannot serve an open query. This is the missing piece that lets a buyer agent find a
product a merchant just published.

It lives in merchantApi because fastembed and the Qdrant client already do; the MCP server is
TypeScript and has no embedder.
"""

import logging
from typing import Any, List, Optional

from fastapi import APIRouter, Depends
from pydantic import BaseModel, ConfigDict, Field

from ..constants.merchantConstants import (
    defaultSearchLimit,
    embeddingModeHash,
    maxSearchLimit,
)
from .dependencies import getVectorizer

logger = logging.getLogger(__name__)

catalogSearchRouter = APIRouter(prefix="/api/v1/catalog", tags=["catalog-search"])


class CatalogSearchRequest(BaseModel):
    """A natural-language product query."""

    model_config = ConfigDict(frozen=True, extra="forbid")

    queryText: str = Field(min_length=1, max_length=500)
    limit: int = Field(default=defaultSearchLimit, ge=1, le=maxSearchLimit)


class CatalogSearchHit(BaseModel):
    """One ranked catalog entry."""

    model_config = ConfigDict(extra="forbid")

    skuId: Optional[str] = None
    title: Optional[str] = None
    category: Optional[str] = None
    baseUnitPricePaise: Optional[int] = None
    availableStock: Optional[int] = None
    gstRatePercent: Optional[int] = None
    hsnCode: Optional[str] = None
    merchantDid: Optional[str] = None
    score: Optional[float] = None


class CatalogSearchResponse(BaseModel):
    """Ranked results, plus what actually produced the ranking."""

    model_config = ConfigDict(extra="forbid")

    results: List[CatalogSearchHit]
    resultCount: int
    # "model" or "hash". Reported on every response, not just failures: a caller showing these
    # to a person must be able to say whether the ranking came from a language model or from a
    # character hash. Cosine over the latter ranks by incidental character overlap.
    embeddingMode: str
    # Plain-language companion to embeddingMode, so a consumer that just renders text still
    # tells the truth about what it is showing.
    rankingQuality: str
    indexAvailable: bool


semanticRankingNote = "Ranked by semantic similarity using the all-MiniLM-L6-v2 model."
degradedRankingNote = (
    "DEGRADED: the embedding model was unavailable, so results are ranked by a character-hash "
    "pseudo-vector. This is NOT semantic similarity and the ordering is not meaningful."
)
indexUnavailableNote = "The vector index is unavailable, so no catalog search could be run."


@catalogSearchRouter.post(
    "/search",
    response_model=CatalogSearchResponse,
    summary="Find catalog entries matching a natural-language query",
)
async def searchCatalog(
    request: CatalogSearchRequest,
    vectorizer: Any = Depends(getVectorizer),
) -> CatalogSearchResponse:
    """Ranks catalog entries against a plain-language description."""
    if vectorizer is None:
        # An empty result with no explanation would read as "no such product", which is a
        # different and much more misleading answer than "search is not running".
        return CatalogSearchResponse(
            results=[],
            resultCount=0,
            embeddingMode=embeddingModeHash,
            rankingQuality=indexUnavailableNote,
            indexAvailable=False,
        )

    try:
        hits, embeddingMode = await vectorizer.searchListings(request.queryText, request.limit)
    except Exception as err:
        logger.warning("Catalog search failed for query %r: %s", request.queryText, err)
        return CatalogSearchResponse(
            results=[],
            resultCount=0,
            embeddingMode=embeddingModeHash,
            rankingQuality=indexUnavailableNote,
            indexAvailable=False,
        )

    isDegraded = embeddingMode == embeddingModeHash
    return CatalogSearchResponse(
        results=[CatalogSearchHit(**hit) for hit in hits],
        resultCount=len(hits),
        embeddingMode=embeddingMode,
        rankingQuality=degradedRankingNote if isDegraded else semanticRankingNote,
        indexAvailable=True,
    )


__all__ = [
    "CatalogSearchRequest",
    "CatalogSearchResponse",
    "catalogSearchRouter",
    "searchCatalog",
]
