"""Out-of-stock exception interceptor and 3-stage self-healing coordinator."""

import time
from typing import Any, Dict, List, Optional
from razoragentMesh.packages.mandateEngine.amendmentMandateSchema import AmendmentMandate
from razoragentMesh.packages.mandateEngine.cartMandateSchema import CartMandate
from razoragentMesh.packages.mandateEngine.ed25519Signer import Ed25519Signer
from razoragentMesh.packages.mandateEngine.intentMandateSchema import IntentMandate
from razoragentMesh.packages.vectorHealer.constraintFilter import (
    NegativeConstraintFilter,
    NegativeConstraintManifest,
)
from razoragentMesh.packages.vectorHealer.healerConstants import (
    maxPriceDeltaPercent,
    minCosineSimilarity,
)
from razoragentMesh.packages.vectorHealer.healerExceptions import (
    NoSubstituteFoundException,
)
from razoragentMesh.packages.vectorHealer.mandatePatcher import MandatePatcher
from razoragentMesh.packages.vectorHealer.vectorSearcher import VectorSearcher


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
    ) -> tuple[Dict[str, Any], float]:
        """Queries vector index and applies negative constraint AST evaluator."""
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
            scoreThreshold=minCosineSimilarity,
            maxPriceDeltaPct=maxPriceDeltaPercent,
        )

        filterEngine = NegativeConstraintFilter(manifest) if manifest else None

        for cand in candidates:
            if filterEngine is not None:
                evalRes = filterEngine.evaluateCandidate(cand.payload)
                if not evalRes.isAllowed:
                    continue
            return cand.payload, cand.score

        raise NoSubstituteFoundException(f"No valid substitute found for OOS SKU '{failedSkuId}'")

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
        subGstRate = substitutePayload.get("gstRatePercent", 18)
        subHsn = substitutePayload.get("hsnCode", "8471")

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

        durationMs = (time.perf_counter() - startTime) * 1000.0
        return amendment, healedCart, durationMs, cosineScore


class SelfHealingCartEngine(OosInterceptor):
    """Alias for OosInterceptor maintaining test harness compatibility."""
