"""Integration test fixtures, signers, builders, and orchestrator factories."""

from dataclasses import dataclass
import time
from typing import Any, Dict, Optional, Tuple

from razoragentMesh.packages.mandateEngine.crypto.ed25519Signer import Ed25519Signer
from razoragentMesh.packages.mandateEngine.mandates.cartMandateSchema import (
    CartItemSchema,
    CartMandate,
    TaxBreakdownSchema,
)
from razoragentMesh.packages.mandateEngine.mandates.executionMandateSchema import (
    ExecutionMandate,
)
from razoragentMesh.packages.mandateEngine.mandates.intentMandateSchema import (
    IntentMandate,
)
from razoragentMesh.packages.mandateEngine.mandates.mandateFactory import (
    createSignedCartMandate,
    createSignedExecutionMandate,
)
from razoragentMesh.packages.mandateEngine.nonce.nonceLedger import NonceLedger
from razoragentMesh.packages.mandateEngine.settlement.razorpayRouteClient import (
    RazorpayRouteClient,
)
from razoragentMesh.packages.mandateEngine.settlement.settlementOrchestrator import (
    SettlementOrchestrator,
)


@dataclass
class IntegrationSigners:
    """Container holding Ed25519 cryptographic signers for all protocol actors."""

    userSigner: Ed25519Signer
    buyerSigner: Ed25519Signer
    merchantSigner: Ed25519Signer


# Integration Constants
targetSkuId: str = "SKU-001"
orderQuantity: int = 10
baseUnitPricePaise: int = 420000
discountBps: int = 500
discountPaisePerUnit: int = (baseUnitPricePaise * discountBps) // 10000
offeredUnitPricePaise: int = baseUnitPricePaise - discountPaisePerUnit
gstRate: int = 18
delegatedBudgetPaise: int = 5000000
defaultMerchantAccount: str = "acc_merchant_nexus_01"
defaultMerchantGstin: str = "29AABCU9603R1ZJ"
defaultMerchantState: str = "29"
defaultBuyerPincode: str = "560001"
defaultBuyerState: str = "29"
defaultHsnCode: str = "8504"
defaultCategory: str = "industrial_electronics"
defaultUpiToken: str = "upi_circle_e2e_token"
defaultLockToken: str = "lock_e2e_uuid_001"


def setupIntegrationSigners(agentKeyFixtures: Dict[str, Any]) -> IntegrationSigners:
    """Initializes Ed25519 signers for user CFO, buyer agent, and merchant node."""
    userKey = agentKeyFixtures["userCfo"]
    buyerKey = agentKeyFixtures["buyerAgent"]
    merchantKey = agentKeyFixtures["merchantNode"]
    return IntegrationSigners(
        userSigner=Ed25519Signer(userKey["privateKeyHex"]),
        buyerSigner=Ed25519Signer(buyerKey["privateKeyHex"]),
        merchantSigner=Ed25519Signer(merchantKey["privateKeyHex"]),
    )


def buildRawMerchantQuote(
    skuId: str = targetSkuId,
    basePrice: int = baseUnitPricePaise,
    offeredPrice: int = offeredUnitPricePaise,
    gst: int = gstRate,
    currentTime: int = 0,
) -> Dict[str, Any]:
    """Builds a raw merchant SKU quote payload containing prompt injection test patterns."""
    timestamp = currentTime if currentTime > 0 else int(time.time())
    cgstAmount = (offeredPrice * (gst // 2)) // 100
    sgstAmount = (offeredPrice * (gst // 2)) // 100
    return {
        "skuId": skuId,
        "title": "Ultra Precision Pressure Sensor X1\u200B\u200C",
        "description": "Industrial [sensor](https://malicious.link) <script>alert(1)</script>",
        "availableStock": 50,
        "baseUnitPricePaise": basePrice,
        "offeredUnitPricePaise": offeredPrice,
        "currency": "INR",
        "hsnCode": defaultHsnCode,
        "gstRatePercent": gst,
        "taxBreakdown": {
            "cgstPaise": cgstAmount,
            "sgstPaise": sgstAmount,
            "igstPaise": 0,
            "totalTaxPaise": cgstAmount + sgstAmount,
        },
        "quoteExpiryTimestamp": timestamp + 300,
        "quoteHash": "a" * 64,
    }


def buildStandardCartMandate(
    signers: IntegrationSigners,
    lockToken: str = defaultLockToken,
    currentTime: int = 0,
    quantity: int = orderQuantity,
    unitPricePaise: int = offeredUnitPricePaise,
    cartId: str = "cart_e2e_001",
) -> Tuple[CartMandate, int]:
    """Constructs and cryptographically signs a valid single-item CartMandate."""
    timestamp = currentTime if currentTime > 0 else int(time.time())
    taxableSubtotal = unitPricePaise * quantity
    cgstPaise = (taxableSubtotal * (gstRate // 2)) // 100
    totalTaxPaise = cgstPaise * 2
    totalGrossPaise = taxableSubtotal + totalTaxPaise

    cartItem = CartItemSchema(
        skuId=targetSkuId, quantity=quantity, unitPricePaise=unitPricePaise,
        hsnCode=defaultHsnCode, gstRatePercent=gstRate, lineTotalPaise=taxableSubtotal,
    )
    taxBreakdown = TaxBreakdownSchema(
        cgstPaise=cgstPaise, sgstPaise=cgstPaise, igstPaise=0, totalTaxPaise=totalTaxPaise,
    )
    cartMandate = createSignedCartMandate(
        cartId=cartId, merchantSigner=signers.merchantSigner,
        merchantGstin=defaultMerchantGstin, merchantStateCode=defaultMerchantState,
        buyerDeliveryPincode=defaultBuyerPincode, buyerDeliveryStateCode=defaultBuyerState,
        items=[cartItem], taxableSubtotalPaise=taxableSubtotal, taxBreakdown=taxBreakdown,
        shippingPaise=0, discountPaise=0, totalPaise=totalGrossPaise,
        inventoryLockToken=lockToken, inventoryLockExpiresAt=timestamp + 60, timestamp=timestamp,
    )
    return cartMandate, totalGrossPaise


def buildStandardExecutionMandate(
    buyerSigner: Ed25519Signer,
    intentMandate: IntentMandate,
    cartMandate: CartMandate,
    totalGrossPaise: int,
    currentTime: int = 0,
    executionId: str = "exec_e2e_001",
) -> ExecutionMandate:
    """Constructs and signs an ExecutionMandate binding intent and cart mandate hashes."""
    timestamp = currentTime if currentTime > 0 else int(time.time())
    return createSignedExecutionMandate(
        executionId=executionId,
        buyerAgentSigner=buyerSigner,
        intentMandate=intentMandate,
        cartMandate=cartMandate,
        settlementAmountPaise=totalGrossPaise,
        upiCircleToken=defaultUpiToken,
        timestamp=timestamp,
    )


def setupIntegrationOrchestrator(
    mockRedisClient: Any,
    simulatedFailureAccount: Optional[str] = None,
) -> SettlementOrchestrator:
    """Builds a SettlementOrchestrator configured with mock Route client and Redis NonceLedger."""
    routeClient = RazorpayRouteClient(apiKey="rzp_e2e_key", apiSecret="rzp_e2e_secret")
    if simulatedFailureAccount is not None:
        routeClient.simulatedFailureAccount = simulatedFailureAccount
    nonceLedger = NonceLedger(mockRedisClient)
    return SettlementOrchestrator(
        routeClient=routeClient,
        nonceLedger=nonceLedger,
    )
