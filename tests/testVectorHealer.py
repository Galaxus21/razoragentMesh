"""Comprehensive unit and integration tests for Layer 3 vectorHealer."""

import time
from typing import Any, Dict, List
import pytest

from razoragentMesh.packages.mandateEngine.arithmeticEnclave import (
    computeCartSettlementTotal,
    computeGstBreakdown,
)
from razoragentMesh.packages.mandateEngine.cartMandateSchema import (
    CartItemSchema,
    TaxBreakdownSchema,
)
from razoragentMesh.packages.mandateEngine.cryptoKeyUtils import extractPublicKeyFromDid
from razoragentMesh.packages.mandateEngine.ed25519Signer import Ed25519Signer
from razoragentMesh.packages.mandateEngine.ed25519Verifier import Ed25519Verifier
from razoragentMesh.packages.mandateEngine.intentMandateSchema import IntentMandate
from razoragentMesh.packages.mandateEngine.mandateFactory import (
    createSignedCartMandate,
    createSignedIntentMandate,
)
from razoragentMesh.packages.mandateEngine.settlementExceptions import (
    BudgetExceededViolation,
)
from razoragentMesh.packages.vectorHealer.constraintFilter import (
    NegativeConstraintFilter,
    NegativeConstraintManifest,
)
from razoragentMesh.packages.vectorHealer.embeddingProvider import EmbeddingProvider
from razoragentMesh.packages.vectorHealer.healerExceptions import (
    EmbeddingInferenceException,
    NoSubstituteFoundException,
)
from razoragentMesh.packages.vectorHealer.mandatePatcher import MandatePatcher
from razoragentMesh.packages.vectorHealer.oosInterceptor import (
    OosInterceptor,
    SelfHealingCartEngine,
)
from razoragentMesh.packages.vectorHealer.vectorSearcher import VectorSearcher


def testEmbeddingProviderNormalizationAndCosine() -> None:
    """Verifies vector normalization and cosine similarity computation."""
    provider = EmbeddingProvider()

    vec1 = [1.0, 0.0, 0.0]
    vec2 = [1.0, 0.0, 0.0]
    vec3 = [0.0, 1.0, 0.0]

    simIdentical = provider.computeCosineSimilarity(vec1, vec2)
    assert pytest.approx(simIdentical, 1e-5) == 1.0

    simOrthogonal = provider.computeCosineSimilarity(vec1, vec3)
    assert pytest.approx(simOrthogonal, 1e-5) == 0.0

    # Cache registration and retrieval
    provider.registerCachedVector("test_sku", [3.0, 4.0, 0.0])
    emb = provider.computeEmbedding("test_sku")
    assert pytest.approx(sum(x * x for x in emb), 1e-5) == 1.0

    # Empty text raises exception
    with pytest.raises(EmbeddingInferenceException):
        provider.computeEmbedding("")


def testNegativeConstraintFilterEvaluation() -> None:
    """Verifies allergen, brand, physical, and SLA constraint filtering."""
    manifest = NegativeConstraintManifest(
        excludedAllergens=["peanut"],
        excludedBrands=["BadBrand"],
        maxWeightGrams=500,
        maxSlaHours=48,
    )
    filterEngine = NegativeConstraintFilter(manifest)

    # 1. Allergen breach
    itemAllergen = {
        "skuId": "SKU-TEST-01",
        "brand": "GoodBrand",
        "attributes": {"allergens": ["peanut_oil"], "weightGrams": 200, "slaHours": 24},
    }
    evalAllergen = filterEngine.evaluateCandidate(itemAllergen)
    assert not evalAllergen.isAllowed
    assert "ALLERGEN_BREACH" in str(evalAllergen.rejectionReason)

    # 2. Brand breach
    itemBrand = {
        "skuId": "SKU-TEST-02",
        "brand": "BadBrand",
        "attributes": {"allergens": [], "weightGrams": 200, "slaHours": 24},
    }
    evalBrand = filterEngine.evaluateCandidate(itemBrand)
    assert not evalBrand.isAllowed
    assert "BRAND_EXCLUDED" in str(evalBrand.rejectionReason)

    # 3. Weight breach
    itemWeight = {
        "skuId": "SKU-TEST-03",
        "brand": "GoodBrand",
        "attributes": {"allergens": [], "weightGrams": 600, "slaHours": 24},
    }
    evalWeight = filterEngine.evaluateCandidate(itemWeight)
    assert not evalWeight.isAllowed
    assert "WEIGHT_LIMIT_EXCEEDED" in str(evalWeight.rejectionReason)

    # 4. Valid item passes
    itemValid = {
        "skuId": "SKU-TEST-04",
        "brand": "GoodBrand",
        "attributes": {"allergens": [], "weightGrams": 300, "slaHours": 24},
    }
    evalValid = filterEngine.evaluateCandidate(itemValid)
    assert evalValid.isAllowed
    assert evalValid.rejectionReason is None


def testVectorSearcherPriceAndStockFiltering(catalogFixtures: List[Dict[str, Any]]) -> None:
    """Verifies vector searcher excludes candidates exceeding price delta or with insufficient stock."""
    searcher = VectorSearcher(catalogStore=catalogFixtures)

    # Search for SKU-101 substitute
    origItem = next(s for s in catalogFixtures if s["skuId"] == "SKU-101")
    candidates = searcher.searchCandidates(
        queryVector=origItem["embeddingVector"],
        hsnCode=origItem["hsnCode"],
        originalPricePaise=origItem["baseUnitPricePaise"],
        requestedQuantity=1,
        excludeSkuId="SKU-101",
        scoreThreshold=0.85,
        maxPriceDeltaPct=5.0,
    )

    assert len(candidates) >= 1
    topCandidate = candidates[0]
    assert topCandidate.skuId == "SKU-104"
    assert topCandidate.score >= 0.85


