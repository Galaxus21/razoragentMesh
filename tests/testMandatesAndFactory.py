"""Unit tests for Mandate schemas, factory builders, and cryptographic hash chaining."""

import pytest
from razoragentMesh.packages.mandateEngine.mandates.amendmentMandateSchema import AmendmentMandate
from razoragentMesh.packages.mandateEngine.mandates.cartMandateSchema import (
    CartItemSchema,
    CartMandate,
    TaxBreakdownSchema,
)
from razoragentMesh.packages.mandateEngine.crypto.cryptoKeyUtils import generateKeyPair
from razoragentMesh.packages.mandateEngine.crypto.ed25519Signer import Ed25519Signer
from razoragentMesh.packages.mandateEngine.mandates.executionMandateSchema import ExecutionMandate
from razoragentMesh.packages.mandateEngine.mandates.intentMandateSchema import IntentMandate
from razoragentMesh.packages.mandateEngine.mandates.mandateFactory import (
    computeMandateHash,
    createSignedAmendmentMandate,
    createSignedCartMandate,
    createSignedExecutionMandate,
    createSignedIntentMandate,
    verifyMandateHashChain,
)
from razoragentMesh.packages.mandateEngine.settlement.settlementExceptions import (
    MandateHashChainMismatchException,
)


def _createTestSigners() -> Tuple[Ed25519Signer, Ed25519Signer, Ed25519Signer]:
    return (
        Ed25519Signer(generateKeyPair()[0]),
        Ed25519Signer(generateKeyPair()[0]),
        Ed25519Signer(generateKeyPair()[0]),
    )


def testMandateCreationAndHashChaining() -> None:
    """Verifies full lifecycle of M_I, M_C, and M_E with cryptographic hash chain binding."""
    userSigner, merchantSigner, agentSigner = _createTestSigners()
    intentMandate = createSignedIntentMandate(
        mandateId="M-INTENT-001", userSigner=userSigner, delegatedAgentDid=agentSigner.getAgentDid(),
        maxBudgetPaise=500000, upiCircleDelegationToken="upi_circle_tok_123",
        singleTransactionLimitPaise=200000, authorizedCategories=["electronics", "hardware"],
    )
    assert isinstance(intentMandate, IntentMandate) and len(intentMandate.userSignature) == 128

    item = CartItemSchema(skuId="SKU-HARDWARE-01", quantity=2, unitPricePaise=75000, hsnCode="84713010", gstRatePercent=18, lineTotalPaise=150000)
    taxBreakdown = TaxBreakdownSchema(cgstPaise=13500, sgstPaise=13500, igstPaise=0, totalTaxPaise=27000)
    cartMandate = createSignedCartMandate(
        cartId="M-CART-001", merchantSigner=merchantSigner, merchantGstin="29AAAAA0000A1ZY",
        merchantStateCode="29", buyerDeliveryPincode="560001", buyerDeliveryStateCode="29",
        items=[item], taxableSubtotalPaise=150000, taxBreakdown=taxBreakdown,
        shippingPaise=5000, discountPaise=0, totalPaise=182000,
        inventoryLockToken="lock_tok_abc", inventoryLockExpiresAt=1780000000,
    )
    assert isinstance(cartMandate, CartMandate) and len(cartMandate.merchantSignature) == 128

    executionMandate = createSignedExecutionMandate(
        executionId="M-EXEC-001", buyerAgentSigner=agentSigner, intentMandate=intentMandate,
        cartMandate=cartMandate, settlementAmountPaise=182000, upiCircleToken="upi_token_xyz",
    )
    assert isinstance(executionMandate, ExecutionMandate)
    assert executionMandate.intentMandateHash == computeMandateHash(intentMandate)
    assert executionMandate.cartMandateHash == computeMandateHash(cartMandate)
    assert verifyMandateHashChain(intentMandate, cartMandate, executionMandate) is True


def testHashChainMismatchFails() -> None:
    """Verifies that tampering with intent or cart mandate fails hash-chain verification."""
    userSigner, merchantSigner, agentSigner = _createTestSigners()
    makeIntent = lambda mid, b, tok: createSignedIntentMandate(
        mandateId=mid, userSigner=userSigner, delegatedAgentDid=agentSigner.getAgentDid(),
        maxBudgetPaise=b, upiCircleDelegationToken=tok, singleTransactionLimitPaise=200000,
    )
    intentMandate1, intentMandate2 = makeIntent("M-INTENT-001", 500000, "tok_1"), makeIntent("M-INTENT-002", 600000, "tok_2")

    item = CartItemSchema(skuId="SKU-1", quantity=1, unitPricePaise=10000, hsnCode="84713010", gstRatePercent=18, lineTotalPaise=10000)
    cartMandate = createSignedCartMandate(
        cartId="M-CART-001", merchantSigner=merchantSigner, merchantGstin="29AAAAA0000A1ZY",
        merchantStateCode="29", buyerDeliveryPincode="560001", buyerDeliveryStateCode="29",
        items=[item], taxableSubtotalPaise=10000,
        taxBreakdown=TaxBreakdownSchema(cgstPaise=900, sgstPaise=900, igstPaise=0, totalTaxPaise=1800),
        shippingPaise=0, discountPaise=0, totalPaise=11800, inventoryLockToken="lock_1",
        inventoryLockExpiresAt=1780000000,
    )
    executionMandate = createSignedExecutionMandate(
        executionId="M-EXEC-001", buyerAgentSigner=agentSigner, intentMandate=intentMandate1,
        cartMandate=cartMandate, settlementAmountPaise=11800, upiCircleToken="upi_tok",
    )
    with pytest.raises(MandateHashChainMismatchException):
        verifyMandateHashChain(intentMandate2, cartMandate, executionMandate)

