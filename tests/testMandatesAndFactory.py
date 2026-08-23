"""Unit tests for Mandate schemas, factory builders, and cryptographic hash chaining."""

import pytest
from razoragentMesh.packages.mandateEngine.amendmentMandateSchema import AmendmentMandate
from razoragentMesh.packages.mandateEngine.cartMandateSchema import (
    CartItemSchema,
    CartMandate,
    TaxBreakdownSchema,
)
from razoragentMesh.packages.mandateEngine.cryptoKeyUtils import generateKeyPair
from razoragentMesh.packages.mandateEngine.ed25519Signer import Ed25519Signer
from razoragentMesh.packages.mandateEngine.executionMandateSchema import ExecutionMandate
from razoragentMesh.packages.mandateEngine.intentMandateSchema import IntentMandate
from razoragentMesh.packages.mandateEngine.mandateFactory import (
    computeMandateHash,
    createSignedAmendmentMandate,
    createSignedCartMandate,
    createSignedExecutionMandate,
    createSignedIntentMandate,
    verifyMandateHashChain,
)
from razoragentMesh.packages.mandateEngine.settlementExceptions import (
    MandateHashChainMismatchException,
)


def testMandateCreationAndHashChaining() -> None:
    """Verifies full lifecycle of M_I, M_C, and M_E with cryptographic hash chain binding."""
    # Keypairs for User, Merchant, Buyer Agent
    userPriv, _ = generateKeyPair()
    merchantPriv, _ = generateKeyPair()
    agentPriv, _ = generateKeyPair()

    userSigner = Ed25519Signer(userPriv)
    merchantSigner = Ed25519Signer(merchantPriv)
    agentSigner = Ed25519Signer(agentPriv)

    # 1. User issues IntentMandate (M_I)
    intentMandate = createSignedIntentMandate(
        mandateId="M-INTENT-001",
        userSigner=userSigner,
        delegatedAgentDid=agentSigner.getAgentDid(),
        maxBudgetPaise=500000,
        upiCircleDelegationToken="upi_circle_tok_123",
        singleTransactionLimitPaise=200000,
        authorizedCategories=["electronics", "hardware"],
    )
    assert isinstance(intentMandate, IntentMandate)
    assert len(intentMandate.userSignature) == 128

    # 2. Merchant issues CartMandate (M_C)
    item = CartItemSchema(
        skuId="SKU-HARDWARE-01",
        quantity=2,
        unitPricePaise=75000,
        hsnCode="84713010",
        gstRatePercent=18,
        lineTotalPaise=150000,
    )
    taxBreakdown = TaxBreakdownSchema(
        cgstPaise=13500,
        sgstPaise=13500,
        igstPaise=0,
        totalTaxPaise=27000,
    )
    cartMandate = createSignedCartMandate(
        cartId="M-CART-001",
        merchantSigner=merchantSigner,
        merchantGstin="29AAAAA0000A1Z5",
        merchantStateCode="29",
        buyerDeliveryPincode="560001",
        buyerDeliveryStateCode="29",
        items=[item],
        taxableSubtotalPaise=150000,
        taxBreakdown=taxBreakdown,
        shippingPaise=5000,
        discountPaise=0,
        totalPaise=182000,
        inventoryLockToken="lock_tok_abc",
        inventoryLockExpiresAt=1780000000,
    )
    assert isinstance(cartMandate, CartMandate)
    assert len(cartMandate.merchantSignature) == 128

    # 3. Buyer Agent issues ExecutionMandate (M_E) binding H(M_I) || H(M_C)
    executionMandate = createSignedExecutionMandate(
        executionId="M-EXEC-001",
        buyerAgentSigner=agentSigner,
        intentMandate=intentMandate,
        cartMandate=cartMandate,
        settlementAmountPaise=182000,
        upiCircleToken="upi_token_xyz",
    )
    assert isinstance(executionMandate, ExecutionMandate)
    assert executionMandate.intentMandateHash == computeMandateHash(intentMandate)
    assert executionMandate.cartMandateHash == computeMandateHash(cartMandate)

    # 4. Verification of hash chain
    assert verifyMandateHashChain(intentMandate, cartMandate, executionMandate) is True


def testHashChainMismatchFails() -> None:
    """Verifies that tampering with intent or cart mandate fails hash-chain verification."""
    userPriv, _ = generateKeyPair()
    merchantPriv, _ = generateKeyPair()
    agentPriv, _ = generateKeyPair()

    userSigner = Ed25519Signer(userPriv)
    merchantSigner = Ed25519Signer(merchantPriv)
    agentSigner = Ed25519Signer(agentPriv)

    intentMandate1 = createSignedIntentMandate(
        mandateId="M-INTENT-001",
        userSigner=userSigner,
        delegatedAgentDid=agentSigner.getAgentDid(),
        maxBudgetPaise=500000,
        upiCircleDelegationToken="tok_1",
        singleTransactionLimitPaise=200000,
    )
    intentMandate2 = createSignedIntentMandate(
        mandateId="M-INTENT-002",
        userSigner=userSigner,
        delegatedAgentDid=agentSigner.getAgentDid(),
        maxBudgetPaise=600000,
        upiCircleDelegationToken="tok_2",
        singleTransactionLimitPaise=200000,
    )

    item = CartItemSchema(
        skuId="SKU-1",
        quantity=1,
        unitPricePaise=10000,
        hsnCode="84713010",
        gstRatePercent=18,
        lineTotalPaise=10000,
    )
    cartMandate = createSignedCartMandate(
        cartId="M-CART-001",
        merchantSigner=merchantSigner,
        merchantGstin="29AAAAA0000A1Z5",
        merchantStateCode="29",
        buyerDeliveryPincode="560001",
        buyerDeliveryStateCode="29",
        items=[item],
        taxableSubtotalPaise=10000,
        taxBreakdown=TaxBreakdownSchema(cgstPaise=900, sgstPaise=900, igstPaise=0, totalTaxPaise=1800),
        shippingPaise=0,
        discountPaise=0,
        totalPaise=11800,
        inventoryLockToken="lock_1",
        inventoryLockExpiresAt=1780000000,
    )

    executionMandate = createSignedExecutionMandate(
        executionId="M-EXEC-001",
        buyerAgentSigner=agentSigner,
        intentMandate=intentMandate1,
        cartMandate=cartMandate,
        settlementAmountPaise=11800,
        upiCircleToken="upi_tok",
    )

    # Intent mandate 2 has a different hash, should raise MandateHashChainMismatchException
    with pytest.raises(MandateHashChainMismatchException):
        verifyMandateHashChain(intentMandate2, cartMandate, executionMandate)
