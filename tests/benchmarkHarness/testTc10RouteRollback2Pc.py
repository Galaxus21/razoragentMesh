import time
from typing import Any, Dict
import pytest

from razoragentMesh.packages.mandateEngine.mandates.cartMandateSchema import (
    CartItemSchema,
    TaxBreakdownSchema,
)
from razoragentMesh.packages.mandateEngine.crypto.ed25519Signer import Ed25519Signer
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
    SettlementCompensationTriggeredException,
)
from razoragentMesh.packages.mandateEngine.settlement.settlementOrchestrator import (
    SettlementOrchestrator,
)

# Benchmark Constants
splitTotalPaise = 420000
merchantSplitPaise = 380000
protocolFeePaise = 2000
logisticsSplitPaise = 38000
failedLogisticsAccount = "acc_logistics_delhivery"


def _buildTc10RollbackMandates(
    userSigner: Ed25519Signer, buyerSigner: Ed25519Signer, merchantSigner: Ed25519Signer, currentTime: int,
) -> Tuple[IntentMandate, CartMandate, ExecutionMandate]:
    intentMandate = createSignedIntentMandate(
        mandateId="intent_tc10_2pc", userSigner=userSigner, delegatedAgentDid=buyerSigner.getAgentDid(),
        maxBudgetPaise=5000000, upiCircleDelegationToken="upi_token_tc10",
        singleTransactionLimitPaise=1000000, timestamp=currentTime,
    )
    cartItem = CartItemSchema(skuId="SKU-001", quantity=1, unitPricePaise=382000, hsnCode="8504", gstRatePercent=0, lineTotalPaise=382000)
    taxBreakdown = TaxBreakdownSchema(cgstPaise=0, sgstPaise=0, igstPaise=0, totalTaxPaise=0)
    cartMandate = createSignedCartMandate(
        cartId="cart_tc10_2pc", merchantSigner=merchantSigner, merchantGstin="29AABCU9603R1ZJ",
        merchantStateCode="29", buyerDeliveryPincode="560001", buyerDeliveryStateCode="29",
        items=[cartItem], taxableSubtotalPaise=382000, taxBreakdown=taxBreakdown,
        shippingPaise=logisticsSplitPaise, discountPaise=0, totalPaise=splitTotalPaise,
        inventoryLockToken="lock_tc10_token", inventoryLockExpiresAt=currentTime + 60, timestamp=currentTime,
    )
    executionMandate = createSignedExecutionMandate(
        executionId="exec_tc10_2pc", buyerAgentSigner=buyerSigner, intentMandate=intentMandate,
        cartMandate=cartMandate, settlementAmountPaise=splitTotalPaise,
        upiCircleToken="upi_token_tc10", timestamp=currentTime,
    )
    return intentMandate, cartMandate, executionMandate


@pytest.mark.asyncio
async def testTc10RouteRollback2pcSagaCompensation(
    agentKeyFixtures: Dict[str, Any],
    mockRedisClient: Any,
) -> None:
    """TC-10: Route Rollback 2PC — Route split transfer failure triggers 2PC reverse_transfer rollback."""
    userSigner = Ed25519Signer(agentKeyFixtures["userCfo"]["privateKeyHex"])
    buyerSigner = Ed25519Signer(agentKeyFixtures["buyerAgent"]["privateKeyHex"])
    merchantSigner = Ed25519Signer(agentKeyFixtures["merchantNode"]["privateKeyHex"])
    currentTime = int(time.time())

    intentM, cartM, execM = _buildTc10RollbackMandates(userSigner, buyerSigner, merchantSigner, currentTime)

    routeClient = RazorpayRouteClient(apiKey="rzp_mock_key", apiSecret="rzp_mock_secret")
    routeClient.simulatedFailureAccount = failedLogisticsAccount
    orchestrator = SettlementOrchestrator(
        routeClient=routeClient, nonceLedger=NonceLedger(mockRedisClient),
        protocolFeeAccount="acc_protocol_fee", protocolFeePaise=protocolFeePaise,
        logisticsAccount=failedLogisticsAccount,
    )

    with pytest.raises(SettlementCompensationTriggeredException) as excInfo:
        await orchestrator.executeSettlementSaga(
            intentMandate=intentM, cartMandate=cartM, executionMandate=execM,
            merchantAccount="acc_merchant_nexus_01", paymentId="pay_tc10_rollback_test", serverTime=currentTime,
        )

    assert "triggered rollback" in str(excInfo.value)
    assert len(routeClient._reversals) == 2
    totalReversedPaise = sum(r.amount for r in routeClient._reversals.values())
    assert totalReversedPaise == (splitTotalPaise - logisticsSplitPaise)
    assert all(r.status == "processed" for r in routeClient._reversals.values())

