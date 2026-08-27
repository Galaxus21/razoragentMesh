"""Adversarial stress tests for AgentMandateBuilder, AP2 Mandates, and hash binding."""

import time
import pytest
from pydantic import ValidationError
from razoragent_buyer_sdk import (
    AgentKeyManager,
    AgentMandateBuilder,
    AmendmentMandate,
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


def _assertInvalidIntentMandate(userKeyManager: AgentKeyManager, agentDid: str, maxBudgetPaise: int, singleLimit: int) -> None:
    with pytest.raises(MandateValidationError):
        createIntentMandate(
            mandateId="M-I-ERR",
            userKeyManager=userKeyManager,
            delegatedAgentDid=agentDid,
            maxBudgetPaise=maxBudgetPaise,
            upiCircleDelegationToken="tok",
            singleTransactionLimitPaise=singleLimit,
        )


def testIntentMandateAdversarialBounds(userKeyManager: AgentKeyManager, agentKeyManager: AgentKeyManager) -> None:
    """Tests budget, limit, category, and temporal boundary constraints on IntentMandate."""
    agentDid = agentKeyManager.getAgentDid()
    for maxB, singleL in [(0, 5000), (-1000, 5000), (10000, 0), (10000, -500)]:
        _assertInvalidIntentMandate(userKeyManager, agentDid, maxB, singleL)

    hugeBudget = 100_000_000_000 * 100
    hugeIntent = createIntentMandate(
        mandateId="M-I-HUGE", userKeyManager=userKeyManager, delegatedAgentDid=agentDid,
        maxBudgetPaise=hugeBudget, upiCircleDelegationToken="tok_huge",
        singleTransactionLimitPaise=hugeBudget,
        authorizedCategories=["enterprise_infra", "cloud_compute"], validUntilTimestamp=2147483647,
    )
    assert hugeIntent.maxBudgetPaise == hugeBudget

    emptyCatIntent = createIntentMandate(
        mandateId="M-I-EMPTY-CAT", userKeyManager=userKeyManager, delegatedAgentDid=agentDid,
        maxBudgetPaise=50000, upiCircleDelegationToken="tok",
        singleTransactionLimitPaise=50000, authorizedCategories=[],
    )
    assert emptyCatIntent.authorizedCategories == []


def _assertCartItemValidationError(**kwargs) -> None:
    with pytest.raises(ValidationError):
        CartItemSchema(**kwargs)


def testCartMandateSchemaValidation(merchantKeyManager: AgentKeyManager) -> None:
    """Stress tests CartItemSchema and CartMandate invariant enforcement."""
    tax = TaxBreakdownSchema(cgstPaise=900, sgstPaise=900, igstPaise=0, totalTaxPaise=1800)
    with pytest.raises(ValidationError):
        CartMandate(
            cartId="C-001", merchantDid=merchantKeyManager.getAgentDid(),
            merchantGstin="29AABCU9603R1ZJ", merchantStateCode="29",
            buyerDeliveryPincode="560001", buyerDeliveryStateCode="29",
            items=[], taxableSubtotalPaise=10000, taxBreakdown=tax,
            shippingPaise=0, discountPaise=0, totalPaise=11800,
            inventoryLockToken="lock_001", inventoryLockExpiresAt=2000000000,
            nonce="nonce_01", timestamp=1700000000, merchantSignature="a" * 128,
        )

    _assertCartItemValidationError(skuId="SKU-01", quantity=1, unitPricePaise=10000, hsnCode="INVALID", gstRatePercent=18, lineTotalPaise=10000)
    _assertCartItemValidationError(skuId="SKU-01", quantity=1, unitPricePaise=10000, hsnCode="8504", gstRatePercent=40, lineTotalPaise=10000)
    _assertCartItemValidationError(skuId="SKU-01", quantity=0, unitPricePaise=10000, hsnCode="8504", gstRatePercent=18, lineTotalPaise=10000)



def testExecutionMandateHashChainAdversarial(
    agentKeyManager: AgentKeyManager,
    sampleIntentMandate: IntentMandate,
    sampleCartMandate: CartMandate,
) -> None:
    """Stress tests tamper resistance of ExecutionMandate triple-hash binding."""
    execMandate = createExecutionMandate(
        executionId="M-E-001",
        buyerKeyManager=agentKeyManager,
        intentMandate=sampleIntentMandate,
        cartMandate=sampleCartMandate,
        settlementAmountPaise=sampleCartMandate.totalPaise,
        upiCircleToken=sampleIntentMandate.upiCircleDelegationToken,
    )

    # 1-bit flip in intent hash
    mutatedIntentHash = "0" + execMandate.intentMandateHash[1:]
    tamperedIntentExec = execMandate.model_copy(update={"intentMandateHash": mutatedIntentHash})
    assert verifyMandateHashChain(sampleIntentMandate, sampleCartMandate, tamperedIntentExec, raiseOnMismatch=False) is False
    with pytest.raises(MandateHashMismatchError):
        verifyMandateHashChain(sampleIntentMandate, sampleCartMandate, tamperedIntentExec, raiseOnMismatch=True)

    # 1-bit flip in cart hash
    mutatedCartHash = "f" + execMandate.cartMandateHash[1:]
    tamperedCartExec = execMandate.model_copy(update={"cartMandateHash": mutatedCartHash})
    assert verifyMandateHashChain(sampleIntentMandate, sampleCartMandate, tamperedCartExec, raiseOnMismatch=False) is False
    with pytest.raises(MandateHashMismatchError):
        verifyMandateHashChain(sampleIntentMandate, sampleCartMandate, tamperedCartExec, raiseOnMismatch=True)


def _assertMandateInvariantFailure(intent: IntentMandate, cart: CartMandate, execM: ExecutionMandate, curTime: int, expectedMsg: str) -> None:
    with pytest.raises(MandateValidationError) as exc:
        validateMandateInvariants(intent, cart, execM, currentTime=curTime)
    assert expectedMsg in str(exc.value).lower()


def testValidateMandateInvariantsStress(
    agentKeyManager: AgentKeyManager,
    sampleIntentMandate: IntentMandate,
    sampleCartMandate: CartMandate,
) -> None:
    """Stress tests validateMandateInvariants across all failure modes."""
    now = 1700000000
    execMandate = createExecutionMandate(
        executionId="M-E-001", buyerKeyManager=agentKeyManager,
        intentMandate=sampleIntentMandate, cartMandate=sampleCartMandate,
        settlementAmountPaise=sampleCartMandate.totalPaise,
        upiCircleToken=sampleIntentMandate.upiCircleDelegationToken, timestamp=now,
    )
    validateMandateInvariants(sampleIntentMandate, sampleCartMandate, execMandate, currentTime=now)

    _assertMandateInvariantFailure(sampleIntentMandate, sampleCartMandate, execMandate, sampleIntentMandate.validUntilTimestamp + 1, "expired")
    budgetExceeded = sampleIntentMandate.model_copy(update={"maxBudgetPaise": sampleCartMandate.totalPaise - 1})
    _assertMandateInvariantFailure(budgetExceeded, sampleCartMandate, execMandate, now, "exceeds max budget")
    limitExceeded = sampleIntentMandate.model_copy(update={"singleTransactionLimitPaise": sampleCartMandate.totalPaise - 1})
    _assertMandateInvariantFailure(limitExceeded, sampleCartMandate, execMandate, now, "exceeds single limit")
    mismatchedCart = sampleCartMandate.model_copy(update={"totalPaise": sampleCartMandate.totalPaise + 100})
    _assertMandateInvariantFailure(sampleIntentMandate, mismatchedCart, execMandate, now, "does not match execution settlement amount")


def _assertAmendmentSignatures(agentPub: str, merchPub: str, payload: dict, agentSig: str, merchSig: str, expected: bool) -> None:
    assert AgentKeyManager.verifyPayloadSignature(agentPub, payload, agentSig) is expected
    assert AgentKeyManager.verifyPayloadSignature(merchPub, payload, merchSig) is expected


def testAmendmentMandateDualSignatureIntegrity(
    agentKeyManager: AgentKeyManager,
    merchantKeyManager: AgentKeyManager,
    sampleCartMandate: CartMandate,
) -> None:
    """Stress tests dual-signature verification for AmendmentMandate."""
    newCart = sampleCartMandate.model_copy(update={"cartId": "M-C-NEW-001", "totalPaise": sampleCartMandate.totalPaise + 5000})
    amendment = createAmendmentMandate(
        amendmentId="M-A-001", buyerKeyManager=agentKeyManager,
        merchantKeyManager=merchantKeyManager, previousCartMandate=sampleCartMandate,
        newCartMandate=newCart, substitutedSkuMapping={"SKU-001": "SKU-002"},
        priceDeltaPaise=5000, amendmentReason="Out of stock substitute item",
    )
    unsignedPayload = {
        "amendmentId": amendment.amendmentId, "amendmentReason": amendment.amendmentReason,
        "newCartMandateHash": amendment.newCartMandateHash, "nonce": amendment.nonce,
        "previousCartMandateHash": amendment.previousCartMandateHash,
        "priceDeltaPaise": amendment.priceDeltaPaise,
        "substitutedSkuMapping": amendment.substitutedSkuMapping, "timestamp": amendment.timestamp,
    }
    agentPub = agentKeyManager.getPublicKeyHex()
    merchPub = merchantKeyManager.getPublicKeyHex()
    _assertAmendmentSignatures(agentPub, merchPub, unsignedPayload, amendment.agentSignature, amendment.merchantSignature, True)

    tamperedPayload = dict(unsignedPayload, priceDeltaPaise=99999)
    _assertAmendmentSignatures(agentPub, merchPub, tamperedPayload, amendment.agentSignature, amendment.merchantSignature, False)

