import time
from typing import Any, Dict, List
import pytest

from razoragentMesh.packages.mandateEngine.budgetGate import validateBudgetGate
from razoragentMesh.packages.mandateEngine.cartMandateSchema import (
    CartItemSchema,
    TaxBreakdownSchema,
)
from razoragentMesh.packages.mandateEngine.ed25519Signer import Ed25519Signer
from razoragentMesh.packages.mandateEngine.mandateFactory import (
    createSignedCartMandate,
    createSignedExecutionMandate,
    createSignedIntentMandate,
)
from razoragentMesh.packages.mandateEngine.nonceLedger import NonceLedger
from razoragentMesh.packages.mandateEngine.razorpayRouteClient import (
    RazorpayRouteClient,
)
from razoragentMesh.packages.mandateEngine.settlementExceptions import (
    BudgetExceededViolation,
    SingleTransactionLimitExceededException,
)
from razoragentMesh.packages.mandateEngine.settlementOrchestrator import (
    SettlementOrchestrator,
)

# Budget Gating Constants
delegatedBudgetCapPaise = 1000000  # ₹10,000 max budget
attemptedOverBudgetPaise = 1200000  # ₹12,000 attempted cart total
singleTxCeilingPaise = 1000000
overBudgetUnitPricePaise = 1200000


@pytest.mark.asyncio
async def testTc03BudgetBreachDefense(
    agentKeyFixtures: Dict[str, Any],
    mockRedisClient: Any,
) -> None:
    """TC-03: Budget Breach Defense — Cart ₹12,000 vs Budget ₹10,000 raises BudgetExceededViolation, ₹0 charged."""
    userKey = agentKeyFixtures["userCfo"]
    buyerKey = agentKeyFixtures["buyerAgent"]
    merchantKey = agentKeyFixtures["merchantNode"]

    userSigner = Ed25519Signer(userKey["privateKeyHex"])
    buyerSigner = Ed25519Signer(buyerKey["privateKeyHex"])
    merchantSigner = Ed25519Signer(merchantKey["privateKeyHex"])

    currentTime = int(time.time())

    # Step 1: Principal delegates ₹10,000 budget cap
    intentMandate = createSignedIntentMandate(
        mandateId="intent_tc03_budget_cap",
        userSigner=userSigner,
        delegatedAgentDid=buyerSigner.getAgentDid(),
        maxBudgetPaise=delegatedBudgetCapPaise,
        upiCircleDelegationToken="upi_circle_tc03",
        singleTransactionLimitPaise=singleTxCeilingPaise,
        timestamp=currentTime,
    )

    # Step 2: Merchant signs cart totaling ₹12,000 (breach of budget cap)
    cartItem = CartItemSchema(
        skuId="SKU-014",
        quantity=1,
        unitPricePaise=attemptedOverBudgetPaise,
        hsnCode="9026",
        gstRatePercent=0,
        lineTotalPaise=attemptedOverBudgetPaise,
    )
    taxBreakdown = TaxBreakdownSchema(
        cgstPaise=0, sgstPaise=0, igstPaise=0, totalTaxPaise=0
    )

    cartMandate = createSignedCartMandate(
        cartId="cart_tc03_overbudget",
        merchantSigner=merchantSigner,
        merchantGstin="29AABCU9603R1ZM",
        merchantStateCode="29",
        buyerDeliveryPincode="560001",
        buyerDeliveryStateCode="29",
        items=[cartItem],
        taxableSubtotalPaise=attemptedOverBudgetPaise,
        taxBreakdown=taxBreakdown,
        shippingPaise=0,
        discountPaise=0,
        totalPaise=attemptedOverBudgetPaise,
        inventoryLockToken="lock_tc03_token",
        inventoryLockExpiresAt=currentTime + 60,
        timestamp=currentTime,
    )

    executionMandate = createSignedExecutionMandate(
        executionId="exec_tc03_breach",
        buyerAgentSigner=buyerSigner,
        intentMandate=intentMandate,
        cartMandate=cartMandate,
        settlementAmountPaise=attemptedOverBudgetPaise,
        upiCircleToken="upi_circle_tc03",
        timestamp=currentTime,
    )

    # Step 3: Verify budget gate directly intercepts breach
    with pytest.raises(BudgetExceededViolation) as excInfo:
        validateBudgetGate(
            intentMandate=intentMandate,
            cartMandate=cartMandate,
            executionMandate=executionMandate,
            currentTimestamp=currentTime,
        )
    assert "exceeds delegated budget" in str(excInfo.value)

    # Step 4: Verify Settlement Orchestrator aborts before invoking Razorpay Route API
    routeClient = RazorpayRouteClient(apiKey="rzp_mock_key", apiSecret="rzp_mock_secret")
    nonceLedger = NonceLedger(mockRedisClient)
    orchestrator = SettlementOrchestrator(
        routeClient=routeClient,
        nonceLedger=nonceLedger,
    )

    with pytest.raises(BudgetExceededViolation):
        await orchestrator.executeSettlementSaga(
            intentMandate=intentMandate,
            cartMandate=cartMandate,
            executionMandate=executionMandate,
            merchantAccount="acc_merchant_nexus_01",
            paymentId="pay_tc03_blocked",
            serverTime=currentTime,
        )

    # Critical Invariant: Zero API transfers executed, ₹0 charged
    assert len(routeClient._transfers) == 0
    assert len(routeClient._capturedPayments) == 0


