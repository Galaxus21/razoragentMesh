"""Out-of-stock exception interceptor and 3-stage self-healing coordinator."""

import time
from typing import Any, Dict, List, Optional

from razoragentMesh.packages.mandateEngine import (
    AmendmentMandate,
    CartMandate,
    Ed25519Signer,
    IntentMandate,
)


from ..constants.healerConstants import (
    defaultFallbackHsnCode,
    defaultGstRatePercent,
    maxPriceDeltaPercent,
    millisecondsPerSecond,
    minCosineSimilarity,
)
from ..constraints.constraintFilter import (
    NegativeConstraintFilter,
)
from ..constraints.negativeManifestSchema import (
    NegativeConstraintManifest,
)
from ..healerExceptions import (
    NoSubstituteFoundException,
)
from ..patching.mandatePatcher import MandatePatcher
from ..search.vectorSearcher import VectorSearcher


class OosInterceptor:
    """Coordinates 3-stage self-healing pipeline upon inventory reservation failure."""

    def __init__(
        self,
        qdrantClient: Optional[Any] = None,
        catalogStore: Optional[List[Dict[str, Any]]] = None,
    ) -> None:
        self.catalog = {s["skuId"]: s for s in (catalogStore or [])}
        self.searcher = VectorSearcher(qdrantClient, catalogStore)
        self.patcher = MandatePatcher()

    def _findViableSubstitute(
        self,
        failedSkuId: str,
        requestedQuantity: int,
        manifest: Optional[NegativeConstraintManifest],
        scoreThreshold: Optional[float] = None,
        maxPriceDeltaPct: Optional[float] = None,
    ) -> tuple[Dict[str, Any], float]:
        """Queries vector index and applies negative constraint AST evaluator.

        The two thresholds are parameters rather than the module constants they used to be read
        from directly. A caller that accepts a similarity floor or a price tolerance from its own
        API has to be able to pass it down; hardcoding them here meant such a caller would
        advertise knobs that silently did nothing.
        """
        if failedSkuId not in self.catalog:
            raise NoSubstituteFoundException(f"Failed SKU '{failedSkuId}' not found in catalog store")

        originalItem = self.catalog[failedSkuId]
        queryVector = originalItem.get("embeddingVector", [])
        hsnCode = originalItem.get("hsnCode", "")
        origPrice = originalItem.get("baseUnitPricePaise", 0)

        candidates = self.searcher.searchCandidates(
            queryVector=queryVector,
            hsnCode=hsnCode,
            originalPricePaise=origPrice,
            requestedQuantity=requestedQuantity,
            excludeSkuId=failedSkuId,
            scoreThreshold=minCosineSimilarity if scoreThreshold is None else scoreThreshold,
            maxPriceDeltaPct=(
                maxPriceDeltaPercent if maxPriceDeltaPct is None else maxPriceDeltaPct
            ),
        )

        filterEngine = NegativeConstraintFilter(manifest) if manifest else None

        for cand in candidates:
            if filterEngine is not None:
                evalRes = filterEngine.evaluateCandidate(cand.payload)
                if not evalRes.isAllowed:
                    continue
            return cand.payload, cand.score

        raise NoSubstituteFoundException(f"No valid substitute found for OOS SKU '{failedSkuId}'")

    def findSubstitute(
        self,
        failedSkuId: str,
        requestedQuantity: int,
        constraintManifest: Optional[NegativeConstraintManifest] = None,
        scoreThreshold: Optional[float] = None,
        maxPriceDeltaPct: Optional[float] = None,
    ) -> tuple[Dict[str, Any], float, float]:
        """Runs the substitution search alone, without patching or signing anything.

        `healOutOfStock` below needs a buyer signer AND a merchant signer, because it produces a
        dual-signed AmendmentMandate. No service holds both: the buyer key belongs to the agent.
        That made the whole class unconstructable outside tests, which is why Layer 3 shipped as
        a library nothing built.

        This is the half that needs no keys -- the Qdrant ANN query and the negative-constraint
        AST -- so it can run in the Merchant API, next to the vector index. The MCP server, which
        does hold the merchant key, signs the amendment afterwards.

        The returned duration is measured over exactly this work, which is what the "sub-300ms
        Qdrant ANN cosine similarity" claim is about. Mandate signing is deliberately not in it.
        """
        startTime = time.perf_counter()
        substitutePayload, cosineScore = self._findViableSubstitute(
            failedSkuId=failedSkuId,
            requestedQuantity=requestedQuantity,
            manifest=constraintManifest,
            scoreThreshold=scoreThreshold,
            maxPriceDeltaPct=maxPriceDeltaPct,
        )
        durationMs = (time.perf_counter() - startTime) * millisecondsPerSecond
        return substitutePayload, cosineScore, durationMs

    def healOutOfStock(
        self,
        failedSkuId: str,
        requestedQuantity: int,
        buyerAgentSigner: Ed25519Signer,
        merchantSigner: Ed25519Signer,
        originalCartMandate: CartMandate,
        intentMandate: Optional[IntentMandate] = None,
        constraintManifest: Optional[NegativeConstraintManifest] = None,
    ) -> tuple[AmendmentMandate, CartMandate, float, float]:
        """Executes full 3-stage self-healing workflow and measures total latency in milliseconds."""
        startTime = time.perf_counter()

        substitutePayload, cosineScore = self._findViableSubstitute(
            failedSkuId=failedSkuId,
            requestedQuantity=requestedQuantity,
            manifest=constraintManifest,
        )

        subSkuId = substitutePayload["skuId"]
        subUnitPrice = substitutePayload["baseUnitPricePaise"]
        subGstRate = substitutePayload.get("gstRatePercent", defaultGstRatePercent)
        subHsn = substitutePayload.get("hsnCode", defaultFallbackHsnCode)

        amendment, healedCart = self.patcher.patchCartMandate(
            originalCartMandate=originalCartMandate,
            failedSkuId=failedSkuId,
            substituteSkuId=subSkuId,
            substituteUnitPricePaise=subUnitPrice,
            substituteGstRatePercent=subGstRate,
            substituteHsnCode=subHsn,
            requestedQuantity=requestedQuantity,
            buyerAgentSigner=buyerAgentSigner,
            merchantSigner=merchantSigner,
            intentMandate=intentMandate,
        )

        durationMs = (time.perf_counter() - startTime) * millisecondsPerSecond
        return amendment, healedCart, durationMs, cosineScore


class SelfHealingCartEngine(OosInterceptor):
    """Alias for OosInterceptor maintaining test harness compatibility."""


__all__ = [
    "OosInterceptor",
    "SelfHealingCartEngine",
]
