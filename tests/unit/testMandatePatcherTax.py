"""Unit tests for Mandate Patcher tax calculations, GST slabs, and AP2 budget gates."""

import time
from typing import Any, Dict
import pytest

from razoragentMesh.packages.mandateEngine.crypto.ed25519Signer import Ed25519Signer
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
from razoragentMesh.packages.vectorHealer.src.patching.mandatePatcher import (
    MandatePatcher,
)

testMerchantGstin = "29AABCU9603R1ZJ"
testKarnatakaState = "29"
testDeliveryPincode = "560001"


def _createTaxTestCart(
    merchantSigner: Ed25519Signer,
    unitPricePaise: int,
    gstRatePercent: int = 18,
    skuId: str = "SKU-TAX-ORIG",
) -> CartMandate:
    """Helper to construct signed base CartMandate for tax patching tests."""
    now = int(time.time())
    totalTax = (unitPricePaise * gstRatePercent) // 100
    cgst, sgst = totalTax // 2, totalTax // 2
    item = CartItemSchema(
        skuId=skuId, quantity=1, unitPricePaise=unitPricePaise,
        hsnCode="84713010", gstRatePercent=gstRatePercent, lineTotalPaise=unitPricePaise,
    )
    taxBreakdown = TaxBreakdownSchema(
        cgstPaise=cgst, sgstPaise=sgst, igstPaise=0, totalTaxPaise=totalTax,
    )
    return createSignedCartMandate(
        cartId=f"cart_{skuId.lower()}", merchantSigner=merchantSigner,
        merchantGstin=testMerchantGstin, merchantStateCode=testKarnatakaState,
        buyerDeliveryPincode=testDeliveryPincode, buyerDeliveryStateCode=testKarnatakaState,
        items=[item], taxableSubtotalPaise=unitPricePaise, taxBreakdown=taxBreakdown,
        shippingPaise=0, discountPaise=0, totalPaise=unitPricePaise + totalTax,
        inventoryLockToken="lock_tax_token", inventoryLockExpiresAt=now + 60, timestamp=now,
    )


def testMandatePatcherBudgetGateExceededRejection(agentKeyFixtures: Dict[str, Any]) -> None:
    """Verifies that mandate patcher rejects substitute exceeding delegated budget."""
    buyerSigner = Ed25519Signer(agentKeyFixtures["buyerAgent"]["privateKeyHex"])
    merchantSigner = Ed25519Signer(agentKeyFixtures["merchantNode"]["privateKeyHex"])
    userSigner = Ed25519Signer(agentKeyFixtures["userCfo"]["privateKeyHex"])

    intent = createSignedIntentMandate(
        mandateId="intent_budget_test", userSigner=userSigner,
        delegatedAgentDid=buyerSigner.getAgentDid(), maxBudgetPaise=300000,
        upiCircleDelegationToken="tok_budget_123", singleTransactionLimitPaise=300000,
    )
    origCart = _createTaxTestCart(merchantSigner, unitPricePaise=250000, gstRatePercent=18)
    patcher = MandatePatcher()

    with pytest.raises(BudgetExceededViolation):
        patcher.patchCartMandate(
            originalCartMandate=origCart, failedSkuId="SKU-TAX-ORIG",
            substituteSkuId="SKU-SUB-EXPENSIVE", substituteUnitPricePaise=355000,
            substituteGstRatePercent=18, substituteHsnCode="8471",
            requestedQuantity=1, buyerAgentSigner=buyerSigner,
            merchantSigner=merchantSigner, intentMandate=intent,
        )


