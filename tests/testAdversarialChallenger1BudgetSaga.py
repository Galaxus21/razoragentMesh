"""Challenger 1: Budget Gate and 2PC Settlement Saga Invariant Tests.

Tests:
1. Budget Gate Invariants & Breach Interception
2. Two-Phase Commit (2PC) Settlement Saga Compensation
"""

from typing import Any, Dict
import pytest

from razoragentMesh.packages.mandateEngine.verification.arithmeticEnclave import (
    computeGstBreakdown,
)
from razoragentMesh.packages.mandateEngine.verification.budgetGate import validateBudgetGate
from razoragentMesh.packages.mandateEngine.mandates.cartMandateSchema import (
    CartItemSchema,
    CartMandate,
    TaxBreakdownSchema,
)
from razoragentMesh.packages.mandateEngine.crypto.ed25519Signer import Ed25519Signer
from razoragentMesh.packages.mandateEngine.mandates.executionMandateSchema import ExecutionMandate
from razoragentMesh.packages.mandateEngine.mandates.intentMandateSchema import IntentMandate
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
    ArithmeticEnclaveMismatchException,
    BudgetExceededViolation,
    CategoryNotAuthorizedException,
    MandateExpiredException,
    SingleTransactionLimitExceededException,
    SettlementCompensationTriggeredException,
)
from razoragentMesh.packages.mandateEngine.settlement.settlementOrchestrator import (
    SettlementOrchestrator,
)


def _buildCartAndExecution(
    merchantSigner: Ed25519Signer,
    buyerSigner: Ed25519Signer,
    intentMandate: IntentMandate,
    itemUnitPrice: int,
    itemQuantity: int,
    taxPercent: int,
    shipping: int,
    discount: int,
    claimedCartTotal: int,
    claimedSettlementAmt: int,
    currentTime: int,
) -> tuple[CartMandate, ExecutionMandate]:
    subtotal = itemUnitPrice * itemQuantity
    tb = computeGstBreakdown(subtotal, taxPercent, isIntraState=True)
    item = CartItemSchema(
        skuId="SKU-STRESS-01", quantity=itemQuantity, unitPricePaise=itemUnitPrice,
        hsnCode="8471", gstRatePercent=taxPercent, lineTotalPaise=subtotal,
    )
    tbSchema = TaxBreakdownSchema(
        cgstPaise=tb["cgstPaise"], sgstPaise=tb["sgstPaise"],
        igstPaise=tb["igstPaise"], totalTaxPaise=tb["totalTaxPaise"],
    )
    cart = createSignedCartMandate(
        cartId="cart_gate_stress", merchantSigner=merchantSigner,
        merchantGstin="29AABCU9603R1ZJ", merchantStateCode="29",
        buyerDeliveryPincode="560001", buyerDeliveryStateCode="29",
        items=[item], taxableSubtotalPaise=subtotal, taxBreakdown=tbSchema,
        shippingPaise=shipping, discountPaise=discount, totalPaise=claimedCartTotal,
        inventoryLockToken="lock_gate_token", inventoryLockExpiresAt=currentTime + 60,
        timestamp=currentTime,
    )
    execM = createSignedExecutionMandate(
        executionId="exec_gate_stress", buyerAgentSigner=buyerSigner,
        intentMandate=intentMandate, cartMandate=cart,
        settlementAmountPaise=claimedSettlementAmt, upiCircleToken="upi_token_gate",
        timestamp=currentTime,
    )
    return cart, execM


