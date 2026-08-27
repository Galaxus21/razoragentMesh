"""Pytest fixtures and test vectors for RazorAgent Buyer SDK."""

import pytest
from razoragent_buyer_sdk import (
    AgentKeyManager,
    CartItemSchema,
    TaxBreakdownSchema,
    createCartMandate,
    createIntentMandate,
)

# Deterministic Test Private Keys (32 raw bytes = 64 hex characters)
userPrivateKeyHex: str = "1111111111111111111111111111111111111111111111111111111111111111"
agentPrivateKeyHex: str = "2222222222222222222222222222222222222222222222222222222222222222"
merchantPrivateKeyHex: str = "3333333333333333333333333333333333333333333333333333333333333333"


@pytest.fixture
def userKeyManager() -> AgentKeyManager:
    """AgentKeyManager for principal/CFO user."""
    return AgentKeyManager.fromPrivateKeyHex(userPrivateKeyHex)


@pytest.fixture
def agentKeyManager() -> AgentKeyManager:
    """AgentKeyManager for autonomous buyer agent."""
    return AgentKeyManager.fromPrivateKeyHex(agentPrivateKeyHex)


@pytest.fixture
def merchantKeyManager() -> AgentKeyManager:
    """AgentKeyManager for merchant."""
    return AgentKeyManager.fromPrivateKeyHex(merchantPrivateKeyHex)


@pytest.fixture
def sampleIntentMandate(userKeyManager: AgentKeyManager, agentKeyManager: AgentKeyManager):
    """Generates standard signed IntentMandate (M_I)."""
    return createIntentMandate(
        mandateId="M-I-TEST-001",
        userKeyManager=userKeyManager,
        delegatedAgentDid=agentKeyManager.getAgentDid(),
        maxBudgetPaise=500000,
        upiCircleDelegationToken="upi_delegate_tok_001",
        singleTransactionLimitPaise=500000,
        authorizedCategories=["electronics", "office"],
        validUntilTimestamp=2000000000,
        nonce="nonce_test_intent_001",
        timestamp=1700000000,
    )


@pytest.fixture
def sampleCartMandate(merchantKeyManager: AgentKeyManager):
    """Generates standard signed CartMandate (M_C)."""
    items = [
        CartItemSchema(
            skuId="SKU-001",
            quantity=1,
            unitPricePaise=420000,
            hsnCode="8504",
            gstRatePercent=18,
            lineTotalPaise=420000,
        )
    ]
    taxBreakdown = TaxBreakdownSchema(
        cgstPaise=37800,
        sgstPaise=37800,
        igstPaise=0,
        totalTaxPaise=75600,
    )
    return createCartMandate(
        cartId="M-C-TEST-001",
        merchantKeyManager=merchantKeyManager,
        merchantGstin="29AABCU9603R1ZJ",
        merchantStateCode="29",
        buyerDeliveryPincode="560001",
        buyerDeliveryStateCode="29",
        items=items,
        taxableSubtotalPaise=420000,
        taxBreakdown=taxBreakdown,
        shippingPaise=0,
        discountPaise=0,
        totalPaise=495600,
        inventoryLockToken="lock_tok_test_001",
        inventoryLockExpiresAt=2000000000,
        nonce="nonce_test_cart_001",
        timestamp=1700000000,
    )