def testMandatePatcherBudgetCeilingExactMatch(agentKeyFixtures: Dict[str, Any]) -> None:
    """Tests exact budget boundary condition where healed total matches max budget."""
    buyerSigner = Ed25519Signer(agentKeyFixtures["buyerAgent"]["privateKeyHex"])
    merchantSigner = Ed25519Signer(agentKeyFixtures["merchantNode"]["privateKeyHex"])
    userSigner = Ed25519Signer(agentKeyFixtures["userCfo"]["privateKeyHex"])
    origCart = _createTaxTestCart(merchantSigner, unitPricePaise=100000)
    patcher = MandatePatcher()

    exactBudget = 118000
    intentExact = createSignedIntentMandate(
        mandateId="intent_exact_budget", userSigner=userSigner,
        delegatedAgentDid=buyerSigner.getAgentDid(), maxBudgetPaise=exactBudget,
        upiCircleDelegationToken="tok_exact", singleTransactionLimitPaise=exactBudget,
    )
    _, healed = patcher.patchCartMandate(
        originalCartMandate=origCart, failedSkuId="SKU-TAX-ORIG",
        substituteSkuId="SKU-SUB-EXACT", substituteUnitPricePaise=100000,
        substituteGstRatePercent=18, substituteHsnCode="84713010",
        requestedQuantity=1, buyerAgentSigner=buyerSigner,
        merchantSigner=merchantSigner, intentMandate=intentExact,
    )
    assert healed.totalPaise == exactBudget


def testMandatePatcherBudgetCeiling1PaisaDeficit(agentKeyFixtures: Dict[str, Any]) -> None:
    """Tests 1-paisa budget boundary deficit rejection."""
    buyerSigner = Ed25519Signer(agentKeyFixtures["buyerAgent"]["privateKeyHex"])
    merchantSigner = Ed25519Signer(agentKeyFixtures["merchantNode"]["privateKeyHex"])
    userSigner = Ed25519Signer(agentKeyFixtures["userCfo"]["privateKeyHex"])
    origCart = _createTaxTestCart(merchantSigner, unitPricePaise=100000)
    patcher = MandatePatcher()

    intentUnder = createSignedIntentMandate(
        mandateId="intent_under_budget", userSigner=userSigner,
        delegatedAgentDid=buyerSigner.getAgentDid(), maxBudgetPaise=117999,
        upiCircleDelegationToken="tok_under", singleTransactionLimitPaise=117999,
    )
    with pytest.raises(BudgetExceededViolation):
        patcher.patchCartMandate(
            originalCartMandate=origCart, failedSkuId="SKU-TAX-ORIG",
            substituteSkuId="SKU-SUB-EXACT", substituteUnitPricePaise=100000,
            substituteGstRatePercent=18, substituteHsnCode="84713010",
            requestedQuantity=1, buyerAgentSigner=buyerSigner,
            merchantSigner=merchantSigner, intentMandate=intentUnder,
        )


def testMandatePatcherIntraStateGstRecalculation(agentKeyFixtures: Dict[str, Any]) -> None:
    """Verifies statutory 50/50 CGST + SGST recalculation on substituted item."""
    buyerSigner = Ed25519Signer(agentKeyFixtures["buyerAgent"]["privateKeyHex"])
    merchantSigner = Ed25519Signer(agentKeyFixtures["merchantNode"]["privateKeyHex"])
    origCart = _createTaxTestCart(merchantSigner, unitPricePaise=100000)
    patcher = MandatePatcher()

    _, healed = patcher.patchCartMandate(
        originalCartMandate=origCart, failedSkuId="SKU-TAX-ORIG",
        substituteSkuId="SKU-SUB-INTRA", substituteUnitPricePaise=200000,
        substituteGstRatePercent=18, substituteHsnCode="84713010",
        requestedQuantity=1, buyerAgentSigner=buyerSigner, merchantSigner=merchantSigner,
    )

    assert healed.taxableSubtotalPaise == 200000
    assert healed.taxBreakdown.cgstPaise == 18000
    assert healed.taxBreakdown.sgstPaise == 18000
    assert healed.taxBreakdown.igstPaise == 0
    assert healed.taxBreakdown.totalTaxPaise == 36000
    assert healed.totalPaise == 236000


