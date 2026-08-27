import time
from typing import Any, Dict, List, Optional
import pytest

from razoragentMesh.packages.mandateEngine.mandates.amendmentMandateSchema import AmendmentMandate
from razoragentMesh.packages.mandateEngine.verification.arithmeticEnclave import (
    computeCartSettlementTotal,
    computeGstBreakdown,
    computeLineItemTotal,
)
from razoragentMesh.packages.mandateEngine.mandates.cartMandateSchema import (
    CartItemSchema,
    CartMandate,
    TaxBreakdownSchema,
)
from razoragentMesh.packages.mandateEngine.crypto.cryptoKeyUtils import extractPublicKeyFromDid
from razoragentMesh.packages.mandateEngine.crypto.ed25519Signer import Ed25519Signer
from razoragentMesh.packages.mandateEngine.crypto.ed25519Verifier import Ed25519Verifier
from razoragentMesh.packages.mandateEngine.mandates.mandateFactory import (
    createSignedAmendmentMandate,
    createSignedCartMandate,
)

# Benchmark Constants
originalOosSkuId = "SKU-101"
expectedSubstituteSkuId = "SKU-104"
originalPricePaise = 350000  # ₹3,500
substitutePricePaise = 355000  # ₹3,550 (+₹50 / +1.43%)
maxPriceDeltaPercent = 5.0
minCosineSimilarity = 0.85
targetSlaMs = 300.0


class SelfHealingCartEngine:
    """Self-healing cart engine executing vector search and AP2 mandate patching."""

    def __init__(self, qdrantClient: Any, catalogStore: List[Dict[str, Any]]) -> None:
        self._qdrant = qdrantClient
        self._catalog = {s["skuId"]: s for s in catalogStore}

    def _findSubstitute(self, failedSkuId: str, reqQty: int, origPrice: int, hsnCode: str, queryVector: list) -> Any:
        scoredPoints = self._qdrant.search(
            collectionName="merchantCatalog", queryVector=queryVector, limit=5,
            scoreThreshold=minCosineSimilarity, filterHsnCode=hsnCode, excludeSkuId=failedSkuId,
        )
        for point in scoredPoints:
            candPrice, candStock = point.payload["baseUnitPricePaise"], point.payload["availableStock"]
            if candStock >= reqQty and (abs(candPrice - origPrice) / origPrice * 100.0) <= maxPriceDeltaPercent:
                return point
        raise RuntimeError(f"No valid substitute found for {failedSkuId}")

    def _buildHealedMandates(
        self, originalCart: CartMandate, subSkuId: str, subPrice: int, subGstRate: int,
        hsnCode: str, reqQty: int, origPrice: int, failedSkuId: str,
        buyerAgentSigner: Ed25519Signer, merchantSigner: Ed25519Signer, now: int,
    ) -> tuple[AmendmentMandate, CartMandate]:
        taxable = computeLineItemTotal(subPrice, reqQty)
        gst = computeGstBreakdown(taxable, subGstRate, isIntraState=True)
        total = computeCartSettlementTotal(taxable, gst["totalTaxPaise"])
        cartItem = CartItemSchema(skuId=subSkuId, quantity=reqQty, unitPricePaise=subPrice, hsnCode=hsnCode, gstRatePercent=subGstRate, lineTotalPaise=taxable)
        taxBreakdown = TaxBreakdownSchema(cgstPaise=gst["cgstPaise"], sgstPaise=gst["sgstPaise"], igstPaise=0, totalTaxPaise=gst["totalTaxPaise"])
        newCart = createSignedCartMandate(
            cartId=f"cart_healed_{subSkuId.lower()}", merchantSigner=merchantSigner,
            merchantGstin=originalCart.merchantGstin, merchantStateCode=originalCart.merchantStateCode,
            buyerDeliveryPincode=originalCart.buyerDeliveryPincode, buyerDeliveryStateCode=originalCart.buyerDeliveryStateCode,
            items=[cartItem], taxableSubtotalPaise=taxable, taxBreakdown=taxBreakdown,
            shippingPaise=0, discountPaise=0, totalPaise=total,
            inventoryLockToken="lock_token_healed_sku104", inventoryLockExpiresAt=now + 60, timestamp=now,
        )
        amendment = createSignedAmendmentMandate(
            amendmentId="amend_tc04_oos", buyerAgentSigner=buyerAgentSigner, merchantSigner=merchantSigner,
            previousCartMandate=originalCart, newCartMandate=newCart, substitutedSkuMapping={failedSkuId: subSkuId},
            priceDeltaPaise=subPrice - origPrice, amendmentReason="INSUFFICIENT_STOCK_OOS_HEALED", timestamp=now,
        )
        return amendment, newCart

    def healOutOfStock(
        self, failedSkuId: str, requestedQuantity: int, buyerAgentSigner: Ed25519Signer,
        merchantSigner: Ed25519Signer, originalCartMandate: CartMandate,
    ) -> tuple[AmendmentMandate, CartMandate, float, float]:
        startTime = time.perf_counter()
        orig = self._catalog[failedSkuId]
        sub = self._findSubstitute(failedSkuId, requestedQuantity, orig["baseUnitPricePaise"], orig["hsnCode"], orig["embeddingVector"])
        now = int(time.time())
        amendment, newCart = self._buildHealedMandates(
            originalCartMandate, sub.payload["skuId"], sub.payload["baseUnitPricePaise"],
            sub.payload["gstRatePercent"], orig["hsnCode"], requestedQuantity, orig["baseUnitPricePaise"],
            failedSkuId, buyerAgentSigner, merchantSigner, now,
        )
        elapsedMs = (time.perf_counter() - startTime) * 1000.0
        return amendment, newCart, elapsedMs, sub.score


