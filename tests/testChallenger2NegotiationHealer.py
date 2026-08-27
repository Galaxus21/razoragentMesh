"""Negotiation, Self-Healing and Negative Constraints Invariant Tests.

Tests:
1. Rubinstein-Ståhl Bargaining Monotonicity (TC-02)
2. Out-of-Stock Self-Healing & Latency SLA (TC-04)
3. Negative Constraint Filtering (TC-05)
"""

import time
from typing import Any, Dict, List
import pytest

from razoragentMesh.packages.mandateEngine.mandates.cartMandateSchema import (
    CartItemSchema,
    CartMandate,
    TaxBreakdownSchema,
)
from razoragentMesh.packages.mandateEngine.crypto.cryptoKeyUtils import extractPublicKeyFromDid
from razoragentMesh.packages.mandateEngine.crypto.ed25519Signer import Ed25519Signer
from razoragentMesh.packages.mandateEngine.crypto.ed25519Verifier import Ed25519Verifier
from razoragentMesh.packages.mandateEngine.mandates.mandateFactory import (
    createSignedCartMandate,
    createSignedIntentMandate,
)
from razoragentMesh.packages.mandateEngine.settlement.settlementExceptions import (
    BudgetExceededViolation,
)
from razoragentMesh.packages.vectorHealer.src.constraints import (
    NegativeConstraintFilter,
    NegativeConstraintManifest,
)
from razoragentMesh.packages.vectorHealer.src.interception import OosInterceptor
from razoragentMesh.packages.x402Gateway.src.compiler.astContractCompiler import (
    compileCommercialContractAst,
)
from razoragentMesh.packages.x402Gateway.src.negotiation.bidStateMachine import (
    NegotiationStatus,
    RubinsteinStahlNegotiator,
)
from razoragentMesh.packages.x402Gateway.src.gatewayExceptions import (
    NegotiationExhaustedException,
    NonMonotonicConcessionViolation,
)
from razoragentMesh.tests.mockInfraHelpers import MockQdrantClient


def _createOosSampleCart(merchantSigner: Ed25519Signer, cartId: str, lockToken: str) -> CartMandate:
    now = int(time.time())
    return createSignedCartMandate(
        cartId=cartId,
        merchantSigner=merchantSigner,
        merchantGstin="29AABCU9603R1ZJ",
        merchantStateCode="29",
        buyerDeliveryPincode="560001",
        buyerDeliveryStateCode="29",
        items=[
            CartItemSchema(
                skuId="SKU-101",
                quantity=1,
                unitPricePaise=350000,
                hsnCode="8471",
                gstRatePercent=18,
                lineTotalPaise=350000,
            )
        ],
        taxableSubtotalPaise=350000,
        taxBreakdown=TaxBreakdownSchema(cgstPaise=31500, sgstPaise=31500, igstPaise=0, totalTaxPaise=63000),
        shippingPaise=0,
        discountPaise=0,
        totalPaise=413000,
        inventoryLockToken=lockToken,
        inventoryLockExpiresAt=now + 60,
        timestamp=now,
    )


def testChallenger2RubinsteinStahlMonotonicityViolations() -> None:
    """Stress Test 3.1a: Bid decrease and ask increase raise NonMonotonicConcessionViolation."""
    negotiator = RubinsteinStahlNegotiator(
        skuId="SKU-CHAIR-001",
        quantity=10,
        escrowBalancePaise=5000,
        sellerCostFloorPaise=330000,
    )
    turn1 = negotiator.executeTurn(1, 320000, 350000)
    assert not turn1.isConverged
    assert negotiator.cumulativeMicroFeesPaise == 50
    assert negotiator.escrowBalancePaise == 4950

    with pytest.raises(NonMonotonicConcessionViolation) as excInfo:
        negotiator.executeTurn(2, 315000, 345000)
    assert "Buyer bid cannot decrease" in str(excInfo.value)

    with pytest.raises(NonMonotonicConcessionViolation) as excInfo2:
        negotiator.executeTurn(2, 325000, 355000)
    assert "Seller ask cannot increase" in str(excInfo2.value)


def testChallenger2RubinsteinStahlProgressionAndExhaustion() -> None:
    """Stress Test 3.1b: Valid turn progression, exhaustion at turn 5, and rejection at turn 6."""
    negotiator = RubinsteinStahlNegotiator(
        skuId="SKU-CHAIR-001",
        quantity=10,
        escrowBalancePaise=5000,
        sellerCostFloorPaise=330000,
    )
    negotiator.executeTurn(1, 320000, 350000)
    assert not negotiator.executeTurn(2, 325000, 345000).isConverged
    assert negotiator.cumulativeMicroFeesPaise == 100
    assert not negotiator.executeTurn(3, 330000, 340000).isConverged
    assert negotiator.cumulativeMicroFeesPaise == 150
    assert not negotiator.executeTurn(4, 332000, 335000).isConverged
    assert negotiator.cumulativeMicroFeesPaise == 200

    turn5 = negotiator.executeTurn(5, 333000, 334000)
    assert not turn5.isConverged
    assert negotiator.status == NegotiationStatus.NEGOTIATION_EXHAUSTED
    assert negotiator.cumulativeMicroFeesPaise == 250

    with pytest.raises(NegotiationExhaustedException):
        negotiator.executeTurn(6, 334000, 334000)


