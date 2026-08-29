"""Challenger 1 Empirical Stress: GSTR Mixed Tax, JCS Invariance, and Asymmetric Discounts.

Tests:
1. Multi-item GSTR-1 mixed tax calculation, TCS withholding, and JCS canonical hash across (0%, 5%, 12%, 18%, 28%)
2. Zero penny drift (Δ = 0 paise) under asymmetric discount allocation across odd unit prices
"""

from typing import List, Tuple
import pytest

from razoragentMesh.packages.mandateEngine.crypto.cryptoKeyUtils import generateKeyPair
from razoragentMesh.packages.mandateEngine.crypto.ed25519Signer import Ed25519Signer
from razoragentMesh.packages.mandateEngine.crypto.jcsCanonicalizer import (
    canonicalizeAndHash,
    canonicalizeJson,
    computeSha256Digest,
)
from razoragentMesh.packages.mandateEngine.mandates.cartMandateSchema import (
    CartItemSchema,
    CartMandate,
    TaxBreakdownSchema,
)
from razoragentMesh.packages.mandateEngine.mandates.executionMandateSchema import (
    ExecutionMandate,
)
from razoragentMesh.packages.mandateEngine.mandates.mandateFactory import (
    createSignedCartMandate,
    createSignedExecutionMandate,
    createSignedIntentMandate,
)
from razoragentMesh.packages.mandateEngine.settlement.settlementExceptions import (
    ArithmeticDriftException,
)
from razoragentMesh.packages.mandateEngine.tax.gstinValidator import (
    computeGstinChecksum,
)
from razoragentMesh.packages.mandateEngine.tax.gstrInvoiceEngine import (
    GstrInvoicePayload,
    _buildInvoiceDict,
    generateGstrInvoice,
)
from razoragentMesh.packages.mandateEngine.verification.arithmeticEnclave import (
    computeCartSettlementTotal,
    computeGstBreakdown,
    computeLineItemTotal,
    computeTcsWithholding,
)


def _buildSlabItems(slabs: List[int], quantities: List[int], unitPrices: List[int], isIntraState: bool):
    items, expTaxables, expTaxes, expCgst, expSgst, expIgst = [], [], [], [], [], []
    for idx, rate in enumerate(slabs):
        qty, price = quantities[idx], unitPrices[idx]
        taxable = computeLineItemTotal(price, qty)
        expTaxables.append(taxable)
        gst = computeGstBreakdown(taxable, rate, isIntraState=isIntraState)
        assert gst.totalTaxPaise == gst.cgstPaise + gst.sgstPaise + gst.igstPaise
        expTaxes.append(gst.totalTaxPaise)
        expCgst.append(gst.cgstPaise)
        expSgst.append(gst.sgstPaise)
        expIgst.append(gst.igstPaise)
        items.append(CartItemSchema(
            skuId=f"SKU-SLAB-{rate}", quantity=qty, unitPricePaise=price,
            hsnCode=f"84{rate:02d}00", gstRatePercent=rate, lineTotalPaise=taxable,
        ))
    return items, sum(expTaxables), sum(expTaxes), sum(expCgst), sum(expSgst), sum(expIgst)


def _buildGstrMandates(items, taxableSubtotal, totalTax, totalCgst, totalSgst, totalIgst, grossTotal, merchantState, deliveryState):
    uSigner = Ed25519Signer(generateKeyPair()[0])
    mSigner = Ed25519Signer(generateKeyPair()[0])
    aSigner = Ed25519Signer(generateKeyPair()[0])
    intent = createSignedIntentMandate(
        mandateId="M-I-GSTR-STRESS", userSigner=uSigner, delegatedAgentDid=aSigner.getAgentDid(),
        maxBudgetPaise=10000000, upiCircleDelegationToken="upi_tok_gstr", singleTransactionLimitPaise=10000000,
    )
    tb = TaxBreakdownSchema(cgstPaise=totalCgst, sgstPaise=totalSgst, igstPaise=totalIgst, totalTaxPaise=totalTax)
    prefix14 = f"{merchantState}AABCU9603R1Z"
    gstin = f"{prefix14}{computeGstinChecksum(prefix14)}"
    cart = createSignedCartMandate(
        cartId="M-C-GSTR-STRESS", merchantSigner=mSigner, merchantGstin=gstin,
        merchantStateCode=merchantState, buyerDeliveryPincode="560001", buyerDeliveryStateCode=deliveryState,
        items=items, taxableSubtotalPaise=taxableSubtotal, taxBreakdown=tb, shippingPaise=7500,
        discountPaise=5000, totalPaise=grossTotal, inventoryLockToken="lock_gstr_stress", inventoryLockExpiresAt=2000000000,
    )
    execM = createSignedExecutionMandate(
        executionId="M-E-GSTR-STRESS", buyerAgentSigner=aSigner, intentMandate=intent,
        cartMandate=cart, settlementAmountPaise=grossTotal, upiCircleToken="upi_tok_gstr", timestamp=1750000000,
    )
    return cart, execM


