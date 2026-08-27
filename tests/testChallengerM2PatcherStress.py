"""Empirical Challenger M2 Stress Suite for Mandate Patcher."""

import time
from typing import Any, Dict
import pytest

from razoragentMesh.packages.mandateEngine.crypto.cryptoKeyUtils import extractPublicKeyFromDid
from razoragentMesh.packages.mandateEngine.crypto.ed25519Signer import Ed25519Signer
from razoragentMesh.packages.mandateEngine.crypto.ed25519Verifier import Ed25519Verifier
from razoragentMesh.packages.mandateEngine.mandates.cartMandateSchema import (
    CartItemSchema,
    CartMandate,
    TaxBreakdownSchema,
)
from razoragentMesh.packages.mandateEngine.mandates.mandateFactory import (
    createSignedCartMandate,
    createSignedIntentMandate,
)
from razoragentMesh.packages.mandateEngine.settlement.settlementExceptions import (
    BudgetExceededViolation,
)
from razoragentMesh.packages.vectorHealer.src.patching.mandatePatcher import MandatePatcher

testMerchantGstin = "29AABCU9603R1ZJ"
testStateCode = "29"
testPincode = "560001"


def _createBaseTestCart(
    merchantSigner: Ed25519Signer,
    unitPricePaise: int,
    skuId: str = "SKU-ORIG-001",
) -> CartMandate:
    """Helper to construct signed base CartMandate for patching tests."""
    now = int(time.time())
    totalTax = (unitPricePaise * 18) // 100
    cgst, sgst = totalTax // 2, totalTax // 2
    item = CartItemSchema(
        skuId=skuId, quantity=1, unitPricePaise=unitPricePaise,
        hsnCode="84713010", gstRatePercent=18, lineTotalPaise=unitPricePaise,
    )
    taxBreakdown = TaxBreakdownSchema(
        cgstPaise=cgst, sgstPaise=sgst, igstPaise=0, totalTaxPaise=totalTax,
    )
    return createSignedCartMandate(
        cartId=f"cart_{skuId.lower()}", merchantSigner=merchantSigner,
        merchantGstin=testMerchantGstin, merchantStateCode=testStateCode,
        buyerDeliveryPincode=testPincode, buyerDeliveryStateCode=testStateCode,
        items=[item], taxableSubtotalPaise=unitPricePaise, taxBreakdown=taxBreakdown,
        shippingPaise=0, discountPaise=0, totalPaise=unitPricePaise + totalTax,
        inventoryLockToken="lock_base_001", inventoryLockExpiresAt=now + 60, timestamp=now,
    )


def testMandatePatcherCheaperAndExpensiveDeltas(agentKeyFixtures: Dict[str, Any]) -> None:
    """Verifies downward and upward price delta computations in patched mandates."""
    buyerSigner = Ed25519Signer(agentKeyFixtures["buyerAgent"]["privateKeyHex"])
    merchantSigner = Ed25519Signer(agentKeyFixtures["merchantNode"]["privateKeyHex"])
    origCart = _createBaseTestCart(merchantSigner, unitPricePaise=100000)
    patcher = MandatePatcher()

    amendCheap, healedCheap = patcher.patchCartMandate(
        originalCartMandate=origCart, failedSkuId="SKU-ORIG-001",
        substituteSkuId="SKU-SUB-CHEAP", substituteUnitPricePaise=80000,
        substituteGstRatePercent=18, substituteHsnCode="84713010",
        requestedQuantity=1, buyerAgentSigner=buyerSigner, merchantSigner=merchantSigner,
    )
    assert amendCheap.priceDeltaPaise == -20000
    assert healedCheap.totalPaise == 94400

    amendExp, healedExp = patcher.patchCartMandate(
        originalCartMandate=origCart, failedSkuId="SKU-ORIG-001",
        substituteSkuId="SKU-SUB-EXP", substituteUnitPricePaise=110000,
        substituteGstRatePercent=18, substituteHsnCode="84713010",
        requestedQuantity=1, buyerAgentSigner=buyerSigner, merchantSigner=merchantSigner,
    )
    assert amendExp.priceDeltaPaise == 10000
    assert healedExp.totalPaise == 129800


