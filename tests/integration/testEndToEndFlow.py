import time
from typing import Any, Dict, List
import pytest

from razoragentMesh.packages.catalogSanitizer.catalogSanitizer import (
    sanitizeMerchantSkuQuote,
)
from razoragentMesh.packages.mandateEngine.verification.budgetGate import validateBudgetGate
from razoragentMesh.packages.mandateEngine.mandates.cartMandateSchema import (
    CartItemSchema,
    TaxBreakdownSchema,
)
from razoragentMesh.packages.mandateEngine.crypto.ed25519Signer import Ed25519Signer
from razoragentMesh.packages.mandateEngine.mandates.mandateFactory import (
    createSignedCartMandate,
    createSignedExecutionMandate,
    createSignedIntentMandate,
    verifyMandateHashChain,
)
from razoragentMesh.packages.mandateEngine.nonce.nonceLedger import NonceLedger
from razoragentMesh.packages.mandateEngine.settlement.razorpayRouteClient import (
    RazorpayRouteClient,
)
from razoragentMesh.packages.mandateEngine.settlement.settlementOrchestrator import (
    SettlementOrchestrator,
)

# Integration Constants
targetSkuId = "SKU-001"
orderQuantity = 10  # Triggers volume discount tier (5% discount)
baseUnitPricePaise = 420000  # ₹4,200
discountBps = 500  # 5.00% discount
discountPaisePerUnit = (baseUnitPricePaise * discountBps) // 10000  # 21,000 paise
offeredUnitPricePaise = baseUnitPricePaise - discountPaisePerUnit  # 399,000 paise (₹3,990)
gstRate = 18
delegatedBudgetPaise = 5000000  # ₹50,000 budget cap


