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

    def healOutOfStock(
        self,
        failedSkuId: str,
        requestedQuantity: int,
        buyerAgentSigner: Ed25519Signer,
        merchantSigner: Ed25519Signer,
        originalCartMandate: CartMandate,
    ) -> tuple[AmendmentMandate, CartMandate, float, float]:
        startTime = time.perf_counter()

        originalItem = self._catalog[failedSkuId]
        queryVector = originalItem["embeddingVector"]
        hsnCode = originalItem["hsnCode"]
        origPrice = originalItem["baseUnitPricePaise"]

        # Step 1: Vector similarity search with HSN filter
        scoredPoints = self._qdrant.search(
            collectionName="merchantCatalog",
            queryVector=queryVector,
            limit=5,
            scoreThreshold=minCosineSimilarity,
            filterHsnCode=hsnCode,
            excludeSkuId=failedSkuId,
        )

        substitute = None
        for point in scoredPoints:
            candPrice = point.payload["baseUnitPricePaise"]
            candStock = point.payload["availableStock"]
            priceDeltaPct = abs(candPrice - origPrice) / origPrice * 100.0

            if candStock >= requestedQuantity and priceDeltaPct <= maxPriceDeltaPercent:
                substitute = point
                break

        if not substitute:
            raise RuntimeError(f"No valid substitute found for {failedSkuId}")

        subSkuId = substitute.payload["skuId"]
        subUnitPrice = substitute.payload["baseUnitPricePaise"]
        subGstRate = substitute.payload["gstRatePercent"]

        # Step 2: Recompute deterministic financial line items & GST
        newTaxable = computeLineItemTotal(subUnitPrice, requestedQuantity)
        newGst = computeGstBreakdown(newTaxable, subGstRate, isIntraState=True)
        newTotal = computeCartSettlementTotal(newTaxable, newGst["totalTaxPaise"])

        newCartItem = CartItemSchema(
            skuId=subSkuId,
            quantity=requestedQuantity,
            unitPricePaise=subUnitPrice,
            hsnCode=hsnCode,
            gstRatePercent=subGstRate,
            lineTotalPaise=newTaxable,
        )
        newTaxBreakdown = TaxBreakdownSchema(
            cgstPaise=newGst["cgstPaise"],
            sgstPaise=newGst["sgstPaise"],
            igstPaise=0,
            totalTaxPaise=newGst["totalTaxPaise"],
        )

        now = int(time.time())
        newCartMandate = createSignedCartMandate(
            cartId=f"cart_healed_{subSkuId.lower()}",
            merchantSigner=merchantSigner,
            merchantGstin=originalCartMandate.merchantGstin,
            merchantStateCode=originalCartMandate.merchantStateCode,
            buyerDeliveryPincode=originalCartMandate.buyerDeliveryPincode,
            buyerDeliveryStateCode=originalCartMandate.buyerDeliveryStateCode,
            items=[newCartItem],
            taxableSubtotalPaise=newTaxable,
            taxBreakdown=newTaxBreakdown,
            shippingPaise=0,
            discountPaise=0,
            totalPaise=newTotal,
            inventoryLockToken="lock_token_healed_sku104",
            inventoryLockExpiresAt=now + 60,
            timestamp=now,
        )

        priceDeltaPaise = subUnitPrice - origPrice
        amendmentMandate = createSignedAmendmentMandate(
            amendmentId="amend_tc04_oos",
            buyerAgentSigner=buyerAgentSigner,
            merchantSigner=merchantSigner,
            previousCartMandate=originalCartMandate,
            newCartMandate=newCartMandate,
            substitutedSkuMapping={failedSkuId: subSkuId},
            priceDeltaPaise=priceDeltaPaise,
            amendmentReason="INSUFFICIENT_STOCK_OOS_HEALED",
            timestamp=now,
        )

        elapsedMs = (time.perf_counter() - startTime) * 1000.0
        return amendmentMandate, newCartMandate, elapsedMs, substitute.score


def testTc04OosSelfHealingLatencyAndIntegrity(
    agentKeyFixtures: Dict[str, Any],
    catalogFixtures: List[Dict[str, Any]],
    mockQdrantClient: Any,
) -> None:
    """TC-04: OOS Self-Healing — SKU-101 OOS auto-substitutes SKU-104 with < 300ms SLA."""
    buyerKey = agentKeyFixtures["buyerAgent"]
    merchantKey = agentKeyFixtures["merchantNode"]

    buyerSigner = Ed25519Signer(buyerKey["privateKeyHex"])
    merchantSigner = Ed25519Signer(merchantKey["privateKeyHex"])

    # Create dummy original CartMandate with OOS SKU-101
    now = int(time.time())
    origTaxable = originalPricePaise
    origGst = computeGstBreakdown(origTaxable, 18, isIntraState=True)
    origTotal = computeCartSettlementTotal(origTaxable, origGst["totalTaxPaise"])

    originalCart = createSignedCartMandate(
        cartId="cart_orig_oos_sku101",
        merchantSigner=merchantSigner,
        merchantGstin="29AABCU9603R1ZM",
        merchantStateCode="29",
        buyerDeliveryPincode="560001",
        buyerDeliveryStateCode="29",
        items=[
            CartItemSchema(
                skuId=originalOosSkuId,
                quantity=1,
                unitPricePaise=originalPricePaise,
                hsnCode="8471",
                gstRatePercent=18,
                lineTotalPaise=origTaxable,
            )
        ],
        taxableSubtotalPaise=origTaxable,
        taxBreakdown=TaxBreakdownSchema(
            cgstPaise=origGst["cgstPaise"],
            sgstPaise=origGst["sgstPaise"],
            igstPaise=0,
            totalTaxPaise=origGst["totalTaxPaise"],
        ),
        shippingPaise=0,
        discountPaise=0,
        totalPaise=origTotal,
        inventoryLockToken="lock_failed_oos",
        inventoryLockExpiresAt=now + 60,
        timestamp=now,
    )

    healer = SelfHealingCartEngine(mockQdrantClient, catalogFixtures)
    amendment, healedCart, durationMs, cosineSim = healer.healOutOfStock(
        failedSkuId=originalOosSkuId,
        requestedQuantity=1,
        buyerAgentSigner=buyerSigner,
        merchantSigner=merchantSigner,
        originalCartMandate=originalCart,
    )

    # TC-04 Invariants
    assert durationMs < targetSlaMs
    assert amendment.substitutedSkuMapping[originalOosSkuId] == expectedSubstituteSkuId
    assert amendment.priceDeltaPaise == 5000  # Exactly ₹50
    assert cosineSim >= minCosineSimilarity
    assert healedCart.items[0].skuId == expectedSubstituteSkuId
    assert healedCart.totalPaise == (355000 + (355000 * 18 // 100))

    # Cryptographic signature validation on AmendmentMandate
    agentPub = extractPublicKeyFromDid(buyerSigner.getAgentDid())
    merchantPub = extractPublicKeyFromDid(merchantSigner.getAgentDid())

    unsignedPayload = {
        k: v
        for k, v in amendment.model_dump().items()
        if k not in ("agentSignature", "merchantSignature")
    }
    assert Ed25519Verifier.verifyPayloadSignature(
        publicKeyHex=agentPub,
        payload=unsignedPayload,
        signatureHex=amendment.agentSignature,
    )
    assert Ed25519Verifier.verifyPayloadSignature(
        publicKeyHex=merchantPub,
        payload=unsignedPayload,
        signatureHex=amendment.merchantSignature,
    )