def testMandatePatcherMultiSlabTaxConservation(agentKeyFixtures: Dict[str, Any]) -> None:
    """Verifies tax recalculation across standard GST slabs (5% and 28%)."""
    buyerSigner = Ed25519Signer(agentKeyFixtures["buyerAgent"]["privateKeyHex"])
    merchantSigner = Ed25519Signer(agentKeyFixtures["merchantNode"]["privateKeyHex"])
    origCart = _createTaxTestCart(merchantSigner, unitPricePaise=100000)
    patcher = MandatePatcher()

    _, healed28 = patcher.patchCartMandate(
        originalCartMandate=origCart, failedSkuId="SKU-TAX-ORIG",
        substituteSkuId="SKU-SUB-28", substituteUnitPricePaise=100000,
        substituteGstRatePercent=28, substituteHsnCode="8703",
        requestedQuantity=1, buyerAgentSigner=buyerSigner, merchantSigner=merchantSigner,
    )
    assert healed28.taxBreakdown.cgstPaise == 14000
    assert healed28.taxBreakdown.sgstPaise == 14000
    assert healed28.taxBreakdown.totalTaxPaise == 28000
    assert healed28.totalPaise == 128000

    _, healed5 = patcher.patchCartMandate(
        originalCartMandate=origCart, failedSkuId="SKU-TAX-ORIG",
        substituteSkuId="SKU-SUB-05", substituteUnitPricePaise=100000,
        substituteGstRatePercent=5, substituteHsnCode="3004",
        requestedQuantity=1, buyerAgentSigner=buyerSigner, merchantSigner=merchantSigner,
    )
    assert healed5.taxBreakdown.cgstPaise == 2500
    assert healed5.taxBreakdown.sgstPaise == 2500
    assert healed5.totalPaise == 105000


def testMandatePatcherZeroRatedExemptSubstitute(agentKeyFixtures: Dict[str, Any]) -> None:
    """Verifies tax recalculation when substituting with a 0% GST exempt good."""
    buyerSigner = Ed25519Signer(agentKeyFixtures["buyerAgent"]["privateKeyHex"])
    merchantSigner = Ed25519Signer(agentKeyFixtures["merchantNode"]["privateKeyHex"])
    origCart = _createTaxTestCart(merchantSigner, unitPricePaise=50000)
    patcher = MandatePatcher()

    _, healedExempt = patcher.patchCartMandate(
        originalCartMandate=origCart, failedSkuId="SKU-TAX-ORIG",
        substituteSkuId="SKU-SUB-EXEMPT", substituteUnitPricePaise=60000,
        substituteGstRatePercent=0, substituteHsnCode="0401",
        requestedQuantity=1, buyerAgentSigner=buyerSigner, merchantSigner=merchantSigner,
    )

    assert healedExempt.taxableSubtotalPaise == 60000
    assert healedExempt.taxBreakdown.cgstPaise == 0
    assert healedExempt.taxBreakdown.sgstPaise == 0
    assert healedExempt.taxBreakdown.igstPaise == 0
    assert healedExempt.taxBreakdown.totalTaxPaise == 0
    assert healedExempt.totalPaise == 60000


def testMandatePatcherOddPaiseGstRoundingConservation(agentKeyFixtures: Dict[str, Any]) -> None:
    """Verifies integer division tax conservation on odd-paise amounts."""
    buyerSigner = Ed25519Signer(agentKeyFixtures["buyerAgent"]["privateKeyHex"])
    merchantSigner = Ed25519Signer(agentKeyFixtures["merchantNode"]["privateKeyHex"])
    origCart = _createTaxTestCart(merchantSigner, unitPricePaise=100000)
    patcher = MandatePatcher()

    _, healed = patcher.patchCartMandate(
        originalCartMandate=origCart, failedSkuId="SKU-TAX-ORIG",
        substituteSkuId="SKU-SUB-ODD", substituteUnitPricePaise=33333,
        substituteGstRatePercent=18, substituteHsnCode="84713010",
        requestedQuantity=1, buyerAgentSigner=buyerSigner, merchantSigner=merchantSigner,
    )

    assert healed.taxableSubtotalPaise == 33333
    assert healed.taxBreakdown.cgstPaise == 2999
    assert healed.taxBreakdown.sgstPaise == 2999
    assert healed.taxBreakdown.totalTaxPaise == 5998
    assert healed.totalPaise == 39331
