"""Mandate Patcher for emitting dual-signed AmendmentMandate and healed CartMandate."""

import time
from typing import Optional

from razoragentMesh.packages.mandateEngine import (
    AmendmentMandate,
    BudgetExceededViolation,
    CartItemSchema,
    CartMandate,
    Ed25519Signer,
    IntentMandate,
    TaxBreakdownSchema,
    computeCartSettlementTotal,
    computeGstBreakdown,
    computeLineItemTotal,
    createSignedAmendmentMandate,
    createSignedCartMandate,
    validateIntegerPaise,
)


from ..constants.healerConstants import lockExpiryTtlSeconds, reasonInsufficientStock
from .cartDiffGenerator import generateCartDiff


class MandatePatcher:
    """Reconstructs CartMandate with substitute SKU and emits dual-signed AmendmentMandate."""

    def patchCartMandate(
        self, originalCartMandate: CartMandate, failedSkuId: str, substituteSkuId: str,
        substituteUnitPricePaise: int, substituteGstRatePercent: int, substituteHsnCode: str,
        requestedQuantity: int, buyerAgentSigner: Ed25519Signer, merchantSigner: Ed25519Signer,
        intentMandate: Optional[IntentMandate] = None, amendmentReason: str = reasonInsufficientStock,
    ) -> tuple[AmendmentMandate, CartMandate]:
        """Generates healed CartMandate and AmendmentMandate with dual Ed25519 signatures."""
        newTaxable, newGst, newTotal = _recalculateSubtotals(
            substituteUnitPricePaise, requestedQuantity, substituteGstRatePercent,
            originalCartMandate.shippingPaise, originalCartMandate.discountPaise,
        )
        _validateBudgetConstraint(newTotal, intentMandate)
        now = int(time.time())
        healedCart = _buildHealedCartMandate(
            originalCartMandate, substituteSkuId, substituteUnitPricePaise,
            substituteGstRatePercent, substituteHsnCode, requestedQuantity,
            newTaxable, newGst, newTotal, merchantSigner, now,
        )
        amendment = _dualSignAmendment(
            originalCartMandate, healedCart, failedSkuId, substituteSkuId,
            substituteUnitPricePaise, amendmentReason, buyerAgentSigner, merchantSigner, now,
        )
        return amendment, healedCart


def _recalculateSubtotals(
    unitPricePaise: int, quantity: int, gstRatePercent: int,
    shippingPaise: int, discountPaise: int,
) -> tuple[int, dict[str, int], int]:
    """Calculates integer paise subtotal, statutory GST breakdown, and settlement total."""
    validateIntegerPaise(unitPricePaise, "substituteUnitPricePaise")
    validateIntegerPaise(quantity, "requestedQuantity")
    validateIntegerPaise(gstRatePercent, "substituteGstRatePercent")

    newTaxable = computeLineItemTotal(unitPricePaise, quantity)
    newGst = computeGstBreakdown(newTaxable, gstRatePercent, isIntraState=True)
    newTotal = computeCartSettlementTotal(
        taxableSubtotalPaise=newTaxable, totalTaxPaise=newGst["totalTaxPaise"],
        shippingPaise=shippingPaise, discountPaise=discountPaise,
    )
    return newTaxable, newGst, newTotal


def _validateBudgetConstraint(newTotalPaise: int, intentMandate: Optional[IntentMandate]) -> None:
    """Verifies that healed cart total does not breach delegated budget ceiling."""
    if intentMandate is not None and newTotalPaise > intentMandate.maxBudgetPaise:
        raise BudgetExceededViolation(
            f"Substitute total ₹{newTotalPaise/100:.2f} exceeds delegated budget ₹{intentMandate.maxBudgetPaise/100:.2f}"
        )


def _buildHealedCartMandate(
    orig: CartMandate, skuId: str, price: int, gstRate: int, hsn: str,
    qty: int, taxable: int, gst: dict[str, int], total: int, signer: Ed25519Signer, ts: int,
) -> CartMandate:
    """Constructs and signs a new healed CartMandate with substitute SKU."""
    item = CartItemSchema(
        skuId=skuId, quantity=qty, unitPricePaise=price,
        hsnCode=hsn, gstRatePercent=gstRate, lineTotalPaise=taxable,
    )
    taxBreakdown = TaxBreakdownSchema(
        cgstPaise=gst["cgstPaise"], sgstPaise=gst["sgstPaise"],
        igstPaise=gst["igstPaise"], totalTaxPaise=gst["totalTaxPaise"],
    )
    return createSignedCartMandate(
        cartId=f"cart_healed_{skuId.lower()}", merchantSigner=signer,
        merchantGstin=orig.merchantGstin, merchantStateCode=orig.merchantStateCode,
        buyerDeliveryPincode=orig.buyerDeliveryPincode,
        buyerDeliveryStateCode=orig.buyerDeliveryStateCode,
        items=[item], taxableSubtotalPaise=taxable, taxBreakdown=taxBreakdown,
        shippingPaise=orig.shippingPaise, discountPaise=orig.discountPaise,
        totalPaise=total, inventoryLockToken=f"lock_token_healed_{skuId.lower()}",
        inventoryLockExpiresAt=ts + lockExpiryTtlSeconds, timestamp=ts,
    )


def _dualSignAmendment(
    orig: CartMandate, healed: CartMandate, failedSku: str, subSku: str,
    price: int, reason: str, buyerSigner: Ed25519Signer, merchSigner: Ed25519Signer, ts: int,
) -> AmendmentMandate:
    """Generates price delta diff and signs AmendmentMandate with buyer and merchant keys."""
    priceDelta = generateCartDiff(
        originalCartMandate=orig, failedSkuId=failedSku, substituteUnitPricePaise=price,
    )
    return createSignedAmendmentMandate(
        amendmentId=f"amend_{failedSku.lower()}_{subSku.lower()}",
        buyerAgentSigner=buyerSigner, merchantSigner=merchSigner,
        previousCartMandate=orig, newCartMandate=healed,
        substitutedSkuMapping={failedSku: subSku},
        priceDeltaPaise=priceDelta, amendmentReason=reason, timestamp=ts,
    )


__all__ = ["MandatePatcher"]