def testChallenger2RubinsteinStahlMarginFloorAndAstCompilation() -> None:
    """Stress Test 3.2: Seller margin floor enforcement and AST compilation integrity."""
    negotiator = RubinsteinStahlNegotiator(
        skuId="SKU-104",
        quantity=50,
        escrowBalancePaise=5000,
        sellerCostFloorPaise=335000,
    )
    counterAsk = negotiator.computeSellerCounterAsk(initialAskPaise=345000, buyerBidPaise=300000, turnIndex=10)
    assert counterAsk >= 335000, "Counter-ask must not breach seller cost floor"

    negotiator.executeTurn(1, 330000, 345000)
    negotiator.executeTurn(2, 333000, 338000)
    finalTurn = negotiator.executeTurn(3, 335000, 335000)

    assert finalTurn.isConverged
    assert negotiator.status == NegotiationStatus.CONVERGED
    assert negotiator.cumulativeMicroFeesPaise == 150

    ast, astHash = compileCommercialContractAst(
        skuId="SKU-104", quantity=50, agreedUnitPrice=335000, turns=3,
        buyerDid="did:agent:buyer_c2", merchantDid="did:agent:merchant_c2",
        timestamp=1755936000, gstRate=18, isIntraState=True,
    )
    assert ast.agreedUnitPricePaise == 335000
    assert ast.taxableSubtotalPaise == 16750000
    assert ast.totalTaxPaise == 3015000
    assert ast.totalGrossPaise == 19765000
    assert len(astHash) == 64


def testChallenger2OosSelfHealingBoundaryConditions(
    agentKeyFixtures: Dict[str, Any],
    catalogFixtures: List[Dict[str, Any]],
    mockQdrantClient: MockQdrantClient,
) -> None:
    """Stress Test 4.1: Vector boundary conditions and dual signature verification."""
    buyerSigner = Ed25519Signer(agentKeyFixtures["buyerAgent"]["privateKeyHex"])
    merchantSigner = Ed25519Signer(agentKeyFixtures["merchantNode"]["privateKeyHex"])
    origCart = _createOosSampleCart(merchantSigner, "cart_c2_oos_test", "lock_failed_oos")
    interceptor = OosInterceptor(mockQdrantClient, catalogFixtures)

    amendment, healedCart, durationMs, cosineSim = interceptor.healOutOfStock(
        failedSkuId="SKU-101", requestedQuantity=1, buyerAgentSigner=buyerSigner,
        merchantSigner=merchantSigner, originalCartMandate=origCart,
    )

    assert durationMs < 300.0, f"Healing latency {durationMs:.2f}ms exceeded 300ms SLA"
    assert amendment.substitutedSkuMapping["SKU-101"] == "SKU-104"
    assert amendment.priceDeltaPaise == 5000
    assert cosineSim >= 0.85
    assert healedCart.items[0].skuId == "SKU-104"

    agentPub = extractPublicKeyFromDid(buyerSigner.getAgentDid())
    merchantPub = extractPublicKeyFromDid(merchantSigner.getAgentDid())
    unsignedAmendment = {k: v for k, v in amendment.model_dump().items() if k not in ("agentSignature", "merchantSignature")}
    assert Ed25519Verifier.verifyPayloadSignature(agentPub, unsignedAmendment, amendment.agentSignature)
    assert Ed25519Verifier.verifyPayloadSignature(merchantPub, unsignedAmendment, amendment.merchantSignature)


def testChallenger2OosSelfHealing100IterationsLatencySla(
    agentKeyFixtures: Dict[str, Any],
    catalogFixtures: List[Dict[str, Any]],
    mockQdrantClient: MockQdrantClient,
) -> None:
    """Stress Test 4.2: 100 consecutive OOS self-healing cycles for latency SLA compliance."""
    buyerSigner = Ed25519Signer(agentKeyFixtures["buyerAgent"]["privateKeyHex"])
    merchantSigner = Ed25519Signer(agentKeyFixtures["merchantNode"]["privateKeyHex"])
    origCart = _createOosSampleCart(merchantSigner, "cart_c2_sla_test", "lock_sla_oos")
    interceptor = OosInterceptor(mockQdrantClient, catalogFixtures)

    latencies: List[float] = []
    for _ in range(100):
        _, _, durationMs, _ = interceptor.healOutOfStock(
            failedSkuId="SKU-101", requestedQuantity=1, buyerAgentSigner=buyerSigner,
            merchantSigner=merchantSigner, originalCartMandate=origCart,
        )
        latencies.append(durationMs)

    assert len(latencies) == 100
    assert max(latencies) < 300.0, f"Max latency {max(latencies):.2f}ms exceeded 300ms SLA"
    assert (sum(latencies) / len(latencies)) < 20.0


