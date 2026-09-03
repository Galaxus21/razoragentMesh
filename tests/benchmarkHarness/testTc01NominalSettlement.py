import time
from typing import Any, Dict, List, Tuple
import pytest

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
from razoragentMesh.packages.mandateEngine.settlement.settlementOrchestrator import (
    SettlementOrchestrator,
)

# Benchmark Constants
nominalSkuId = "SKU-001"
nominalQuantity = 1
nominalUnitPricePaise = 420000
nominalGstRate = 18
nominalGstin = "29AABCU9603R1ZJ"
nominalStateCode = "29"
nominalPincode = "560001"
nominalMaxBudgetPaise = 5000000
nominalSingleTxLimitPaise = 1000000
nominalUpiToken = "upi_circle_token_tc01"
nominalMerchantAccount = "acc_merchant_nexus_01"


async def _performTc01InventoryLock(mockRedisClient: Any, catalogFixtures: List[Dict[str, Any]], lockToken: str) -> None:
    skuRecord = next(s for s in catalogFixtures if s["skuId"] == nominalSkuId)
    initialStock = skuRecord["availableStock"]
    assert initialStock > 0
    stockKey = f"sku:{nominalSkuId}:stock"
    fencingKey = f"sku:{nominalSkuId}:fence"
    evalResult = await mockRedisClient.eval("", 2, stockKey, fencingKey, nominalQuantity, lockToken, 60)
    assert evalResult[0] == 1 and evalResult[1] >= 1
    remainingStock = int(await mockRedisClient.get(stockKey) or 0)
    assert remainingStock == initialStock - nominalQuantity


def _buildTc01Mandates(
    userSigner: Ed25519Signer, buyerSigner: Ed25519Signer, merchantSigner: Ed25519Signer,
    lockToken: str, currentTime: int,
) -> Tuple[IntentMandate, CartMandate, ExecutionMandate, int]:
    intentMandate = createSignedIntentMandate(
        mandateId="intent_mandate_tc01", userSigner=userSigner,
        delegatedAgentDid=buyerSigner.getAgentDid(), maxBudgetPaise=nominalMaxBudgetPaise,
        upiCircleDelegationToken=nominalUpiToken, singleTransactionLimitPaise=nominalSingleTxLimitPaise,
        authorizedCategories=["industrial_electronics"], timestamp=currentTime,
    )
    taxableSubtotal = nominalUnitPricePaise * nominalQuantity
    halfRate = nominalGstRate // 2
    cgstPaise = (taxableSubtotal * halfRate) // 100
    totalTaxPaise = cgstPaise * 2
    totalPaise = taxableSubtotal + totalTaxPaise

    cartItem = CartItemSchema(
        category="industrial_electronics",
        skuId=nominalSkuId, quantity=nominalQuantity, unitPricePaise=nominalUnitPricePaise,
        hsnCode="8504", gstRatePercent=nominalGstRate, lineTotalPaise=taxableSubtotal,
    )
    taxBreakdown = TaxBreakdownSchema(cgstPaise=cgstPaise, sgstPaise=cgstPaise, igstPaise=0, totalTaxPaise=totalTaxPaise)
    cartMandate = createSignedCartMandate(
        cartId="cart_mandate_tc01", merchantSigner=merchantSigner, merchantGstin=nominalGstin,
        merchantStateCode=nominalStateCode, buyerDeliveryPincode=nominalPincode,
        buyerDeliveryStateCode=nominalStateCode, items=[cartItem], taxableSubtotalPaise=taxableSubtotal,
        taxBreakdown=taxBreakdown, shippingPaise=0, discountPaise=0, totalPaise=totalPaise,
        inventoryLockToken=lockToken, inventoryLockExpiresAt=currentTime + 60, timestamp=currentTime,
    )
    executionMandate = createSignedExecutionMandate(
        executionId="exec_mandate_tc01", buyerAgentSigner=buyerSigner, intentMandate=intentMandate,
        cartMandate=cartMandate, settlementAmountPaise=totalPaise, upiCircleToken=nominalUpiToken,
        timestamp=currentTime,
    )
    return intentMandate, cartMandate, executionMandate, totalPaise


@pytest.mark.asyncio
async def testNominalA2aSettlementHandshake(
    agentKeyFixtures: Dict[str, Any], catalogFixtures: List[Dict[str, Any]], mockRedisClient: Any,
) -> None:
    """TC-01: Nominal A2A Settlement Handshake — Discovery to 60s lock to AP2 signing to ₹4,200 settlement."""
    userSigner = Ed25519Signer(agentKeyFixtures["userCfo"]["privateKeyHex"])
    buyerSigner = Ed25519Signer(agentKeyFixtures["buyerAgent"]["privateKeyHex"])
    merchantSigner = Ed25519Signer(agentKeyFixtures["merchantNode"]["privateKeyHex"])

    lockToken = "lock_token_uuid_tc01"
    await _performTc01InventoryLock(mockRedisClient, catalogFixtures, lockToken)

    currentTime = int(time.time())
    intentM, cartM, execM, totalPaise = _buildTc01Mandates(userSigner, buyerSigner, merchantSigner, lockToken, currentTime)

    orchestrator = SettlementOrchestrator(
        routeClient=RazorpayRouteClient(apiKey="rzp_test_123", apiSecret="rzp_secret_456"),
        nonceLedger=NonceLedger(mockRedisClient),
    )
    settlementResult = await orchestrator.executeSettlementSaga(
        intentMandate=intentM, cartMandate=cartM, executionMandate=execM,
        merchantAccount=nominalMerchantAccount, paymentId="pay_tc01_capture_success", serverTime=currentTime,
    )
    assert settlementResult.status == "captured" and settlementResult.amountPaise == totalPaise
    assert len(settlementResult.transfers) >= 1 and len(settlementResult.invoice.cryptographicAuditHash) == 64
    assert settlementResult.invoice.grandTotalPaise == totalPaise

