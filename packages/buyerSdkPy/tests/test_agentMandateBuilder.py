"""Unit tests for AP2 Mandate construction, canonical hashing, and chain binding."""

import pytest
from razoragent_buyer_sdk import (
    AgentKeyManager,
    AgentMandateBuilder,
    ArithmeticDriftError,
    CartItemSchema,
    CartMandate,
    ExecutionMandate,
    IntentMandate,
    MandateHashMismatchError,
    MandateValidationError,
    TaxBreakdownSchema,
    computeMandateHash,
    createAmendmentMandate,
    createCartMandate,
    createExecutionMandate,
    createIntentMandate,
    validateMandateInvariants,
    verifyMandateHashChain,
)


def testCreateSignedIntentMandate(userKeyManager: AgentKeyManager, agentKeyManager: AgentKeyManager) -> None:
    """Verifies creation and signature validity of IntentMandate (M_I)."""
    intent = createIntentMandate(
        mandateId="M-I-001",
        userKeyManager=userKeyManager,
        delegatedAgentDid=agentKeyManager.getAgentDid(),
        maxBudgetPaise=1000000,
        upiCircleDelegationToken="upi_tok_test_001",
        singleTransactionLimitPaise=500000,
        authorizedCategories=["electronics"],
        validUntilTimestamp=2000000000,
        nonce="nonce_001",
        timestamp=1700000000,
    )
    assert intent.mandateId == "M-I-001"
    assert intent.userDid == userKeyManager.getAgentDid()
    assert intent.delegatedAgentDid == agentKeyManager.getAgentDid()
    assert len(intent.userSignature) == 128


def testCreateSignedCartMandate(merchantKeyManager: AgentKeyManager) -> None:
    """Verifies creation and signature validity of CartMandate (M_C)."""
    items = [
        CartItemSchema(
            skuId="SKU-001",
            quantity=2,
            unitPricePaise=200000,
            hsnCode="8504",
            gstRatePercent=18,
            lineTotalPaise=400000,
        )
    ]
    taxBreakdown = TaxBreakdownSchema(
        cgstPaise=36000,
        sgstPaise=36000,
        igstPaise=0,
        totalTaxPaise=72000,
    )
    cart = createCartMandate(
        cartId="M-C-001",
        merchantKeyManager=merchantKeyManager,
        merchantGstin="29AABCU9603R1ZJ",
        merchantStateCode="29",
        buyerDeliveryPincode="560001",
        buyerDeliveryStateCode="29",
        items=items,
        taxableSubtotalPaise=400000,
        taxBreakdown=taxBreakdown,
        shippingPaise=0,
        discountPaise=0,
        totalPaise=472000,
        inventoryLockToken="lock_tok_001",
        inventoryLockExpiresAt=2000000000,
        nonce="nonce_cart_001",
        timestamp=1700000000,
    )
    assert cart.cartId == "M-C-001"
    assert cart.merchantDid == merchantKeyManager.getAgentDid()
    assert len(cart.merchantSignature) == 128


def testCreateSignedExecutionMandate(
    agentKeyManager: AgentKeyManager,
    sampleIntentMandate: IntentMandate,
    sampleCartMandate: CartMandate,
) -> None:
    """Verifies creation and hash binding of ExecutionMandate (M_E)."""
    execution = createExecutionMandate(
        executionId="M-E-001",
        buyerKeyManager=agentKeyManager,
        intentMandate=sampleIntentMandate,
        cartMandate=sampleCartMandate,
        settlementAmountPaise=sampleCartMandate.totalPaise,
        upiCircleToken=sampleIntentMandate.upiCircleDelegationToken,
        nonce="nonce_exec_001",
        timestamp=1700000000,
    )
    assert execution.executionId == "M-E-001"
    assert execution.buyerAgentDid == agentKeyManager.getAgentDid()
    assert execution.intentMandateHash == computeMandateHash(sampleIntentMandate)
    assert execution.cartMandateHash == computeMandateHash(sampleCartMandate)
    assert len(execution.agentSignature) == 128


def testCreateSignedAmendmentMandate(
    agentKeyManager: AgentKeyManager,
    merchantKeyManager: AgentKeyManager,
    sampleCartMandate: CartMandate,
) -> None:
    """Verifies dual-signed AmendmentMandate (M_A) creation."""
    amendment = createAmendmentMandate(
        amendmentId="M-A-001",
        buyerKeyManager=agentKeyManager,
        merchantKeyManager=merchantKeyManager,
        previousCartMandate=sampleCartMandate,
        newCartMandate=sampleCartMandate,
        substitutedSkuMapping={"SKU-001": "SKU-002"},
        priceDeltaPaise=5000,
        amendmentReason="Out of stock substitute",
        nonce="nonce_amend_001",
        timestamp=1700000000,
    )
    assert amendment.amendmentId == "M-A-001"
    assert len(amendment.agentSignature) == 128
    assert len(amendment.merchantSignature) == 128


