import time
from typing import Any, Dict, List
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
from razoragentMesh.packages.mandateEngine.settlementOrchestrator import (
    SettlementOrchestrator,
)

# Benchmark Constants
nominalSkuId = "SKU-001"
nominalQuantity = 1
nominalUnitPricePaise = 420000
nominalGstRate = 18
nominalGstin = "29AABCU9603R1ZM"
nominalStateCode = "29"
nominalPincode = "560001"
nominalMaxBudgetPaise = 5000000
nominalSingleTxLimitPaise = 1000000
nominalUpiToken = "upi_circle_token_tc01"
nominalMerchantAccount = "acc_merchant_nexus_01"


@pytest.mark.asyncio
async def testNominalA2aSettlementHandshake(
    agentKeyFixtures: Dict[str, Any],
    catalogFixtures: List[Dict[str, Any]],
    mockRedisClient: Any,
) -> None:
    """TC-01: Nominal A2A Settlement Handshake — Discovery to 60s lock to AP2 signing to ₹4,200 settlement."""
    userKey = agentKeyFixtures["userCfo"]
    buyerKey = agentKeyFixtures["buyerAgent"]
    merchantKey = agentKeyFixtures["merchantNode"]

    userSigner = Ed25519Signer(userKey["privateKeyHex"])
    buyerSigner = Ed25519Signer(buyerKey["privateKeyHex"])
    merchantSigner = Ed25519Signer(merchantKey["privateKeyHex"])

    # Step 1: Query catalog & verify SKU-001
    skuRecord = next(s for s in catalogFixtures if s["skuId"] == nominalSkuId)
    initialStock = skuRecord["availableStock"]
    assert initialStock > 0

    # Step 2: Atomic 60s inventory lock in Redis Lua
    stockKey = f"sku:{nominalSkuId}:stock"
    fencingKey = f"sku:{nominalSkuId}:fence"
    lockToken = "lock_token_uuid_tc01"
    evalResult = await mockRedisClient.eval(
        "", 2, stockKey, fencingKey, nominalQuantity, lockToken, 60
    )
    assert evalResult[0] == 1
    assert evalResult[1] >= 1

    remainingStock = int(await mockRedisClient.get(stockKey) or 0)
    assert remainingStock == initialStock - nominalQuantity

    # Step 3: AP2 Cryptographic Mandate Signing Chain
    currentTime = int(time.time())
    intentMandate = createSignedIntentMandate(
        mandateId="intent_mandate_tc01",
        userSigner=userSigner,
        delegatedAgentDid=buyerSigner.getAgentDid(),
        maxBudgetPaise=nominalMaxBudgetPaise,
        upiCircleDelegationToken=nominalUpiToken,
        singleTransactionLimitPaise=nominalSingleTxLimitPaise,
        authorizedCategories=["industrial_electronics"],
        timestamp=currentTime,
    )

    # Taxable subtotal and 18% intra-state GST calculation in integer paise
    taxableSubtotal = nominalUnitPricePaise * nominalQuantity
    halfRate = nominalGstRate // 2
    cgstPaise = (taxableSubtotal * halfRate) // 100
    sgstPaise = cgstPaise
    totalTaxPaise = cgstPaise + sgstPaise
    totalPaise = taxableSubtotal + totalTaxPaise

    cartItem = CartItemSchema(
        skuId=nominalSkuId,
        quantity=nominalQuantity,
        unitPricePaise=nominalUnitPricePaise,
        hsnCode="8504",
        gstRatePercent=nominalGstRate,
        lineTotalPaise=taxableSubtotal,
    )
    taxBreakdown = TaxBreakdownSchema(
        cgstPaise=cgstPaise,
        sgstPaise=sgstPaise,
        igstPaise=0,
        totalTaxPaise=totalTaxPaise,
    )

    cartMandate = createSignedCartMandate(
        cartId="cart_mandate_tc01",
        merchantSigner=merchantSigner,
        merchantGstin=nominalGstin,
        merchantStateCode=nominalStateCode,
        buyerDeliveryPincode=nominalPincode,
        buyerDeliveryStateCode=nominalStateCode,
        items=[cartItem],
        taxableSubtotalPaise=taxableSubtotal,
        taxBreakdown=taxBreakdown,
        shippingPaise=0,
        discountPaise=0,
        totalPaise=totalPaise,
        inventoryLockToken=lockToken,
        inventoryLockExpiresAt=currentTime + 60,
        timestamp=currentTime,
    )

    executionMandate = createSignedExecutionMandate(
        executionId="exec_mandate_tc01",
        buyerAgentSigner=buyerSigner,
        intentMandate=intentMandate,
        cartMandate=cartMandate,
        settlementAmountPaise=totalPaise,
        upiCircleToken=nominalUpiToken,
        timestamp=currentTime,
    )

    # Step 4: 2PC Settlement Saga Orchestration
    routeClient = RazorpayRouteClient(apiKey="rzp_test_123", apiSecret="rzp_secret_456")
    nonceLedger = NonceLedger(mockRedisClient)
    orchestrator = SettlementOrchestrator(
        routeClient=routeClient,
        nonceLedger=nonceLedger,
    )

    settlementResult = await orchestrator.executeSettlementSaga(
        intentMandate=intentMandate,
        cartMandate=cartMandate,
        executionMandate=executionMandate,
        merchantAccount=nominalMerchantAccount,
        paymentId="pay_tc01_capture_success",
        serverTime=currentTime,
    )

    # Step 5: Verify all TC-01 Invariants
    assert settlementResult.status == "captured"
    assert settlementResult.amountPaise == totalPaise
    assert len(settlementResult.transfers) >= 1
    assert settlementResult.invoice.cryptographicAuditHash is not None
    assert len(settlementResult.invoice.cryptographicAuditHash) == 64
    assert settlementResult.invoice.grandTotalPaise == totalPaise
