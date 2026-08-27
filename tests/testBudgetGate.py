"""Unit tests for AP2 Budget Gate and invariant verification."""

import pytest
from razoragentMesh.packages.mandateEngine.verification.arithmeticEnclave import (
    computeCartSettlementTotal,
    computeGstBreakdown,
    computeLineItemTotal,
)
from razoragentMesh.packages.mandateEngine.verification.budgetGate import validateBudgetGate
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
    createSignedCartMandate,
    createSignedExecutionMandate,
    createSignedIntentMandate,
)
from razoragentMesh.packages.mandateEngine.settlement.settlementExceptions import (
    ArithmeticEnclaveMismatchException,
    BudgetExceededViolation,
    CategoryNotAuthorizedException,
    MandateExpiredException,
    SingleTransactionLimitExceededException,
)


def _setupMandates(budgetPaise: int, unitPricePaise: int, quantity: int = 1, singleLimit: int = 2000000) -> tuple:
    """Helper creating signed test mandate trio."""
    uSigner = Ed25519Signer(generateKeyPair()[0])
    mSigner = Ed25519Signer(generateKeyPair()[0])
    aSigner = Ed25519Signer(generateKeyPair()[0])

    intentM = createSignedIntentMandate(
        mandateId="M-I-01", userSigner=uSigner, delegatedAgentDid=aSigner.getAgentDid(),
        maxBudgetPaise=budgetPaise, upiCircleDelegationToken="upi_tok",
        singleTransactionLimitPaise=singleLimit, authorizedCategories=["electronics"],
        validUntilTimestamp=2000000000,
    )
    lineTaxable = computeLineItemTotal(unitPricePaise, quantity)
    gst = computeGstBreakdown(lineTaxable, 18, isIntraState=True)
    totalPaise = computeCartSettlementTotal(lineTaxable, gst["totalTaxPaise"], shippingPaise=0, discountPaise=0)

    item = CartItemSchema(
        skuId="SKU-ELEC-01", quantity=quantity, unitPricePaise=unitPricePaise,
        hsnCode="84713010", gstRatePercent=18, lineTotalPaise=lineTaxable,
    )
    taxBreakdown = TaxBreakdownSchema(
        cgstPaise=gst["cgstPaise"], sgstPaise=gst["sgstPaise"],
        igstPaise=gst["igstPaise"], totalTaxPaise=gst["totalTaxPaise"],
    )
    cartM = createSignedCartMandate(
        cartId="M-C-01", merchantSigner=mSigner, merchantGstin="29AAAAA0000A1ZY",
        merchantStateCode="29", buyerDeliveryPincode="560001", buyerDeliveryStateCode="29",
        items=[item], taxableSubtotalPaise=lineTaxable, taxBreakdown=taxBreakdown,
        shippingPaise=0, discountPaise=0, totalPaise=totalPaise,
        inventoryLockToken="lock_tok", inventoryLockExpiresAt=2000000000,
    )
    execM = createSignedExecutionMandate(
        executionId="M-E-01", buyerAgentSigner=aSigner, intentMandate=intentM,
        cartMandate=cartM, settlementAmountPaise=totalPaise, upiCircleToken="upi_tok",
    )
    return intentM, cartM, execM



def testBudgetGateWithinBudgetPasses() -> None:
    """Verifies that settlement within budget passes gating."""
    # Taxable 350000, 18% tax 63000 -> Total 413000 <= 500000 budget
    intentM, cartM, execM = _setupMandates(budgetPaise=500000, unitPricePaise=350000)
    assert validateBudgetGate(intentM, cartM, execM, currentTimestamp=1700000000, skuCategories=["electronics"]) is True


def testBudgetGateBreachBlocked() -> None:
    """Verifies that cart amount exceeding budget cap raises BudgetExceededViolation (₹0 charged)."""
    # Taxable 1000000, 18% tax 180000 -> Total 1180000 > 1000000 budget
    intentM, cartM, execM = _setupMandates(budgetPaise=1000000, unitPricePaise=1000000)
    with pytest.raises(BudgetExceededViolation):
        validateBudgetGate(intentM, cartM, execM, currentTimestamp=1700000000)


def testBudgetGateSingleLimitExceeded() -> None:
    """Verifies single transaction ceiling enforcement."""
    # Taxable 1000000, Total 1180000 > 1000000 single limit
    intentM, cartM, execM = _setupMandates(budgetPaise=2000000, unitPricePaise=1000000, singleLimit=1000000)
    with pytest.raises(SingleTransactionLimitExceededException):
        validateBudgetGate(intentM, cartM, execM, currentTimestamp=1700000000)


def testBudgetGateExpiredMandate() -> None:
    """Verifies temporal expiration gating."""
    intentM, cartM, execM = _setupMandates(budgetPaise=500000, unitPricePaise=350000)
    with pytest.raises(MandateExpiredException):
        validateBudgetGate(intentM, cartM, execM, currentTimestamp=2000000001)


def testBudgetGateCategoryViolation() -> None:
    """Verifies category authorization restriction."""
    intentM, cartM, execM = _setupMandates(budgetPaise=500000, unitPricePaise=350000)
    with pytest.raises(CategoryNotAuthorizedException):
        validateBudgetGate(intentM, cartM, execM, currentTimestamp=1700000000, skuCategories=["furniture"])


def testBudgetGateArithmeticMismatchDrift() -> None:
    """Verifies that even a 1 paise divergence between mandate and enclave raises ArithmeticEnclaveMismatchException."""
    intentM, cartM, execM = _setupMandates(budgetPaise=500000, unitPricePaise=350000)
    # Artificially modify execution mandate amount by +1 paise
    tamperedExecM = ExecutionMandate(
        executionId=execM.executionId,
        buyerAgentDid=execM.buyerAgentDid,
        intentMandateHash=execM.intentMandateHash,
        cartMandateHash=execM.cartMandateHash,
        settlementAmountPaise=execM.settlementAmountPaise + 1,
        currency="INR",
        upiCircleToken=execM.upiCircleToken,
        nonce=execM.nonce,
        timestamp=execM.timestamp,
        agentSignature=execM.agentSignature,
    )
    with pytest.raises(ArithmeticEnclaveMismatchException):
        validateBudgetGate(intentM, cartM, tamperedExecM, currentTimestamp=1700000000)
