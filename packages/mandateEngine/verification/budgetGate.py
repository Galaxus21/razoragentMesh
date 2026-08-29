"""AP2 Budget Gate and mathematical invariant validator."""

import time
from typing import Optional

from ..mandates.cartMandateSchema import CartMandate
from ..mandates.executionMandateSchema import ExecutionMandate
from ..mandates.intentMandateSchema import IntentMandate
from ..settlement.settlementExceptions import (
    ArithmeticEnclaveMismatchException,
    BudgetExceededViolation,
    CategoryNotAuthorizedException,
    MandateExpiredException,
    SingleTransactionLimitExceededException,
    UnauthorizedAgentException,
)
from .arithmeticEnclave import (
    computeCartSettlementTotal,
    computeGstBreakdown,
    computeLineItemTotal,
)


def validateBudgetGate(
    intentMandate: IntentMandate,
    cartMandate: CartMandate,
    executionMandate: ExecutionMandate,
    currentTimestamp: Optional[int] = None,
    skuCategories: Optional[list[str]] = None,
    serverTime: Optional[int] = None,
) -> bool:
    """Evaluates budget bounds, enclave math invariants, and delegation constraints."""
    evalTime = serverTime if serverTime is not None else (currentTimestamp or int(time.time()))
    if evalTime > intentMandate.validUntilTimestamp:
        raise MandateExpiredException(
            f"Intent mandate expired at {intentMandate.validUntilTimestamp} (current: {evalTime})"
        )

    _verifyDelegatedAgent(intentMandate, executionMandate)

    enclaveTotal = _recomputeEnclaveTotal(cartMandate)
    settlementAmt = executionMandate.settlementAmountPaise
    if enclaveTotal != settlementAmt or cartMandate.totalPaise != settlementAmt:
        raise ArithmeticEnclaveMismatchException(
            f"Arithmetic enclave mismatch: recomputed={enclaveTotal}, "
            f"cartTotal={cartMandate.totalPaise}, execution={settlementAmt}"
        )

    _verifyBudgetCaps(intentMandate, settlementAmt)
    _verifyCategoryAuthorization(intentMandate, skuCategories)
    return True


def _verifyDelegatedAgent(
    intentMandate: IntentMandate,
    executionMandate: ExecutionMandate,
) -> None:
    """Binds the executing agent to the agent the user actually delegated authority to.

    The Ed25519 verifying key is derived from the DID carried inside each mandate, so a
    signature proves only that the mandate is self-consistent -- not that its signer was
    authorized. Without this comparison, any party holding a user's signed IntentMandate could
    mint their own ExecutionMandate against it and spend the delegated budget.
    """
    if executionMandate.buyerAgentDid != intentMandate.delegatedAgentDid:
        raise UnauthorizedAgentException(
            f"Executing agent {executionMandate.buyerAgentDid} is not the delegated agent "
            f"{intentMandate.delegatedAgentDid} authorized by intent mandate "
            f"{intentMandate.mandateId}: ₹0 charged"
        )


def _recomputeEnclaveTotal(cartMandate: CartMandate) -> int:
    """Calculates total paise from items and taxes using pure integer arithmetic."""
    isIntraState = cartMandate.merchantStateCode == cartMandate.buyerDeliveryStateCode
    recomputedSubtotal = 0
    recomputedTax = 0

    for item in cartMandate.items:
        lineTaxable = computeLineItemTotal(item.unitPricePaise, item.quantity)
        gst = computeGstBreakdown(lineTaxable, item.gstRatePercent, isIntraState)
        recomputedSubtotal += lineTaxable
        recomputedTax += gst.totalTaxPaise

    return computeCartSettlementTotal(
        recomputedSubtotal,
        recomputedTax,
        cartMandate.shippingPaise,
        cartMandate.discountPaise,
    )


def _verifyBudgetCaps(intentMandate: IntentMandate, amountPaise: int) -> None:
    """Checks budget cap and single transaction ceiling."""
    if amountPaise > intentMandate.maxBudgetPaise:
        raise BudgetExceededViolation(
            f"Requested amount {amountPaise} paise exceeds delegated budget {intentMandate.maxBudgetPaise} paise: ₹0 charged"
        )
    if amountPaise > intentMandate.singleTransactionLimitPaise:
        raise SingleTransactionLimitExceededException(
            f"Transaction amount {amountPaise} paise exceeds single limit {intentMandate.singleTransactionLimitPaise} paise"
        )


def _verifyCategoryAuthorization(
    intentMandate: IntentMandate,
    skuCategories: Optional[list[str]],
) -> None:
    """Ensures cart categories are within delegated whitelist."""
    if not intentMandate.authorizedCategories or not skuCategories:
        return
    unauthorized = set(skuCategories) - set(intentMandate.authorizedCategories)
    if unauthorized:
        raise CategoryNotAuthorizedException(
            f"Unauthorized product categories in cart: {sorted(list(unauthorized))}"
        )


__all__ = ["validateBudgetGate"]