@pytest.mark.asyncio
async def testEndToEndAutonomousProcurementFlow(
    agentKeyFixtures: Dict[str, Any],
    catalogFixtures: List[Dict[str, Any]],
    mockRedisClient: Any,
) -> None:
    """End-to-End Integration Test: Full Layer 0 -> Layer 1 -> Layer 4 autonomous settlement flow."""
    userKey = agentKeyFixtures["userCfo"]
    buyerKey = agentKeyFixtures["buyerAgent"]
    merchantKey = agentKeyFixtures["merchantNode"]

    userSigner = Ed25519Signer(userKey["privateKeyHex"])
    buyerSigner = Ed25519Signer(buyerKey["privateKeyHex"])
    merchantSigner = Ed25519Signer(merchantKey["privateKeyHex"])

    currentTime = int(time.time())

    # --- Phase 1: Layer 0 Ingress Catalog Sanitization ---
    rawMerchantQuote = {
        "skuId": targetSkuId,
        "title": "Ultra Precision Pressure Sensor X1\u200B\u200C",  # Hidden zero-width injection
        "description": "Industrial [sensor](https://malicious.link) <script>alert(1)</script>",
        "availableStock": 50,
        "baseUnitPricePaise": baseUnitPricePaise,
        "offeredUnitPricePaise": offeredUnitPricePaise,
        "currency": "INR",
        "hsnCode": "8504",
        "gstRatePercent": gstRate,
        "taxBreakdown": {
            "cgstPaise": 359100,
            "sgstPaise": 359100,
            "igstPaise": 0,
            "totalTaxPaise": 718200,
        },
        "quoteExpiryTimestamp": currentTime + 300,
        "quoteHash": "a" * 64,
    }
    sanitizedQuote = sanitizeMerchantSkuQuote(rawMerchantQuote)
    assert "\u200b" not in sanitizedQuote.title
    assert "<script>" not in sanitizedQuote.description

    # --- Phase 2: IntentMandate Delegation (AP2) ---
    intentMandate = createSignedIntentMandate(
        mandateId="intent_e2e_001",
        userSigner=userSigner,
        delegatedAgentDid=buyerSigner.getAgentDid(),
        maxBudgetPaise=delegatedBudgetPaise,
        upiCircleDelegationToken="upi_circle_e2e_token",
        singleTransactionLimitPaise=delegatedBudgetPaise,
        authorizedCategories=["industrial_electronics"],
        timestamp=currentTime,
    )

    # --- Phase 3: Inventory Lock Reservation (Layer 1 Redis Lua) ---
    stockKey = f"sku:{targetSkuId}:stock"
    fencingKey = f"sku:{targetSkuId}:fence"
    lockToken = "lock_e2e_uuid_001"

    lockStatus, fencingToken = await mockRedisClient.eval(
        "", 2, stockKey, fencingKey, orderQuantity, lockToken, 60
    )
    assert lockStatus == 1
    assert fencingToken >= 1

    # --- Phase 4: CartMandate Construction & Merchant Signing ---
    taxableSubtotal = offeredUnitPricePaise * orderQuantity  # 39,900,000 paise (₹39,900)
    cgstPaise = (taxableSubtotal * (gstRate // 2)) // 100  # 3,591,000 paise
    sgstPaise = cgstPaise
    totalTaxPaise = cgstPaise + sgstPaise  # 7,182,000 paise
    totalGrossPaise = taxableSubtotal + totalTaxPaise  # 47,082,000 paise (₹47,082)

    cartItem = CartItemSchema(
        skuId=targetSkuId,
        quantity=orderQuantity,
        unitPricePaise=offeredUnitPricePaise,
        hsnCode="8504",
        gstRatePercent=gstRate,
        lineTotalPaise=taxableSubtotal,
    )
    taxBreakdown = TaxBreakdownSchema(
        cgstPaise=cgstPaise,
        sgstPaise=sgstPaise,
        igstPaise=0,
        totalTaxPaise=totalTaxPaise,
    )

    cartMandate = createSignedCartMandate(
        cartId="cart_e2e_001",
        merchantSigner=merchantSigner,
        merchantGstin="29AABCU9603R1ZM",
        merchantStateCode="29",
        buyerDeliveryPincode="560001",
        buyerDeliveryStateCode="29",
        items=[cartItem],
        taxableSubtotalPaise=taxableSubtotal,
        taxBreakdown=taxBreakdown,
        shippingPaise=0,
        discountPaise=0,
        totalPaise=totalGrossPaise,
        inventoryLockToken=lockToken,
        inventoryLockExpiresAt=currentTime + 60,
        timestamp=currentTime,
    )

    # --- Phase 5: ExecutionMandate Chained Commitment (Layer 4) ---
    executionMandate = createSignedExecutionMandate(
        executionId="exec_e2e_001",
        buyerAgentSigner=buyerSigner,
        intentMandate=intentMandate,
        cartMandate=cartMandate,
        settlementAmountPaise=totalGrossPaise,
        upiCircleToken="upi_circle_e2e_token",
        timestamp=currentTime,
    )

    # Verify Hash Chain & Budget Gate
    assert verifyMandateHashChain(intentMandate, cartMandate, executionMandate) is True
    assert validateBudgetGate(intentMandate, cartMandate, executionMandate, currentTime) is True

    # --- Phase 6: 2PC Settlement Saga Execution ---
    routeClient = RazorpayRouteClient(apiKey="rzp_e2e_key", apiSecret="rzp_e2e_secret")
    nonceLedger = NonceLedger(mockRedisClient)
    orchestrator = SettlementOrchestrator(
        routeClient=routeClient,
        nonceLedger=nonceLedger,
    )

    result = await orchestrator.executeSettlementSaga(
        intentMandate=intentMandate,
        cartMandate=cartMandate,
        executionMandate=executionMandate,
        merchantAccount="acc_merchant_nexus_01",
        paymentId="pay_e2e_settlement_001",
        serverTime=currentTime,
    )

    # Final Invariants Verification
    assert result.status == "captured"
    assert result.amountPaise == totalGrossPaise
    assert len(result.transfers) >= 1
    assert result.invoice.grandTotalPaise == totalGrossPaise
    assert len(result.invoice.cryptographicAuditHash) == 64