def _buildOriginalOosCart(merchantSigner: Ed25519Signer, now: int) -> CartMandate:
    origTaxable = originalPricePaise
    origGst = computeGstBreakdown(origTaxable, 18, isIntraState=True)
    origTotal = computeCartSettlementTotal(origTaxable, origGst["totalTaxPaise"])
    item = CartItemSchema(skuId=originalOosSkuId, quantity=1, unitPricePaise=originalPricePaise, hsnCode="8471", gstRatePercent=18, lineTotalPaise=origTaxable)
    taxBreakdown = TaxBreakdownSchema(cgstPaise=origGst["cgstPaise"], sgstPaise=origGst["sgstPaise"], igstPaise=0, totalTaxPaise=origGst["totalTaxPaise"])
    return createSignedCartMandate(
        cartId="cart_orig_oos_sku101", merchantSigner=merchantSigner, merchantGstin="29AABCU9603R1ZJ",
        merchantStateCode="29", buyerDeliveryPincode="560001", buyerDeliveryStateCode="29",
        items=[item], taxableSubtotalPaise=origTaxable, taxBreakdown=taxBreakdown,
        shippingPaise=0, discountPaise=0, totalPaise=origTotal,
        inventoryLockToken="lock_failed_oos", inventoryLockExpiresAt=now + 60, timestamp=now,
    )


def testTc04OosSelfHealingLatencyAndIntegrity(
    agentKeyFixtures: Dict[str, Any], catalogFixtures: List[Dict[str, Any]], mockQdrantClient: Any,
) -> None:
    """TC-04: OOS Self-Healing — SKU-101 OOS auto-substitutes SKU-104 with < 300ms SLA."""
    buyerSigner = Ed25519Signer(agentKeyFixtures["buyerAgent"]["privateKeyHex"])
    merchantSigner = Ed25519Signer(agentKeyFixtures["merchantNode"]["privateKeyHex"])

    originalCart = _buildOriginalOosCart(merchantSigner, int(time.time()))
    healer = SelfHealingCartEngine(mockQdrantClient, catalogFixtures)
    amendment, healedCart, durationMs, cosineSim = healer.healOutOfStock(
        failedSkuId=originalOosSkuId, requestedQuantity=1,
        buyerAgentSigner=buyerSigner, merchantSigner=merchantSigner, originalCartMandate=originalCart,
    )

    assert durationMs < targetSlaMs and amendment.substitutedSkuMapping[originalOosSkuId] == expectedSubstituteSkuId
    assert amendment.priceDeltaPaise == 5000 and cosineSim >= minCosineSimilarity
    assert healedCart.items[0].skuId == expectedSubstituteSkuId and healedCart.totalPaise == (355000 + (355000 * 18 // 100))

    agentPub = extractPublicKeyFromDid(buyerSigner.getAgentDid())
    merchantPub = extractPublicKeyFromDid(merchantSigner.getAgentDid())
    unsignedPayload = {k: v for k, v in amendment.model_dump().items() if k not in ("agentSignature", "merchantSignature")}
    assert Ed25519Verifier.verifyPayloadSignature(publicKeyHex=agentPub, payload=unsignedPayload, signatureHex=amendment.agentSignature)
    assert Ed25519Verifier.verifyPayloadSignature(publicKeyHex=merchantPub, payload=unsignedPayload, signatureHex=amendment.merchantSignature)