def testMandatePatcherEd25519DualSignatures(agentKeyFixtures: Dict[str, Any]) -> None:
    """Verifies Ed25519 dual signature chain and tamper resistance on amendment."""
    buyerSigner = Ed25519Signer(agentKeyFixtures["buyerAgent"]["privateKeyHex"])
    merchantSigner = Ed25519Signer(agentKeyFixtures["merchantNode"]["privateKeyHex"])
    origCart = _createBaseTestCart(merchantSigner, unitPricePaise=100000)
    patcher = MandatePatcher()

    amend, healed = patcher.patchCartMandate(
        originalCartMandate=origCart, failedSkuId="SKU-ORIG-001",
        substituteSkuId="SKU-SUB-01", substituteUnitPricePaise=105000,
        substituteGstRatePercent=18, substituteHsnCode="84713010",
        requestedQuantity=1, buyerAgentSigner=buyerSigner, merchantSigner=merchantSigner,
    )
    buyerPub = extractPublicKeyFromDid(buyerSigner.getAgentDid())
    merchPub = extractPublicKeyFromDid(merchantSigner.getAgentDid())
    unsignedDict = {
        k: v for k, v in amend.model_dump().items() if k not in ("agentSignature", "merchantSignature")
    }
    assert Ed25519Verifier.verifyPayloadSignature(buyerPub, unsignedDict, amend.agentSignature)
    assert Ed25519Verifier.verifyPayloadSignature(merchPub, unsignedDict, amend.merchantSignature)

    tampered = dict(unsignedDict)
    tampered["priceDeltaPaise"] = 999999
    assert not Ed25519Verifier.verifyPayloadSignature(buyerPub, tampered, amend.agentSignature)


def testMandatePatcherBudgetCeilingExactBoundary(agentKeyFixtures: Dict[str, Any]) -> None:
    """Stress-tests exact 1-paisa budget boundary condition on cart amendments."""
    buyerSigner = Ed25519Signer(agentKeyFixtures["buyerAgent"]["privateKeyHex"])
    merchantSigner = Ed25519Signer(agentKeyFixtures["merchantNode"]["privateKeyHex"])
    userSigner = Ed25519Signer(agentKeyFixtures["userCfo"]["privateKeyHex"])
    origCart = _createBaseTestCart(merchantSigner, unitPricePaise=100000)
    patcher = MandatePatcher()

    exactBudget = 118000
    intentExact = createSignedIntentMandate(
        mandateId="intent_exact_budget", userSigner=userSigner,
        delegatedAgentDid=buyerSigner.getAgentDid(), maxBudgetPaise=exactBudget,
        upiCircleDelegationToken="tok_exact", singleTransactionLimitPaise=exactBudget,
        timestamp=int(time.time()),
    )
    _, healed = patcher.patchCartMandate(
        originalCartMandate=origCart, failedSkuId="SKU-ORIG-001",
        substituteSkuId="SKU-SUB-EXACT", substituteUnitPricePaise=100000,
        substituteGstRatePercent=18, substituteHsnCode="84713010",
        requestedQuantity=1, buyerAgentSigner=buyerSigner, merchantSigner=merchantSigner,
        intentMandate=intentExact,
    )
    assert healed.totalPaise == exactBudget

    intentUnder = createSignedIntentMandate(
        mandateId="intent_under_budget", userSigner=userSigner,
        delegatedAgentDid=buyerSigner.getAgentDid(), maxBudgetPaise=exactBudget - 1,
        upiCircleDelegationToken="tok_under", singleTransactionLimitPaise=exactBudget - 1,
        timestamp=int(time.time()),
    )
    with pytest.raises(BudgetExceededViolation):
        patcher.patchCartMandate(
            originalCartMandate=origCart, failedSkuId="SKU-ORIG-001",
            substituteSkuId="SKU-SUB-EXACT", substituteUnitPricePaise=100000,
            substituteGstRatePercent=18, substituteHsnCode="84713010",
            requestedQuantity=1, buyerAgentSigner=buyerSigner, merchantSigner=merchantSigner,
            intentMandate=intentUnder,
        )