def testMandateHashChainBinding(
    agentKeyManager: AgentKeyManager,
    sampleIntentMandate: IntentMandate,
    sampleCartMandate: CartMandate,
) -> None:
    """Verifies triple-hash binding chain verification and tamper detection."""
    execution = createExecutionMandate(
        executionId="M-E-001",
        buyerKeyManager=agentKeyManager,
        intentMandate=sampleIntentMandate,
        cartMandate=sampleCartMandate,
        settlementAmountPaise=sampleCartMandate.totalPaise,
        upiCircleToken="token_001",
    )
    assert verifyMandateHashChain(sampleIntentMandate, sampleCartMandate, execution) is True

    # Mutate intent hash in execution
    tamperedExecution = ExecutionMandate(
        executionId=execution.executionId,
        buyerAgentDid=execution.buyerAgentDid,
        intentMandateHash="0" * 64,
        cartMandateHash=execution.cartMandateHash,
        settlementAmountPaise=execution.settlementAmountPaise,
        currency=execution.currency,
        upiCircleToken=execution.upiCircleToken,
        nonce=execution.nonce,
        timestamp=execution.timestamp,
        agentSignature=execution.agentSignature,
    )
    with pytest.raises(MandateHashMismatchError):
        verifyMandateHashChain(sampleIntentMandate, sampleCartMandate, tamperedExecution)


def testSignatureStrippingInHashComputation(sampleIntentMandate: IntentMandate) -> None:
    """Verifies that signature mutation does not alter computed mandate hash."""
    originalHash = computeMandateHash(sampleIntentMandate)
    mutatedSignatureIntent = IntentMandate(
        mandateId=sampleIntentMandate.mandateId,
        userDid=sampleIntentMandate.userDid,
        delegatedAgentDid=sampleIntentMandate.delegatedAgentDid,
        maxBudgetPaise=sampleIntentMandate.maxBudgetPaise,
        currency=sampleIntentMandate.currency,
        authorizedCategories=sampleIntentMandate.authorizedCategories,
        validUntilTimestamp=sampleIntentMandate.validUntilTimestamp,
        upiCircleDelegationToken=sampleIntentMandate.upiCircleDelegationToken,
        singleTransactionLimitPaise=sampleIntentMandate.singleTransactionLimitPaise,
        nonce=sampleIntentMandate.nonce,
        timestamp=sampleIntentMandate.timestamp,
        userSignature="0" * 128,
    )
    assert computeMandateHash(mutatedSignatureIntent) == originalHash


def testMandateInvariantValidations(
    agentKeyManager: AgentKeyManager,
    sampleIntentMandate: IntentMandate,
    sampleCartMandate: CartMandate,
) -> None:
    """Verifies business invariant assertions across AP2 mandate chain."""
    execution = createExecutionMandate(
        executionId="M-E-001",
        buyerKeyManager=agentKeyManager,
        intentMandate=sampleIntentMandate,
        cartMandate=sampleCartMandate,
        settlementAmountPaise=sampleCartMandate.totalPaise,
        upiCircleToken="token_001",
    )
    # Valid pass
    validateMandateInvariants(sampleIntentMandate, sampleCartMandate, execution, currentTime=1700000000)

    # Expired intent mandate
    with pytest.raises(MandateValidationError):
        validateMandateInvariants(sampleIntentMandate, sampleCartMandate, execution, currentTime=2000000001)

    # Settlement amount exceeding max budget
    smallBudgetIntent = createIntentMandate(
        mandateId="M-I-SMALL",
        userKeyManager=agentKeyManager,
        delegatedAgentDid=agentKeyManager.getAgentDid(),
        maxBudgetPaise=1000,
        upiCircleDelegationToken="tok",
        singleTransactionLimitPaise=1000,
    )
    with pytest.raises(MandateValidationError):
        validateMandateInvariants(smallBudgetIntent, sampleCartMandate, execution)


def testZeroFloatRejectionInMandates() -> None:
    """Verifies float values in mandate dictionaries trigger ArithmeticDriftError."""
    corruptedPayload = {"maxBudgetPaise": 5000.50, "currency": "INR"}
    with pytest.raises(ArithmeticDriftError):
        computeMandateHash(corruptedPayload)