class TestBudgetGateBreachDefense:
    """Empirical stress tests for AP2 BudgetGate constraints."""

    @pytest.fixture
    def setupMandates(self, agentKeyFixtures: Dict[str, Any]):
        userKey = agentKeyFixtures["userCfo"]
        buyerKey = agentKeyFixtures["buyerAgent"]
        merchantKey = agentKeyFixtures["merchantNode"]
        userSigner = Ed25519Signer(userKey["privateKeyHex"])
        buyerSigner = Ed25519Signer(buyerKey["privateKeyHex"])
        merchantSigner = Ed25519Signer(merchantKey["privateKeyHex"])
        currentTime = 1755936000

        intentMandate = createSignedIntentMandate(
            mandateId="intent_gate_test", userSigner=userSigner,
            delegatedAgentDid=buyerSigner.getAgentDid(), maxBudgetPaise=1000000,
            upiCircleDelegationToken="upi_token_gate", singleTransactionLimitPaise=500000,
            authorizedCategories=["electronics", "office_supplies"],
            validUntilTimestamp=currentTime + 3600, timestamp=currentTime,
        )
        return {
            "userSigner": userSigner, "buyerSigner": buyerSigner,
            "merchantSigner": merchantSigner, "intentMandate": intentMandate,
            "currentTime": currentTime,
        }

    def testBudgetCapExactBoundaries(self, setupMandates: Dict[str, Any]) -> None:
        """Tests exact boundary conditions for max budget cap and single transaction limit."""
        ctx = setupMandates
        cart, execM = _buildCartAndExecution(
            ctx["merchantSigner"], ctx["buyerSigner"], ctx["intentMandate"],
            500000, 1, 0, 0, 0, 500000, 500000, ctx["currentTime"],
        )
        assert validateBudgetGate(ctx["intentMandate"], cart, execM, ctx["currentTime"]) is True

        cartOver, execOver = _buildCartAndExecution(
            ctx["merchantSigner"], ctx["buyerSigner"], ctx["intentMandate"],
            500001, 1, 0, 0, 0, 500001, 500001, ctx["currentTime"],
        )
        with pytest.raises(SingleTransactionLimitExceededException):
            validateBudgetGate(ctx["intentMandate"], cartOver, execOver, ctx["currentTime"])

    def testArithmeticDriftMismatchedCartAndExecutionTotals(self, setupMandates: Dict[str, Any]) -> None:
        """Tests detection of arithmetic tampering in cart or execution amounts."""
        ctx = setupMandates
        cartTampered, execTampered = _buildCartAndExecution(
            ctx["merchantSigner"], ctx["buyerSigner"], ctx["intentMandate"],
            100000, 1, 0, 0, 0, 90000, 90000, ctx["currentTime"],
        )
        with pytest.raises(ArithmeticEnclaveMismatchException):
            validateBudgetGate(ctx["intentMandate"], cartTampered, execTampered, ctx["currentTime"])

    def testMandateExpirationBoundary(self, setupMandates: Dict[str, Any]) -> None:
        """Tests exact expiration boundary."""
        ctx = setupMandates
        validUntil = ctx["intentMandate"].validUntilTimestamp
        cart, execM = _buildCartAndExecution(
            ctx["merchantSigner"], ctx["buyerSigner"], ctx["intentMandate"],
            100000, 1, 0, 0, 0, 100000, 100000, validUntil,
        )
        assert validateBudgetGate(ctx["intentMandate"], cart, execM, currentTimestamp=validUntil) is True
        with pytest.raises(MandateExpiredException):
            validateBudgetGate(ctx["intentMandate"], cart, execM, currentTimestamp=validUntil + 1)

    def testUnauthorizedCategoryRejection(self, setupMandates: Dict[str, Any]) -> None:
        """Tests rejection when unauthorized categories are present."""
        ctx = setupMandates
        cart, execM = _buildCartAndExecution(
            ctx["merchantSigner"], ctx["buyerSigner"], ctx["intentMandate"],
            100000, 1, 0, 0, 0, 100000, 100000, ctx["currentTime"],
        )
        with pytest.raises(CategoryNotAuthorizedException):
            validateBudgetGate(ctx["intentMandate"], cart, execM, ctx["currentTime"], skuCategories=["electronics", "luxury_jewelry"])

    @pytest.mark.asyncio
    async def testSettlementSagaAbortsOnBudgetBreachWithZeroDebited(
        self,
        setupMandates: Dict[str, Any],
        mockRedisClient: Any,
    ) -> None:
        """Asserts that settlement saga blocks on budget breach, resulting in 0 captures and 0 transfers."""
        ctx = setupMandates
        cartOverBudget, execOverBudget = _buildCartAndExecution(
            ctx["merchantSigner"], ctx["buyerSigner"], ctx["intentMandate"],
            1500000, 1, 0, 0, 0, 1500000, 1500000, ctx["currentTime"],
        )
        routeClient = RazorpayRouteClient()
        orchestrator = SettlementOrchestrator(
            routeClient=routeClient, nonceLedger=NonceLedger(mockRedisClient),
        )
        with pytest.raises(BudgetExceededViolation):
            await orchestrator.executeSettlementSaga(
                intentMandate=ctx["intentMandate"], cartMandate=cartOverBudget,
                executionMandate=execOverBudget, merchantAccount="acc_merchant_nexus_01",
                paymentId="pay_budget_breach_intercept", serverTime=ctx["currentTime"],
            )
        assert len(routeClient._capturedPayments) == 0
        assert len(routeClient._transfers) == 0