def testTc03SingleTransactionLimitDefense(
    agentKeyFixtures: Dict[str, Any],
) -> None:
    """Verifies that exceeding single transaction limit raises SingleTransactionLimitExceededException."""
    userSigner = Ed25519Signer(agentKeyFixtures["userCfo"]["privateKeyHex"])
    buyerSigner = Ed25519Signer(agentKeyFixtures["buyerAgent"]["privateKeyHex"])
    merchantSigner = Ed25519Signer(agentKeyFixtures["merchantNode"]["privateKeyHex"])

    currentTime = int(time.time())

    # Total budget ₹50,000, but single transaction limit is ₹5,000
    intentMandate = createSignedIntentMandate(
        mandateId="intent_tc03_tx_limit",
        userSigner=userSigner,
        delegatedAgentDid=buyerSigner.getAgentDid(),
        maxBudgetPaise=5000000,
        upiCircleDelegationToken="upi_circle_tc03",
        singleTransactionLimitPaise=500000,  # ₹5,000 ceiling
        timestamp=currentTime,
    )

    # Cart is ₹8,000 (within ₹50k budget, but exceeds ₹5k single limit)
    cartItem = CartItemSchema(
        skuId="SKU-009",
        quantity=1,
        unitPricePaise=800000,
        hsnCode="8517",
        gstRatePercent=0,
        lineTotalPaise=800000,
    )
    taxBreakdown = TaxBreakdownSchema(
        cgstPaise=0, sgstPaise=0, igstPaise=0, totalTaxPaise=0
    )

    cartMandate = createSignedCartMandate(
        cartId="cart_tc03_tx_breach",
        merchantSigner=merchantSigner,
        merchantGstin="29AABCU9603R1ZM",
        merchantStateCode="29",
        buyerDeliveryPincode="560001",
        buyerDeliveryStateCode="29",
        items=[cartItem],
        taxableSubtotalPaise=800000,
        taxBreakdown=taxBreakdown,
        shippingPaise=0,
        discountPaise=0,
        totalPaise=800000,
        inventoryLockToken="lock_tc03_tx_token",
        inventoryLockExpiresAt=currentTime + 60,
        timestamp=currentTime,
    )

    executionMandate = createSignedExecutionMandate(
        executionId="exec_tc03_tx_breach",
        buyerAgentSigner=buyerSigner,
        intentMandate=intentMandate,
        cartMandate=cartMandate,
        settlementAmountPaise=800000,
        upiCircleToken="upi_circle_tc03",
        timestamp=currentTime,
    )

    with pytest.raises(SingleTransactionLimitExceededException):
        validateBudgetGate(
            intentMandate=intentMandate,
            cartMandate=cartMandate,
            executionMandate=executionMandate,
            currentTimestamp=currentTime,
        )
