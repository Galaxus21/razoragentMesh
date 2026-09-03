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
    TaxHeadMismatchException,
    MandateExpiredException,
    SingleTransactionLimitExceededException,
)


def _setupMandates(
    budgetPaise: int, unitPricePaise: int, quantity: int = 1, singleLimit: int = 2000000,
    authorizedCategories: list = None,
) -> tuple:
    """Helper creating signed test mandate trio."""
    uSigner = Ed25519Signer(generateKeyPair()[0])
    mSigner = Ed25519Signer(generateKeyPair()[0])
    aSigner = Ed25519Signer(generateKeyPair()[0])

    intentM = createSignedIntentMandate(
        mandateId="M-I-01", userSigner=uSigner, delegatedAgentDid=aSigner.getAgentDid(),
        maxBudgetPaise=budgetPaise, upiCircleDelegationToken="upi_tok",
        singleTransactionLimitPaise=singleLimit,
        authorizedCategories=["electronics"] if authorizedCategories is None else authorizedCategories,
        validUntilTimestamp=2000000000,
    )
    lineTaxable = computeLineItemTotal(unitPricePaise, quantity)
    gst = computeGstBreakdown(lineTaxable, 18, isIntraState=True)
    totalPaise = computeCartSettlementTotal(lineTaxable, gst.totalTaxPaise, shippingPaise=0, discountPaise=0)

    item = CartItemSchema(
        skuId="SKU-ELEC-01", quantity=quantity, unitPricePaise=unitPricePaise,
        hsnCode="84713010", gstRatePercent=18, lineTotalPaise=lineTaxable,
    )
    taxBreakdown = TaxBreakdownSchema(
        cgstPaise=gst.cgstPaise, sgstPaise=gst.sgstPaise,
        igstPaise=gst.igstPaise, totalTaxPaise=gst.totalTaxPaise,
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


def testARestrictedDelegationRefusesACallerThatSuppliesNoCategories() -> None:
    """Passing nothing must not silence the whitelist.

    Surfaced by mutation testing: `python scripts/mutationScore.py --modules
    packages/mandateEngine/verification/budgetGate.py` reported the guard at budgetGate.py:126
    surviving as `pass`, meaning no test exercised it. That branch is the one that matters most.
    `_verifyCategoryAuthorization` used to return early whenever `skuCategories` was empty, and
    every caller passed nothing -- which is exactly how `authorized_categories` came to be
    recorded on every mandate and enforced on none. A gate any caller can disable by omission is
    not a gate, so a bound that cannot be evaluated has to refuse.
    """
    intentM, cartM, execM = _setupMandates(budgetPaise=500000, unitPricePaise=350000)
    with pytest.raises(CategoryNotAuthorizedException) as excInfo:
        validateBudgetGate(intentM, cartM, execM, currentTimestamp=1700000000)
    assert "carries no category" in str(excInfo.value)
    assert "electronics" in str(excInfo.value)


def testAnUnrestrictedDelegationIsUnaffectedByTheAbsenceOfCategories() -> None:
    """The counterweight: refusing on absence must not break the default delegation.

    Both SDKs default `authorizedCategories` to an empty list, so reading the refusal above as
    "no categories supplied means reject" would break every delegation that never opted into a
    category restriction.
    """
    intentM, cartM, execM = _setupMandates(
        budgetPaise=500000, unitPricePaise=350000, authorizedCategories=[]
    )
    assert validateBudgetGate(intentM, cartM, execM, currentTimestamp=1700000000) is True


def testSettlementAtExactlyTheBudgetCapIsAllowed() -> None:
    """The cap is a ceiling the buyer may reach, not one they must stay under.

    Also from mutation testing: `amountPaise > maxBudgetPaise` survived being flipped to `>=`,
    so nothing distinguished "spend the whole budget" from "exceed it". Off by one paise in that
    direction refuses a legitimate settlement.
    """
    # Taxable 350000 + 18% = 413000, which is exactly the delegated budget.
    intentM, cartM, execM = _setupMandates(budgetPaise=413000, unitPricePaise=350000)
    assert validateBudgetGate(
        intentM, cartM, execM, currentTimestamp=1700000000, skuCategories=["electronics"]
    ) is True

    with pytest.raises(BudgetExceededViolation):
        validateBudgetGate(
            *_setupMandates(budgetPaise=412999, unitPricePaise=350000),
            currentTimestamp=1700000000, skuCategories=["electronics"],
        )


def testIntraStateCartDeclaringIgstIsRejected() -> None:
    """A cart may not file the right amount under the wrong tax heads.

    Surfaced by mutation testing: flipping `merchantStateCode == buyerDeliveryStateCode` in the
    enclave recomputation survived the whole suite. It survived because CGST+SGST and IGST come
    to the SAME total for the same rate -- 18% on Rs.3,500 is 63000 paise either way -- and the
    enclave only ever compared totals. The money was right and the statutory heads were free to
    be wrong, which surfaces as a mis-filed GSTR-1 rather than as a bad number anyone would see.
    """
    intentM, cartM, execM = _setupMandates(budgetPaise=500000, unitPricePaise=350000)
    # 29 -> 29 is intra-state, so the heads must be CGST+SGST.
    misfiled = TaxBreakdownSchema(cgstPaise=0, sgstPaise=0, igstPaise=63000, totalTaxPaise=63000)
    misfiledCart = cartM.model_copy(update={"taxBreakdown": misfiled})

    with pytest.raises(TaxHeadMismatchException) as excInfo:
        validateBudgetGate(
            intentM, misfiledCart, execM, currentTimestamp=1700000000,
            skuCategories=["electronics"],
        )
    assert "intra-state" in str(excInfo.value)
    # The total is untouched, which is exactly why the arithmetic enclave cannot catch this.
    assert misfiled.totalTaxPaise == cartM.taxBreakdown.totalTaxPaise


def testInterStateCartDeclaringCgstSgstIsRejected() -> None:
    """The same rule in the other direction, so the check is not one-sided."""
    intentM, cartM, execM = _setupMandates(budgetPaise=500000, unitPricePaise=350000)
    # Delivering to state 27 makes this inter-state, where the only lawful head is IGST.
    interStateCart = cartM.model_copy(update={"buyerDeliveryStateCode": "27"})

    with pytest.raises(TaxHeadMismatchException) as excInfo:
        validateBudgetGate(
            intentM, interStateCart, execM, currentTimestamp=1700000000,
            skuCategories=["electronics"],
        )
    assert "inter-state" in str(excInfo.value)
    assert "igst=63000" in str(excInfo.value)


def testASingleWrongTaxHeadIsEnoughToReject() -> None:
    """Every head is checked independently, not only the all-three-wrong case.

    Surfaced by mutation testing: swapping the `or`s in the comparison for `and`s survived,
    because the two tests above both move all three heads at once. Under `and`, a cart with one
    head off by a paise -- the likelier real error, and the one a rounding bug produces -- would
    have settled.
    """
    intentM, cartM, execM = _setupMandates(budgetPaise=500000, unitPricePaise=350000)
    lawful = cartM.taxBreakdown
    # One paise moved from CGST to SGST: the total still reconciles, so only a per-head
    # comparison can see it.
    skewed = TaxBreakdownSchema(
        cgstPaise=lawful.cgstPaise - 1,
        sgstPaise=lawful.sgstPaise + 1,
        igstPaise=lawful.igstPaise,
        totalTaxPaise=lawful.totalTaxPaise,
    )
    skewedCart = cartM.model_copy(update={"taxBreakdown": skewed})

    with pytest.raises(TaxHeadMismatchException):
        validateBudgetGate(
            intentM, skewedCart, execM, currentTimestamp=1700000000,
            skuCategories=["electronics"],
        )