def testChallenger2OosSelfHealingBudgetExceededGuard(
    agentKeyFixtures: Dict[str, Any],
    catalogFixtures: List[Dict[str, Any]],
    mockQdrantClient: MockQdrantClient,
) -> None:
    """Stress Test 4.3: Substitute pushes total beyond delegated budget -> raises BudgetExceededViolation."""
    buyerSigner = Ed25519Signer(agentKeyFixtures["buyerAgent"]["privateKeyHex"])
    merchantSigner = Ed25519Signer(agentKeyFixtures["merchantNode"]["privateKeyHex"])

    intentMandate = createSignedIntentMandate(
        mandateId="intent_tight_budget", userSigner=buyerSigner,
        delegatedAgentDid=buyerSigner.getAgentDid(), maxBudgetPaise=415000,
        upiCircleDelegationToken="upi_tok_c2_test", singleTransactionLimitPaise=500000,
        authorizedCategories=["electronics"], validUntilTimestamp=int(time.time()) + 3600,
    )
    origCart = _createOosSampleCart(merchantSigner, "cart_budget_tight", "lock_budget_tight")
    interceptor = OosInterceptor(mockQdrantClient, catalogFixtures)

    with pytest.raises(BudgetExceededViolation):
        interceptor.healOutOfStock(
            failedSkuId="SKU-101", requestedQuantity=1, buyerAgentSigner=buyerSigner,
            merchantSigner=merchantSigner, originalCartMandate=origCart,
            intentMandate=intentMandate,
        )


def testChallenger2NegativeConstraintAdversarialAllergensAndBrands(
    catalogFixtures: List[Dict[str, Any]],
) -> None:
    """Stress Test 5.1: Adversarial variations of blacklisted allergens and excluded brands."""
    manifest = NegativeConstraintManifest(
        excludedAllergens=["  PeAnUt  ", "PEANUT_OIL", "tree-nuts"],
        excludedBrands=["  SensTech  ", "BadVendor"],
        maxWeightGrams=1000,
        maxSlaHours=48,
    )
    filterEngine = NegativeConstraintFilter(manifest)

    sku201 = next(s for s in catalogFixtures if s["skuId"] == "SKU-201")
    eval201 = filterEngine.evaluateCandidate(sku201)
    assert not eval201.isAllowed
    assert "ALLERGEN_BREACH:peanut" in str(eval201.rejectionReason)

    sku001 = next(s for s in catalogFixtures if s["skuId"] == "SKU-001")
    eval001 = filterEngine.evaluateCandidate(sku001)
    assert not eval001.isAllowed
    assert "BRAND_EXCLUDED:senstech" in str(eval001.rejectionReason)

    sku301 = next(s for s in catalogFixtures if s["skuId"] == "SKU-301")
    eval301 = filterEngine.evaluateCandidate(sku301)
    assert not eval301.isAllowed
    assert "WEIGHT_LIMIT_EXCEEDED" in str(eval301.rejectionReason)

    sku205 = next(s for s in catalogFixtures if s["skuId"] == "SKU-205")
    eval205 = filterEngine.evaluateCandidate(sku205)
    assert eval205.isAllowed
    assert eval205.rejectionReason is None


def testChallenger2NegativeConstraintMultiDimensionAndSlaBreach() -> None:
    """Stress Test 5.2: Dimension and SLA constraint boundary enforcement."""
    manifest = NegativeConstraintManifest(
        maxDimensionCm={"length": 50, "width": 50, "height": 50},
        maxSlaHours=24,
    )
    filterEngine = NegativeConstraintFilter(manifest)

    oversized = {
        "skuId": "SKU-LARGE-001", "brand": "StandardBrand",
        "attributes": {"dimensionsCm": {"length": 65, "width": 40, "height": 40}, "weightGrams": 300},
        "slaHours": 12,
    }
    evalDim = filterEngine.evaluateCandidate(oversized)
    assert not evalDim.isAllowed
    assert "DIMENSION_LIMIT_EXCEEDED:length:65cm" in str(evalDim.rejectionReason)

    slow = {
        "skuId": "SKU-SLOW-001", "brand": "StandardBrand",
        "attributes": {"dimensionsCm": {"length": 20, "width": 20, "height": 20}, "weightGrams": 300},
        "slaHours": 48,
    }
    evalSla = filterEngine.evaluateCandidate(slow)
    assert not evalSla.isAllowed
    assert "SLA_EXCEEDED:48h" in str(evalSla.rejectionReason)

    ok = {
        "skuId": "SKU-OK-001", "brand": "StandardBrand",
        "attributes": {"dimensionsCm": {"length": 20, "width": 20, "height": 20}, "weightGrams": 300},
        "slaHours": 18,
    }
    evalOk = filterEngine.evaluateCandidate(ok)
    assert evalOk.isAllowed
    assert evalOk.rejectionReason is None