class TestGstrMixedTaxAndJcsVerification:
    """1. Multi-item GSTR-1 mixed tax calculation, TCS withholding, and JCS canonical hash generation."""

    @pytest.mark.parametrize(
        "isIntraState,merchantState,deliveryState",
        [(True, "29", "29"), (False, "29", "27"), (False, "07", "33"), (True, "06", "06")],
    )
    def testAllFiveGstSlabsMixedCart(self, isIntraState: bool, merchantState: str, deliveryState: str) -> None:
        """Verifies a 5-item cart spanning all GST slabs (0%, 5%, 12%, 18%, 28%)."""
        slabs = [0, 5, 12, 18, 28]
        quantities = [1, 2, 3, 4, 5]
        unitPrices = [50000, 75000, 120000, 250000, 400000]

        items, taxableSub, totalTax, totalCgst, totalSgst, totalIgst = _buildSlabItems(
            slabs, quantities, unitPrices, isIntraState
        )
        assert totalTax == totalCgst + totalSgst + totalIgst
        grossTotal = computeCartSettlementTotal(
            taxableSubtotalPaise=taxableSub, totalTaxPaise=totalTax, shippingPaise=7500, discountPaise=5000
        )
        cartM, execM = _buildGstrMandates(
            items, taxableSub, totalTax, totalCgst, totalSgst, totalIgst, grossTotal, merchantState, deliveryState
        )
        invoice = generateGstrInvoice(
            cartMandate=cartM, executionMandate=execM, invoiceNumber="INV-STRESS-GSTR-01", invoiceTimestamp=1750000000
        )
        assert isinstance(invoice, GstrInvoicePayload) and invoice.isIntraState == isIntraState
        assert invoice.taxableAmountPaise == taxableSub and invoice.totalTaxPaise == totalTax
        assert invoice.grandTotalPaise == grossTotal

        tcsExpected = computeTcsWithholding(taxableSub, isIntraState=isIntraState)
        assert invoice.totalTcsPaise == tcsExpected["totalTcsPaise"]

        rawDict = _buildInvoiceDict(
            cart=cartM, items=invoice.lineItems,
            totals=(taxableSub, totalCgst, totalSgst, totalIgst, totalTax, grossTotal),
            num="INV-STRESS-GSTR-01", dt=invoice.invoiceDate, intra=isIntraState,
        )
        assert invoice.cryptographicAuditHash == computeSha256Digest(canonicalizeJson(rawDict))

    def testJcsCanonicalHashInvarianceUnderKeyPermutations(self) -> None:
        """Verifies JCS produces identical hash regardless of dict key insertion order."""
        dict1 = {"zebra": 100, "alpha": {"bravo": [1, 2, 3], "charlie": "test"}, "middle": True, "beta": None}
        dict2 = {"beta": None, "middle": True, "alpha": {"charlie": "test", "bravo": [1, 2, 3]}, "zebra": 100}
        bytes1, hash1 = canonicalizeAndHash(dict1)
        bytes2, hash2 = canonicalizeAndHash(dict2)
        assert bytes1 == bytes2 and hash1 == hash2

    def testJcsRejectsAllFloatingPointPoisoning(self) -> None:
        """Verifies JCS strictly rejects floats in shallow, deep, or list structures."""
        with pytest.raises(ArithmeticDriftException):
            canonicalizeJson({"price": 100.0})
        with pytest.raises(ArithmeticDriftException):
            canonicalizeJson({"items": [{"qty": 1, "rate": 0.05}]})
        with pytest.raises(ArithmeticDriftException):
            canonicalizeJson([1, 2, [3, 4.0]])


class TestAsymmetricDiscountAndPennyConservation:
    """2. Zero penny drift (Δ = 0 paise) under asymmetric discount allocation."""

    @pytest.mark.parametrize(
        "prices,globalDiscount",
        [
            ([33333, 55555, 77777], 15000), ([33333, 55555, 77777], 10000),
            ([13, 37, 101, 333, 777, 999], 150), ([100001, 200003, 300007, 400009], 50000),
            ([7, 11, 13, 17, 19, 23, 29, 31], 75), ([999999, 1], 500000),
        ],
    )
    def testAsymmetricDiscountAllocationZeroDrift(self, prices: List[int], globalDiscount: int) -> None:
        """Verifies exact penny conservation across odd unit prices."""
        cartSubtotal = sum(prices)
        assert cartSubtotal > globalDiscount

        rawDiscounts = [(globalDiscount * p) // cartSubtotal for p in prices]
        driftRemainder = globalDiscount - sum(rawDiscounts)
        finalDiscounts = list(rawDiscounts)
        finalDiscounts[prices.index(max(prices))] += driftRemainder

        assert sum(finalDiscounts) == globalDiscount
        netLineTotals = [p - d for p, d in zip(prices, finalDiscounts)]
        assert sum(netLineTotals) == cartSubtotal - globalDiscount

        grossTotal = computeCartSettlementTotal(
            taxableSubtotalPaise=cartSubtotal, totalTaxPaise=0, shippingPaise=500, discountPaise=globalDiscount,
        )
        assert grossTotal == (cartSubtotal - globalDiscount + 500)

    def testOddTaxFloorDivisionFuzzingThorough(self) -> None:
        """Fuzzes 500 odd amounts across all GST slabs checking penny conservation."""
        for rate in [0, 5, 12, 18, 28]:
            for amt in range(1, 501):
                oddAmt = amt * 2 + 1
                resIntra = computeGstBreakdown(oddAmt, rate, isIntraState=True)
                assert resIntra.cgstPaise + resIntra.sgstPaise == resIntra.totalTaxPaise
                assert resIntra.igstPaise == 0
                resInter = computeGstBreakdown(oddAmt, rate, isIntraState=False)
                assert resInter.igstPaise == resInter.totalTaxPaise
                assert resInter.cgstPaise == 0 and resInter.sgstPaise == 0
