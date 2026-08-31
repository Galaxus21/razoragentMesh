import time
from typing import Any, Dict, List, Tuple
import pytest

from razoragentMesh.packages.mandateEngine.verification.budgetGate import validateBudgetGate
from razoragentMesh.packages.mandateEngine.mandates.cartMandateSchema import (
    CartItemSchema,
    TaxBreakdownSchema,
)
from razoragentMesh.packages.mandateEngine.crypto.ed25519Signer import Ed25519Signer
from razoragentMesh.packages.mandateEngine import (
    CartMandate,
    ExecutionMandate,
    IntentMandate,
)
from razoragentMesh.packages.mandateEngine.mandates.mandateFactory import (
    createSignedCartMandate,
    createSignedExecutionMandate,
    createSignedIntentMandate,
)
from razoragentMesh.packages.mandateEngine.nonce.nonceLedger import NonceLedger
from razoragentMesh.packages.mandateEngine.settlement.razorpayRouteClient import (
    RazorpayRouteClient,
)
from razoragentMesh.packages.mandateEngine.settlement.settlementExceptions import (
    BudgetExceededViolation,
    SingleTransactionLimitExceededException,
)
from razoragentMesh.packages.mandateEngine.settlement.settlementOrchestrator import (
    SettlementOrchestrator,
)

# Budget Gating Constants
delegatedBudgetCapPaise = 1000000  # ₹10,000 max budget
attemptedOverBudgetPaise = 1200000  # ₹12,000 attempted cart total
singleTxCeilingPaise = 1000000
overBudgetUnitPricePaise = 1200000


def _buildTc03BreachMandates(
    userSigner: Ed25519Signer, buyerSigner: Ed25519Signer, merchantSigner: Ed25519Signer,
    intentId: str, cartId: str, execId: str, maxBudgetPaise: int,
    singleLimitPaise: int, cartAmountPaise: int, skuId: str, currentTime: int,
) -> Tuple[IntentMandate, CartMandate, ExecutionMandate]:
    intentMandate = createSignedIntentMandate(
        mandateId=intentId, userSigner=userSigner, delegatedAgentDid=buyerSigner.getAgentDid(),
        maxBudgetPaise=maxBudgetPaise, upiCircleDelegationToken="upi_circle_tc03",
        singleTransactionLimitPaise=singleLimitPaise, timestamp=currentTime,
    )
    cartItem = CartItemSchema(skuId=skuId, quantity=1, unitPricePaise=cartAmountPaise, hsnCode="9026", gstRatePercent=0, lineTotalPaise=cartAmountPaise)
    taxBreakdown = TaxBreakdownSchema(cgstPaise=0, sgstPaise=0, igstPaise=0, totalTaxPaise=0)
    cartMandate = createSignedCartMandate(
        cartId=cartId, merchantSigner=merchantSigner, merchantGstin="29AABCU9603R1ZJ",
        merchantStateCode="29", buyerDeliveryPincode="560001", buyerDeliveryStateCode="29",
        items=[cartItem], taxableSubtotalPaise=cartAmountPaise, taxBreakdown=taxBreakdown,
        shippingPaise=0, discountPaise=0, totalPaise=cartAmountPaise,
        inventoryLockToken="lock_tc03_token", inventoryLockExpiresAt=currentTime + 60, timestamp=currentTime,
    )
    executionMandate = createSignedExecutionMandate(
        executionId=execId, buyerAgentSigner=buyerSigner, intentMandate=intentMandate,
        cartMandate=cartMandate, settlementAmountPaise=cartAmountPaise,
        upiCircleToken="upi_circle_tc03", timestamp=currentTime,
    )
    return intentMandate, cartMandate, executionMandate


@pytest.mark.asyncio
async def testTc03BudgetBreachDefense(
    agentKeyFixtures: Dict[str, Any],
    mockRedisClient: Any,
) -> None:
    """TC-03: Budget Breach Defense — Cart ₹12,000 vs Budget ₹10,000 raises BudgetExceededViolation, ₹0 charged."""
    userSigner = Ed25519Signer(agentKeyFixtures["userCfo"]["privateKeyHex"])
    buyerSigner = Ed25519Signer(agentKeyFixtures["buyerAgent"]["privateKeyHex"])
    merchantSigner = Ed25519Signer(agentKeyFixtures["merchantNode"]["privateKeyHex"])
    currentTime = int(time.time())

    intentM, cartM, execM = _buildTc03BreachMandates(
        userSigner, buyerSigner, merchantSigner,
        "intent_tc03_budget_cap", "cart_tc03_overbudget", "exec_tc03_breach",
        delegatedBudgetCapPaise, singleTxCeilingPaise, attemptedOverBudgetPaise, "SKU-014", currentTime,
    )

    with pytest.raises(BudgetExceededViolation) as excInfo:
        validateBudgetGate(intentMandate=intentM, cartMandate=cartM, executionMandate=execM, currentTimestamp=currentTime)
    assert "exceeds delegated budget" in str(excInfo.value)

    routeClient = RazorpayRouteClient(apiKey="rzp_mock_key", apiSecret="rzp_mock_secret")
    orchestrator = SettlementOrchestrator(routeClient=routeClient, nonceLedger=NonceLedger(mockRedisClient))

    with pytest.raises(BudgetExceededViolation):
        await orchestrator.executeSettlementSaga(
            intentMandate=intentM, cartMandate=cartM, executionMandate=execM,
            merchantAccount="acc_merchant_nexus_01", paymentId="pay_tc03_blocked", serverTime=currentTime,
        )

    assert len(routeClient._transfers) == 0 and len(routeClient._capturedPayments) == 0


def testTc03SingleTransactionLimitDefense(
    agentKeyFixtures: Dict[str, Any],
) -> None:
    """Verifies that exceeding single transaction limit raises SingleTransactionLimitExceededException."""
    userSigner = Ed25519Signer(agentKeyFixtures["userCfo"]["privateKeyHex"])
    buyerSigner = Ed25519Signer(agentKeyFixtures["buyerAgent"]["privateKeyHex"])
    merchantSigner = Ed25519Signer(agentKeyFixtures["merchantNode"]["privateKeyHex"])
    currentTime = int(time.time())

    intentM, cartM, execM = _buildTc03BreachMandates(
        userSigner, buyerSigner, merchantSigner,
        "intent_tc03_tx_limit", "cart_tc03_tx_breach", "exec_tc03_tx_breach",
        5000000, 500000, 800000, "SKU-009", currentTime,
    )

    with pytest.raises(SingleTransactionLimitExceededException):
        validateBudgetGate(intentMandate=intentM, cartMandate=cartM, executionMandate=execM, currentTimestamp=currentTime)

