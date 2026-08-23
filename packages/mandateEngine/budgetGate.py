"""AP2 Budget Gate and mathematical invariant validator."""

import time
from typing import Optional

from razoragentMesh.packages.mandateEngine.arithmeticEnclave import (
    computeCartSettlementTotal,
    computeGstBreakdown,
    computeLineItemTotal,
)
from razoragentMesh.packages.mandateEngine.cartMandateSchema import CartMandate
from razoragentMesh.packages.mandateEngine.executionMandateSchema import ExecutionMandate
from razoragentMesh.packages.mandateEngine.intentMandateSchema import IntentMandate
from razoragentMesh.packages.mandateEngine.settlementExceptions import (
    ArithmeticEnclaveMismatchException,
    BudgetExceededViolation,
    CategoryNotAuthorizedException,
    MandateExpiredException,
    SingleTransactionLimitExceededException,
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
        recomputedTax += gst["totalTaxPaise"]

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


def validateBudgetGate(
    intentMandate: IntentMandate,
    cartMandate: CartMandate,
    executionMandate: ExecutionMandate,
    currentTimestamp: Optional[int] = None,
    skuCategories: Optional[list[str]] = None,
) -> bool:
    """Evaluates budget bounds, enclave math invariants, and delegation constraints."""
    evalTime = currentTimestamp or int(time.time())
    if evalTime > intentMandate.validUntilTimestamp:
        raise MandateExpiredException(
            f"Intent mandate expired at {intentMandate.validUntilTimestamp} (current: {evalTime})"
        )

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