def _build2pcTriplets(
    agentKeyFixtures: Dict[str, Any],
    failureStep: str,
    shippingFee: int,
    currentTime: int,
) -> tuple[IntentMandate, CartMandate, ExecutionMandate, int, int]:
    userSigner = Ed25519Signer(agentKeyFixtures["userCfo"]["privateKeyHex"])
    buyerSigner = Ed25519Signer(agentKeyFixtures["buyerAgent"]["privateKeyHex"])
    merchantSigner = Ed25519Signer(agentKeyFixtures["merchantNode"]["privateKeyHex"])
    unitPrice = 380000 if failureStep == "logistics" else 420000
    totalPaise = unitPrice + shippingFee

    intentMandate = createSignedIntentMandate(
        mandateId=f"intent_2pc_{failureStep}_fail", userSigner=userSigner,
        delegatedAgentDid=buyerSigner.getAgentDid(), maxBudgetPaise=1000000,
        upiCircleDelegationToken="upi_tok_2pc", singleTransactionLimitPaise=1000000,
        timestamp=currentTime,
    )
    cartItem = CartItemSchema(
        skuId="SKU-001", quantity=1, unitPricePaise=unitPrice,
        hsnCode="8504", gstRatePercent=0, lineTotalPaise=unitPrice,
    )
    cartMandate = createSignedCartMandate(
        cartId=f"cart_2pc_{failureStep}_fail", merchantSigner=merchantSigner,
        merchantGstin="29AABCU9603R1ZJ", merchantStateCode="29",
        buyerDeliveryPincode="560001", buyerDeliveryStateCode="29",
        items=[cartItem], taxableSubtotalPaise=unitPrice,
        taxBreakdown=TaxBreakdownSchema(cgstPaise=0, sgstPaise=0, igstPaise=0, totalTaxPaise=0),
        shippingPaise=shippingFee, discountPaise=0, totalPaise=totalPaise,
        inventoryLockToken=f"lock_2pc_{failureStep}", inventoryLockExpiresAt=currentTime + 60,
        timestamp=currentTime,
    )
    execMandate = createSignedExecutionMandate(
        executionId=f"exec_2pc_{failureStep}_fail", buyerAgentSigner=buyerSigner,
        intentMandate=intentMandate, cartMandate=cartMandate,
        settlementAmountPaise=totalPaise, upiCircleToken="upi_tok_2pc",
        timestamp=currentTime,
    )
    return intentMandate, cartMandate, execMandate, unitPrice, totalPaise


def _verify2pcReversals(routeClient: RazorpayRouteClient, failureStep: str, unitPrice: int, totalPaise: int, protocolFee: int) -> None:
    if failureStep == "protocolFee":
        assert list(routeClient._reversals.values())[0].amount == (totalPaise - protocolFee)
    elif failureStep == "logistics":
        reversedAmounts = [r.amount for r in routeClient._reversals.values()]
        assert (unitPrice - protocolFee) in reversedAmounts and protocolFee in reversedAmounts


class TestTwoPhaseCommitSettlementRollback:
    """Empirical stress tests for 2PC Settlement Saga compensation and rollback."""

    @pytest.mark.asyncio
    @pytest.mark.parametrize(
        "failureStep,simulatedFailAcc,protocolFee,shippingFee,expectedRollbacks,expectedTransfers,expectedReversals",
        [
            ("merchant", "acc_merchant_fail_01", 0, 0, 0, 0, 0),
            ("protocolFee", "acc_protocol_fee", 50, 0, 1, 1, 1),
            ("logistics", "acc_logistics_delhivery", 2000, 38000, 2, 2, 2),
        ],
    )
    async def test2pcSettlementSagaRollbackLifoSequenceMatrix(
        self,
        failureStep: str,
        simulatedFailAcc: str,
        protocolFee: int,
        shippingFee: int,
        expectedRollbacks: int,
        expectedTransfers: int,
        expectedReversals: int,
        agentKeyFixtures: Dict[str, Any],
        mockRedisClient: Any,
    ) -> None:
        """Tests saga LIFO compensation matrix for failure at steps 1, 2, and 3."""
        currentTime = 1755936000
        intent, cart, execM, unitPrice, totalPaise = _build2pcTriplets(
            agentKeyFixtures, failureStep, shippingFee, currentTime,
        )
        routeClient = RazorpayRouteClient()
        routeClient.simulatedFailureAccount = simulatedFailAcc
        orchestrator = SettlementOrchestrator(
            routeClient=routeClient, nonceLedger=NonceLedger(mockRedisClient),
            protocolFeeAccount="acc_protocol_fee" if protocolFee > 0 else "acc_proto_default",
            protocolFeePaise=protocolFee, logisticsAccount="acc_logistics_delhivery",
        )
        with pytest.raises(SettlementCompensationTriggeredException) as excInfo:
            await orchestrator.executeSettlementSaga(
                intentMandate=intent, cartMandate=cart, executionMandate=execM,
                merchantAccount=simulatedFailAcc if failureStep == "merchant" else "acc_merchant_valid_01",
                paymentId=f"pay_2pc_{failureStep}_fail", serverTime=currentTime,
            )
        assert f"triggered rollback of {expectedRollbacks} transfers" in str(excInfo.value)
        assert len(routeClient._transfers) == expectedTransfers
        assert len(routeClient._reversals) == expectedReversals
        _verify2pcReversals(routeClient, failureStep, unitPrice, totalPaise, protocolFee)
