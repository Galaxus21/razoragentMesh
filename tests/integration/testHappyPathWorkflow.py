"""Integration tests for nominal happy-path autonomous procurement workflows."""

import time
from typing import Any, Dict, List, Tuple
import pytest

from razoragentMesh.packages.catalogSanitizer.catalogSanitizer import (
    sanitizeMerchantSkuQuote,
)
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
    createSignedIntentMandate,
    verifyMandateHashChain,
)
from razoragentMesh.packages.mandateEngine.settlement.settlementOrchestrator import (
    SettlementResult,
)
from razoragentMesh.packages.mandateEngine.settlement.splitManifestBuilder import (
    defaultProtocolFeePaise,
)
from razoragentMesh.packages.mandateEngine.verification.budgetGate import validateBudgetGate
from razoragentMesh.tests.integration.testEndToEndFixtures import (
    IntegrationSigners,
    buildRawMerchantQuote,
    buildStandardCartMandate,
    buildStandardExecutionMandate,
    defaultBuyerPincode,
    defaultBuyerState,
    defaultCategory,
    defaultHsnCode,
    defaultLockToken,
    defaultMerchantAccount,
    defaultMerchantGstin,
    defaultMerchantState,
    defaultUpiToken,
    delegatedBudgetPaise,
    gstRate,
    offeredUnitPricePaise,
    orderQuantity,
    setupIntegrationOrchestrator,
    setupIntegrationSigners,
    targetSkuId,
)

secondarySkuId: str = "SKU-002"
secondaryQuantity: int = 20
secondaryUnitPricePaise: int = 45000
largeBudgetPaise: int = 10000000


def _verifyIngressSanitization(rawQuote: Dict[str, Any]) -> None:
    """Verifies that catalog sanitizer cleans zero-width injection and script tags."""
    sanitizedQuote = sanitizeMerchantSkuQuote(rawQuote)
    assert "\u200b" not in sanitizedQuote.title
    assert "<script>" not in sanitizedQuote.description


async def _reserveInventoryLock(
    mockRedisClient: Any,
    skuId: str,
    qty: int,
    lockToken: str,
) -> int:
    """Reserves stock via Redis Lua atomic script and returns the assigned fencing token."""
    stockKey = f"sku:{skuId}:stock"
    fencingKey = f"sku:{skuId}:fence"
    lockStatus, fencingToken = await mockRedisClient.eval(
        "", 2, stockKey, fencingKey, qty, lockToken, 60
    )
    assert lockStatus == 1
    assert fencingToken >= 1
    return int(fencingToken)


def _verifyMandateIntegrity(
    intentM: IntentMandate,
    cartM: CartMandate,
    execM: ExecutionMandate,
    currentTime: int,
) -> None:
    """Validates cryptographic hash chaining and AP2 budget gating across mandates."""
    assert verifyMandateHashChain(intentM, cartM, execM) is True
    assert validateBudgetGate(intentM, cartM, execM, currentTime) is True


def _verifySettlementInvariants(
    result: SettlementResult,
    expectedTotalPaise: int,
) -> None:
    """Validates post-settlement invariants, transfer captures, and GSTR audit hashes."""
    assert result.status == "captured"
    assert result.amountPaise == expectedTotalPaise
    assert len(result.transfers) >= 1
    assert result.invoice.grandTotalPaise == expectedTotalPaise
    assert len(result.invoice.cryptographicAuditHash) == 64


