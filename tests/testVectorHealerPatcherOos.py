"""Unit and integration tests for Layer 3 vectorHealer patching and OOS interception."""

import time
from typing import Any, Dict, List
import pytest

from razoragentMesh.packages.mandateEngine.verification.arithmeticEnclave import (
    computeCartSettlementTotal,
    computeGstBreakdown,
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
    createSignedCartMandate,
    createSignedIntentMandate,
)
from razoragentMesh.packages.mandateEngine.settlement.settlementExceptions import (
    BudgetExceededViolation,
)
from razoragentMesh.packages.vectorHealer.src.constraints import (
    NegativeConstraintManifest,
)
from razoragentMesh.packages.vectorHealer.src.interception import (
    OosInterceptor,
)
from razoragentMesh.packages.vectorHealer.src.patching import (
    MandatePatcher,
    generateCartDiff,
)


def _buildSampleCart(merchantSigner: Ed25519Signer, cartId: str, taxable: int, gstRate: int = 18) -> CartMandate:
    now = int(time.time())
    gst = computeGstBreakdown(taxable, gstRate, isIntraState=True)
    total = computeCartSettlementTotal(taxable, gst["totalTaxPaise"])
    item = CartItemSchema(
        skuId="SKU-101", quantity=1, unitPricePaise=taxable,
        hsnCode="8471", gstRatePercent=gstRate, lineTotalPaise=taxable,
    )
    tb = TaxBreakdownSchema(cgstPaise=gst["cgstPaise"], sgstPaise=gst["sgstPaise"], igstPaise=0, totalTaxPaise=gst["totalTaxPaise"])
    return createSignedCartMandate(
        cartId=cartId, merchantSigner=merchantSigner, merchantGstin="29AABCU9603R1ZJ",
        merchantStateCode="29", buyerDeliveryPincode="560001", buyerDeliveryStateCode="29",
        items=[item], taxableSubtotalPaise=taxable, taxBreakdown=tb, shippingPaise=0,
        discountPaise=0, totalPaise=total, inventoryLockToken="lock_test",
        inventoryLockExpiresAt=now + 60, timestamp=now,
    )


def testMandatePatcherBudgetGateBreach(agentKeyFixtures: Dict[str, Any]) -> None:
    """Verifies that mandate patcher rejects substitute exceeding delegated budget."""
    buyerSigner = Ed25519Signer(agentKeyFixtures["buyerAgent"]["privateKeyHex"])
    merchantSigner = Ed25519Signer(agentKeyFixtures["merchantNode"]["privateKeyHex"])
    userSigner = Ed25519Signer(agentKeyFixtures["userCfo"]["privateKeyHex"])
    now = int(time.time())

    intent = createSignedIntentMandate(
        mandateId="intent_budget_test", userSigner=userSigner,
        delegatedAgentDid=buyerSigner.getAgentDid(), maxBudgetPaise=300000,
        upiCircleDelegationToken="tok_123", singleTransactionLimitPaise=300000, timestamp=now,
    )
    origCart = _buildSampleCart(merchantSigner, "cart_test_budget", 250000)
    patcher = MandatePatcher()

    with pytest.raises(BudgetExceededViolation):
        patcher.patchCartMandate(
            originalCartMandate=origCart, failedSkuId="SKU-101", substituteSkuId="SKU-104",
            substituteUnitPricePaise=355000, substituteGstRatePercent=18, substituteHsnCode="8471",
            requestedQuantity=1, buyerAgentSigner=buyerSigner, merchantSigner=merchantSigner,
            intentMandate=intent,
        )


def testOosInterceptorEndToEndHealing(agentKeyFixtures: Dict[str, Any], catalogFixtures: List[Dict[str, Any]], mockQdrantClient: Any) -> None:
    """Verifies end-to-end OOS self-healing pipeline with SLA and cryptographic checks."""
    buyerSigner = Ed25519Signer(agentKeyFixtures["buyerAgent"]["privateKeyHex"])
    merchantSigner = Ed25519Signer(agentKeyFixtures["merchantNode"]["privateKeyHex"])
    origCart = _buildSampleCart(merchantSigner, "cart_e2e_oos", 350000)

    interceptor = OosInterceptor(qdrantClient=mockQdrantClient, catalogStore=catalogFixtures)
    manifest = NegativeConstraintManifest(excludedAllergens=["peanut"])
    amendment, healedCart, durationMs, cosineSim = interceptor.healOutOfStock(
        failedSkuId="SKU-101", requestedQuantity=1, buyerAgentSigner=buyerSigner,
        merchantSigner=merchantSigner, originalCartMandate=origCart, constraintManifest=manifest,
    )
    assert durationMs < 300.0 and cosineSim >= 0.85
    assert amendment.substitutedSkuMapping["SKU-101"] == "SKU-104" and healedCart.items[0].skuId == "SKU-104"
    assert healedCart.totalPaise == (355000 + (355000 * 18 // 100))

    agentPub = extractPublicKeyFromDid(buyerSigner.getAgentDid())
    merchantPub = extractPublicKeyFromDid(merchantSigner.getAgentDid())
    unsignedDict = {k: v for k, v in amendment.model_dump().items() if k not in ("agentSignature", "merchantSignature")}
    assert Ed25519Verifier.verifyPayloadSignature(agentPub, unsignedDict, amendment.agentSignature)
    assert Ed25519Verifier.verifyPayloadSignature(merchantPub, unsignedDict, amendment.merchantSignature)


def testGenerateCartDiffCalculation(agentKeyFixtures: Dict[str, Any]) -> None:
    """Verifies that generateCartDiff accurately computes price delta in paise."""
    merchantSigner = Ed25519Signer(agentKeyFixtures["merchantNode"]["privateKeyHex"])
    cart = _buildSampleCart(merchantSigner, "cart_diff_test", 50000)
    diffPaise = generateCartDiff(originalCartMandate=cart, failedSkuId="SKU-101", substituteUnitPricePaise=55000)
    assert diffPaise == 5000

    diffNonExistent = generateCartDiff(originalCartMandate=cart, failedSkuId="SKU-UNKNOWN", substituteUnitPricePaise=55000)
    assert diffNonExistent == 55000