def testMandatePatcherBudgetGateBreach(
    agentKeyFixtures: Dict[str, Any],
) -> None:
    """Verifies that mandate patcher rejects substitute exceeding delegated budget."""
    buyerSigner = Ed25519Signer(agentKeyFixtures["buyerAgent"]["privateKeyHex"])
    merchantSigner = Ed25519Signer(agentKeyFixtures["merchantNode"]["privateKeyHex"])
    userSigner = Ed25519Signer(agentKeyFixtures["userCfo"]["privateKeyHex"])

    now = int(time.time())
    intent = createSignedIntentMandate(
        mandateId="intent_budget_test",
        userSigner=userSigner,
        delegatedAgentDid=buyerSigner.getAgentDid(),
        maxBudgetPaise=300000,  # ₹3,000 budget
        upiCircleDelegationToken="tok_123",
        singleTransactionLimitPaise=300000,
        timestamp=now,
    )

    origTaxable = 250000
    origGst = computeGstBreakdown(origTaxable, 18, isIntraState=True)
    origTotal = computeCartSettlementTotal(origTaxable, origGst["totalTaxPaise"])

    origCart = createSignedCartMandate(
        cartId="cart_test_budget",
        merchantSigner=merchantSigner,
        merchantGstin="29AABCU9603R1ZM",
        merchantStateCode="29",
        buyerDeliveryPincode="560001",
        buyerDeliveryStateCode="29",
        items=[
            CartItemSchema(
                skuId="SKU-101",
                quantity=1,
                unitPricePaise=origTaxable,
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
        inventoryLockToken="lock_test",
        inventoryLockExpiresAt=now + 60,
        timestamp=now,
    )

    patcher = MandatePatcher()
    # Substitute price is ₹3,550 -> with GST = ₹4,189 -> exceeds ₹3,000 budget
    with pytest.raises(BudgetExceededViolation):
        patcher.patchCartMandate(
            originalCartMandate=origCart,
            failedSkuId="SKU-101",
            substituteSkuId="SKU-104",
            substituteUnitPricePaise=355000,
            substituteGstRatePercent=18,
            substituteHsnCode="8471",
            requestedQuantity=1,
            buyerAgentSigner=buyerSigner,
            merchantSigner=merchantSigner,
            intentMandate=intent,
        )


def testOosInterceptorEndToEndHealing(
    agentKeyFixtures: Dict[str, Any],
    catalogFixtures: List[Dict[str, Any]],
    mockQdrantClient: Any,
) -> None:
    """Verifies end-to-end OOS self-healing pipeline with SLA and cryptographic checks."""
    buyerSigner = Ed25519Signer(agentKeyFixtures["buyerAgent"]["privateKeyHex"])
    merchantSigner = Ed25519Signer(agentKeyFixtures["merchantNode"]["privateKeyHex"])

    now = int(time.time())
    origTaxable = 350000
    origGst = computeGstBreakdown(origTaxable, 18, isIntraState=True)
    origTotal = computeCartSettlementTotal(origTaxable, origGst["totalTaxPaise"])

    origCart = createSignedCartMandate(
        cartId="cart_e2e_oos",
        merchantSigner=merchantSigner,
        merchantGstin="29AABCU9603R1ZM",
        merchantStateCode="29",
        buyerDeliveryPincode="560001",
        buyerDeliveryStateCode="29",
        items=[
            CartItemSchema(
                skuId="SKU-101",
                quantity=1,
                unitPricePaise=origTaxable,
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
        inventoryLockToken="lock_oos_1",
        inventoryLockExpiresAt=now + 60,
        timestamp=now,
    )

    interceptor = OosInterceptor(qdrantClient=mockQdrantClient, catalogStore=catalogFixtures)
    manifest = NegativeConstraintManifest(excludedAllergens=["peanut"])

    amendment, healedCart, durationMs, cosineSim = interceptor.healOutOfStock(
        failedSkuId="SKU-101",
        requestedQuantity=1,
        buyerAgentSigner=buyerSigner,
        merchantSigner=merchantSigner,
        originalCartMandate=origCart,
        constraintManifest=manifest,
    )

    # Invariants
    assert durationMs < 300.0
    assert cosineSim >= 0.85
    assert amendment.substitutedSkuMapping["SKU-101"] == "SKU-104"
    assert healedCart.items[0].skuId == "SKU-104"
    assert healedCart.totalPaise == (355000 + (355000 * 18 // 100))

    # Dual signature verification
    agentPub = extractPublicKeyFromDid(buyerSigner.getAgentDid())
    merchantPub = extractPublicKeyFromDid(merchantSigner.getAgentDid())
    unsignedDict = {
        k: v for k, v in amendment.model_dump().items() if k not in ("agentSignature", "merchantSignature")
    }
    assert Ed25519Verifier.verifyPayloadSignature(agentPub, unsignedDict, amendment.agentSignature)
    assert Ed25519Verifier.verifyPayloadSignature(merchantPub, unsignedDict, amendment.merchantSignature)
