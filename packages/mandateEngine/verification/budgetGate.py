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
    TaxHeadMismatchException,
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

    # Determined once and shared. Computing it separately in each consumer meant the copy
    # inside the total recomputation could be inverted with no observable effect -- CGST+SGST
    # and IGST sum to the same total -- so one of the two determinations was unfalsifiable.
    isIntraState = cartMandate.merchantStateCode == cartMandate.buyerDeliveryStateCode
    enclaveTotal = _recomputeEnclaveTotal(cartMandate, isIntraState)
    settlementAmt = executionMandate.settlementAmountPaise
    if enclaveTotal != settlementAmt or cartMandate.totalPaise != settlementAmt:
        raise ArithmeticEnclaveMismatchException(
            f"Arithmetic enclave mismatch: recomputed={enclaveTotal}, "
            f"cartTotal={cartMandate.totalPaise}, execution={settlementAmt}"
        )

    _verifyBudgetCaps(intentMandate, settlementAmt)
    _verifyTaxHeads(cartMandate, isIntraState)
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


def _recomputeEnclaveTotal(cartMandate: CartMandate, isIntraState: bool) -> int:
    """Calculates total paise from items and taxes using pure integer arithmetic."""
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


def _verifyTaxHeads(cartMandate: CartMandate, isIntraState: bool) -> None:
    """Checks WHICH tax heads the cart declares, not merely that they sum correctly.

    `_recomputeEnclaveTotal` compares totals, and CGST+SGST and IGST come to the same total for
    the same rate -- 18% on Rs.3,500 is 63000 paise either way. So a cart declaring the whole
    amount as IGST on an intra-state sale settles cleanly today: the money is right and the
    statutory heads are wrong, which surfaces as a mis-filed GSTR-1 rather than as a bad number.

    Surfaced by mutation testing: flipping `merchantStateCode == buyerDeliveryStateCode` to `!=`
    survived the entire suite, because nothing downstream of the total recomputation can observe
    the difference. It is caught here instead, which is why `validateBudgetGate`determines the
    place of supply once and hands it to both.

    The place/rate rule is not restated here -- `computeGstBreakdown` owns it and this reuses it,
    accumulating per line because tax is floored per line.
    """
    expectedCgst = 0
    expectedSgst = 0
    expectedIgst = 0
    for item in cartMandate.items:
        lineTaxable = computeLineItemTotal(item.unitPricePaise, item.quantity)
        gst = computeGstBreakdown(lineTaxable, item.gstRatePercent, isIntraState)
        expectedCgst += gst.cgstPaise
        expectedSgst += gst.sgstPaise
        expectedIgst += gst.igstPaise

    declared = cartMandate.taxBreakdown
    if (
        declared.cgstPaise != expectedCgst
        or declared.sgstPaise != expectedSgst
        or declared.igstPaise != expectedIgst
    ):
        placeOfSupply = "intra-state" if isIntraState else "inter-state"
        raise TaxHeadMismatchException(
            f"Cart {cartMandate.cartId} is {placeOfSupply} "
            f"({cartMandate.merchantStateCode} -> {cartMandate.buyerDeliveryStateCode}) and must "
            f"declare cgst={expectedCgst}, sgst={expectedSgst}, igst={expectedIgst} paise, but "
            f"declares cgst={declared.cgstPaise}, sgst={declared.sgstPaise}, "
            f"igst={declared.igstPaise}: ₹0 charged"
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
    """Ensures cart categories are within the delegated whitelist.

    An empty `authorizedCategories` is an unrestricted delegation, not a broken one: the user
    placed no category bound, so any cart is in scope. A non-empty whitelist is a bound, and a
    bound that cannot be evaluated must refuse. Returning early on a missing category list --
    which this did -- meant a caller silenced the whole check by passing nothing, and every
    caller did: `skuCategories` had no production caller at all, so `authorized_categories` was
    recorded on the mandate and enforced nowhere.

    Comparison is case-insensitive to match `catalogStore.ts`, which already selects catalog
    SKUs by `category.toLowerCase()`. One category vocabulary, one notion of equality.
    """
    if not intentMandate.authorizedCategories:
        return

    authorized = {category.strip().casefold() for category in intentMandate.authorizedCategories}
    if not skuCategories:
        raise CategoryNotAuthorizedException(
            f"Intent mandate {intentMandate.mandateId} restricts spending to "
            f"{sorted(intentMandate.authorizedCategories)}, but the cart carries no category to "
            f"check against it: ₹0 charged"
        )

    unauthorized = {
        category for category in skuCategories if category.strip().casefold() not in authorized
    }
    if unauthorized:
        raise CategoryNotAuthorizedException(
            f"Unauthorized product categories in cart: {sorted(unauthorized)} "
            f"(authorized: {sorted(intentMandate.authorizedCategories)}): ₹0 charged"
        )


__all__ = ["validateBudgetGate"]
