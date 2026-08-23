"""Mandate Patcher for emitting dual-signed AmendmentMandate and healed CartMandate."""

import time
from typing import Optional

from razoragentMesh.packages.mandateEngine.mandates.amendmentMandateSchema import AmendmentMandate
from razoragentMesh.packages.mandateEngine.verification.arithmeticEnclave import (
    computeCartSettlementTotal,
    computeGstBreakdown,
    computeLineItemTotal,
    validateIntegerPaise,
)
from razoragentMesh.packages.mandateEngine.mandates.cartMandateSchema import (
    CartItemSchema,
    CartMandate,
    TaxBreakdownSchema,
)
from razoragentMesh.packages.mandateEngine.crypto.ed25519Signer import Ed25519Signer
from razoragentMesh.packages.mandateEngine.mandates.intentMandateSchema import IntentMandate
from razoragentMesh.packages.mandateEngine.mandates.mandateFactory import (
    createSignedAmendmentMandate,
    createSignedCartMandate,
)
from razoragentMesh.packages.mandateEngine.settlement.settlementExceptions import (
    BudgetExceededViolation,
)

from ..constants.healerConstants import (
    lockExpiryTtlSeconds,
    reasonInsufficientStock,
)
from ..healerExceptions import (
    MandatePatchingException,
)
from .cartDiffGenerator import generateCartDiff


class MandatePatcher:
    """Reconstructs CartMandate with substitute SKU and emits dual-signed AmendmentMandate."""

    def patchCartMandate(
        self,
        originalCartMandate: CartMandate,
        failedSkuId: str,
        substituteSkuId: str,
        substituteUnitPricePaise: int,
        substituteGstRatePercent: int,
        substituteHsnCode: str,
        requestedQuantity: int,
        buyerAgentSigner: Ed25519Signer,
        merchantSigner: Ed25519Signer,
        intentMandate: Optional[IntentMandate] = None,
        amendmentReason: str = reasonInsufficientStock,
    ) -> tuple[AmendmentMandate, CartMandate]:
        """Generates healed CartMandate and AmendmentMandate with dual Ed25519 signatures."""
        validateIntegerPaise(substituteUnitPricePaise, "substituteUnitPricePaise")
        validateIntegerPaise(requestedQuantity, "requestedQuantity")
        validateIntegerPaise(substituteGstRatePercent, "substituteGstRatePercent")

        newTaxable = computeLineItemTotal(substituteUnitPricePaise, requestedQuantity)
        newGst = computeGstBreakdown(newTaxable, substituteGstRatePercent, isIntraState=True)
        newTotal = computeCartSettlementTotal(newTaxable, newGst["totalTaxPaise"])

        if intentMandate is not None and newTotal > intentMandate.maxBudgetPaise:
            raise BudgetExceededViolation(
                f"Substitute total ₹{newTotal/100:.2f} exceeds delegated budget ₹{intentMandate.maxBudgetPaise/100:.2f}"
            )

        newCartItem = CartItemSchema(
            skuId=substituteSkuId,
            quantity=requestedQuantity,
            unitPricePaise=substituteUnitPricePaise,
            hsnCode=substituteHsnCode,
            gstRatePercent=substituteGstRatePercent,
            lineTotalPaise=newTaxable,
        )
        newTaxBreakdown = TaxBreakdownSchema(
            cgstPaise=newGst["cgstPaise"],
            sgstPaise=newGst["sgstPaise"],
            igstPaise=newGst["igstPaise"],
            totalTaxPaise=newGst["totalTaxPaise"],
        )

        now = int(time.time())
        healedCart = createSignedCartMandate(
            cartId=f"cart_healed_{substituteSkuId.lower()}",
            merchantSigner=merchantSigner,
            merchantGstin=originalCartMandate.merchantGstin,
            merchantStateCode=originalCartMandate.merchantStateCode,
            buyerDeliveryPincode=originalCartMandate.buyerDeliveryPincode,
            buyerDeliveryStateCode=originalCartMandate.buyerDeliveryStateCode,
            items=[newCartItem],
            taxableSubtotalPaise=newTaxable,
            taxBreakdown=newTaxBreakdown,
            shippingPaise=originalCartMandate.shippingPaise,
            discountPaise=originalCartMandate.discountPaise,
            totalPaise=newTotal,
            inventoryLockToken=f"lock_token_healed_{substituteSkuId.lower()}",
            inventoryLockExpiresAt=now + lockExpiryTtlSeconds,
            timestamp=now,
        )

        priceDelta = generateCartDiff(
            originalCartMandate=originalCartMandate,
            failedSkuId=failedSkuId,
            substituteUnitPricePaise=substituteUnitPricePaise,
        )

        amendment = createSignedAmendmentMandate(
            amendmentId=f"amend_{failedSkuId.lower()}_{substituteSkuId.lower()}",
            buyerAgentSigner=buyerAgentSigner,
            merchantSigner=merchantSigner,
            previousCartMandate=originalCartMandate,
            newCartMandate=healedCart,
            substitutedSkuMapping={failedSkuId: substituteSkuId},
            priceDeltaPaise=priceDelta,
            amendmentReason=amendmentReason,
            timestamp=now,
        )

        return amendment, healedCart


__all__ = ["MandatePatcher"]