def _buildMultiItemCartMandate(
    signers: IntegrationSigners,
    lockToken: str,
    currentTime: int,
) -> Tuple[CartMandate, int]:
    """Constructs and cryptographically signs a 2-item cart mandate with volume discounts."""
    subtotalOne = offeredUnitPricePaise * orderQuantity
    subtotalTwo = secondaryUnitPricePaise * secondaryQuantity
    totalTaxable = subtotalOne + subtotalTwo

    cgstOne = (subtotalOne * (gstRate // 2)) // 100
    cgstTwo = (subtotalTwo * (gstRate // 2)) // 100
    totalCgst = cgstOne + cgstTwo
    totalSgst = totalCgst
    totalTax = totalCgst + totalSgst
    totalGross = totalTaxable + totalTax

    itemOne = CartItemSchema(
        skuId=targetSkuId, quantity=orderQuantity, unitPricePaise=offeredUnitPricePaise,
        hsnCode=defaultHsnCode, gstRatePercent=gstRate, lineTotalPaise=subtotalOne,
    )
    itemTwo = CartItemSchema(
        skuId=secondarySkuId, quantity=secondaryQuantity, unitPricePaise=secondaryUnitPricePaise,
        hsnCode=defaultHsnCode, gstRatePercent=gstRate, lineTotalPaise=subtotalTwo,
    )
    taxBreakdown = TaxBreakdownSchema(
        cgstPaise=totalCgst, sgstPaise=totalSgst, igstPaise=0, totalTaxPaise=totalTax,
    )
    cartMandate = createSignedCartMandate(
        cartId="cart_multi_001", merchantSigner=signers.merchantSigner,
        merchantGstin=defaultMerchantGstin, merchantStateCode=defaultMerchantState,
        buyerDeliveryPincode=defaultBuyerPincode, buyerDeliveryStateCode=defaultBuyerState,
        items=[itemOne, itemTwo], taxableSubtotalPaise=totalTaxable,
        taxBreakdown=taxBreakdown, shippingPaise=0, discountPaise=0,
        totalPaise=totalGross, inventoryLockToken=lockToken,
        inventoryLockExpiresAt=currentTime + 60, timestamp=currentTime,
    )
    return cartMandate, totalGross


@pytest.mark.asyncio
async def testEndToEndAutonomousProcurementFlow(
    agentKeyFixtures: Dict[str, Any],
    catalogFixtures: List[Dict[str, Any]],
    mockRedisClient: Any,
) -> None:
    """End-to-End Integration Test: Full Layer 0 -> Layer 1 -> Layer 4 autonomous settlement."""
    signers = setupIntegrationSigners(agentKeyFixtures)
    currentTime = int(time.time())

    rawQuote = buildRawMerchantQuote(currentTime=currentTime)
    _verifyIngressSanitization(rawQuote)

    intentMandate = createSignedIntentMandate(
        mandateId="intent_e2e_001", userSigner=signers.userSigner,
        delegatedAgentDid=signers.buyerSigner.getAgentDid(), maxBudgetPaise=delegatedBudgetPaise,
        upiCircleDelegationToken=defaultUpiToken, singleTransactionLimitPaise=delegatedBudgetPaise,
        authorizedCategories=[defaultCategory], timestamp=currentTime,
    )

    await _reserveInventoryLock(mockRedisClient, targetSkuId, orderQuantity, defaultLockToken)
    cartMandate, totalGrossPaise = buildStandardCartMandate(signers, defaultLockToken, currentTime)
    executionMandate = buildStandardExecutionMandate(
        signers.buyerSigner, intentMandate, cartMandate, totalGrossPaise, currentTime,
    )

    _verifyMandateIntegrity(intentMandate, cartMandate, executionMandate, currentTime)
    orchestrator = setupIntegrationOrchestrator(mockRedisClient)
    result = await orchestrator.executeSettlementSaga(
        intentMandate=intentMandate, cartMandate=cartMandate,
        executionMandate=executionMandate, merchantAccount=defaultMerchantAccount,
        paymentId="pay_e2e_settlement_001", serverTime=currentTime,
    )
    _verifySettlementInvariants(result, totalGrossPaise)


@pytest.mark.asyncio
async def testMultiItemVolumeDiscountProcurementFlow(
    agentKeyFixtures: Dict[str, Any],
    mockRedisClient: Any,
) -> None:
    """Verifies multi-SKU cart procurement with volume discount tiers and integer paise GST."""
    signers = setupIntegrationSigners(agentKeyFixtures)
    currentTime = int(time.time())

    intentMandate = createSignedIntentMandate(
        mandateId="intent_multi_001", userSigner=signers.userSigner,
        delegatedAgentDid=signers.buyerSigner.getAgentDid(), maxBudgetPaise=largeBudgetPaise,
        upiCircleDelegationToken=defaultUpiToken, singleTransactionLimitPaise=largeBudgetPaise,
        authorizedCategories=[defaultCategory], timestamp=currentTime,
    )

    await _reserveInventoryLock(mockRedisClient, targetSkuId, orderQuantity, "lock_multi_001")
    await _reserveInventoryLock(mockRedisClient, secondarySkuId, secondaryQuantity, "lock_multi_002")

    cartMandate, totalGrossPaise = _buildMultiItemCartMandate(signers, "lock_multi_001", currentTime)
    executionMandate = buildStandardExecutionMandate(
        signers.buyerSigner, intentMandate, cartMandate, totalGrossPaise, currentTime, "exec_multi_001",
    )

    _verifyMandateIntegrity(intentMandate, cartMandate, executionMandate, currentTime)
    orchestrator = setupIntegrationOrchestrator(mockRedisClient)
    result = await orchestrator.executeSettlementSaga(
        intentMandate=intentMandate, cartMandate=cartMandate,
        executionMandate=executionMandate, merchantAccount=defaultMerchantAccount,
        paymentId="pay_multi_settlement_001", serverTime=currentTime,
    )
    _verifySettlementInvariants(result, totalGrossPaise)
    assert len(cartMandate.items) == 2


@pytest.mark.asyncio
async def testA2AAutonomousSettlementWithInvoiceHash(
    agentKeyFixtures: Dict[str, Any],
    mockRedisClient: Any,
) -> None:
    """Verifies GSTR-1 audit hash, protocol fee split, and immutable settlement result."""
    signers = setupIntegrationSigners(agentKeyFixtures)
    currentTime = int(time.time())

    intentMandate = createSignedIntentMandate(
        mandateId="intent_a2a_001", userSigner=signers.userSigner,
        delegatedAgentDid=signers.buyerSigner.getAgentDid(), maxBudgetPaise=delegatedBudgetPaise,
        upiCircleDelegationToken=defaultUpiToken, singleTransactionLimitPaise=delegatedBudgetPaise,
        authorizedCategories=[defaultCategory], timestamp=currentTime,
    )
    await _reserveInventoryLock(mockRedisClient, targetSkuId, orderQuantity, "lock_a2a_001")
    cartMandate, totalGrossPaise = buildStandardCartMandate(signers, "lock_a2a_001", currentTime, cartId="cart_a2a_001")
    executionMandate = buildStandardExecutionMandate(
        signers.buyerSigner, intentMandate, cartMandate, totalGrossPaise, currentTime, "exec_a2a_001",
    )

    orchestrator = setupIntegrationOrchestrator(mockRedisClient)
    result = await orchestrator.executeSettlementSaga(
        intentMandate=intentMandate, cartMandate=cartMandate,
        executionMandate=executionMandate, merchantAccount=defaultMerchantAccount,
        paymentId="pay_a2a_settlement_001", serverTime=currentTime,
    )

    assert result.status == "captured"
    assert result.amountPaise == totalGrossPaise
    assert len(result.transfers) == 2
    merchantTransfer = next(t for t in result.transfers if t.account == defaultMerchantAccount)
    protocolTransfer = next(t for t in result.transfers if t.account != defaultMerchantAccount)
    assert merchantTransfer.amount == totalGrossPaise - defaultProtocolFeePaise
    assert protocolTransfer.amount == defaultProtocolFeePaise
    assert result.invoice.invoiceNumber.startswith("INV-")
    assert len(result.invoice.cryptographicAuditHash) == 64
