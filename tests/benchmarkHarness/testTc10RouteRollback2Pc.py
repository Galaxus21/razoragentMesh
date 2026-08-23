import time
from typing import Any, Dict
import pytest

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
    SettlementCompensationTriggeredException,
)
from razoragentMesh.packages.mandateEngine.settlementOrchestrator import (
    SettlementOrchestrator,
)

# Benchmark Constants
splitTotalPaise = 420000
merchantSplitPaise = 380000
protocolFeePaise = 2000
logisticsSplitPaise = 38000
failedLogisticsAccount = "acc_logistics_delhivery"


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

    # Step 1: Create valid mandates for ₹4,200 with ₹380 shipping
    intentMandate = createSignedIntentMandate(
        mandateId="intent_tc10_2pc",
        userSigner=userSigner,
        delegatedAgentDid=buyerSigner.getAgentDid(),
        maxBudgetPaise=5000000,
        upiCircleDelegationToken="upi_token_tc10",
        singleTransactionLimitPaise=1000000,
        timestamp=currentTime,
    )

    cartItem = CartItemSchema(
        skuId="SKU-001",
        quantity=1,
        unitPricePaise=382000,
        hsnCode="8504",
        gstRatePercent=0,
        lineTotalPaise=382000,
    )
    taxBreakdown = TaxBreakdownSchema(
        cgstPaise=0, sgstPaise=0, igstPaise=0, totalTaxPaise=0
    )

    cartMandate = createSignedCartMandate(
        cartId="cart_tc10_2pc",
        merchantSigner=merchantSigner,
        merchantGstin="29AABCU9603R1ZM",
        merchantStateCode="29",
        buyerDeliveryPincode="560001",
        buyerDeliveryStateCode="29",
        items=[cartItem],
        taxableSubtotalPaise=382000,
        taxBreakdown=taxBreakdown,
        shippingPaise=logisticsSplitPaise,  # ₹380 shipping
        discountPaise=0,
        totalPaise=splitTotalPaise,
        inventoryLockToken="lock_tc10_token",
        inventoryLockExpiresAt=currentTime + 60,
        timestamp=currentTime,
    )

    executionMandate = createSignedExecutionMandate(
        executionId="exec_tc10_2pc",
        buyerAgentSigner=buyerSigner,
        intentMandate=intentMandate,
        cartMandate=cartMandate,
        settlementAmountPaise=splitTotalPaise,
        upiCircleToken="upi_token_tc10",
        timestamp=currentTime,
    )

    # Step 2: Initialize Route Client & inject failure on secondary logistics transfer
    routeClient = RazorpayRouteClient(apiKey="rzp_mock_key", apiSecret="rzp_mock_secret")
    routeClient.simulatedFailureAccount = failedLogisticsAccount

    nonceLedger = NonceLedger(mockRedisClient)
    orchestrator = SettlementOrchestrator(
        routeClient=routeClient,
        nonceLedger=nonceLedger,
        protocolFeeAccount="acc_protocol_fee",
        protocolFeePaise=protocolFeePaise,
        logisticsAccount=failedLogisticsAccount,
    )

    # Step 3: Execute 2PC saga -> Failure triggers reverse_transfer compensation
    with pytest.raises(SettlementCompensationTriggeredException) as excInfo:
        await orchestrator.executeSettlementSaga(
            intentMandate=intentMandate,
            cartMandate=cartMandate,
            executionMandate=executionMandate,
            merchantAccount="acc_merchant_nexus_01",
            paymentId="pay_tc10_rollback_test",
            serverTime=currentTime,
        )

    assert "triggered rollback" in str(excInfo.value)

    # Step 4: Verify 2PC compensation invariant
    # Exactly 2 reversals recorded (protocol fee and merchant transfer)
    assert len(routeClient._reversals) == 2
    totalReversedPaise = sum(r.amount for r in routeClient._reversals.values())
    assert totalReversedPaise == (splitTotalPaise - logisticsSplitPaise)
    assert all(r.status == "processed" for r in routeClient._reversals.values())
