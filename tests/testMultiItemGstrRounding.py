"""Adversarial Benchmark Module 1 — Multi-Item GSTR-1 Mixed Tax & Penny Conservation.

Covers:
- TC-11: Multi-item inter-state GSTR-1 mixed tax reconciliation across 4 slabs (0%, 5%, 18%, 28%)
         with Section 52 TCS withholding and RFC 8785 JCS SHA-256 audit digest.
- TC-12: Asymmetric discount allocation & penny conservation across odd-priced items
         and odd-tax GST floor division conservation.
"""

from typing import Any, Tuple
import pytest

from razoragentMesh.packages.mandateEngine.crypto.cryptoKeyUtils import generateKeyPair
from razoragentMesh.packages.mandateEngine.crypto.ed25519Signer import Ed25519Signer
from razoragentMesh.packages.mandateEngine.crypto.jcsCanonicalizer import (
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
from razoragentMesh.packages.mandateEngine.mandates.intentMandateSchema import (
    IntentMandate,
)
from razoragentMesh.packages.mandateEngine.mandates.mandateFactory import (
    createSignedCartMandate,
    createSignedExecutionMandate,
    createSignedIntentMandate,
)
from razoragentMesh.packages.mandateEngine.tax.gstrInvoiceEngine import (
    GstrInvoicePayload,
    generateGstrInvoice,
    isPlaceOfSupplyIntraState,
)
from razoragentMesh.packages.mandateEngine.verification.arithmeticEnclave import (
    computeCartSettlementTotal,
    computeGstBreakdown,
    computeLineItemTotal,
    computeTcsWithholding,
)

sampleMerchantGstin: str = "29AABCU9603R1ZM"
karnatakaStateCode: str = "29"
maharashtraStateCode: str = "27"
deliveryPincodeMumbai: str = "400001"
sampleInvoiceNumberTc11: str = "INV-TC11-GSTR-01"
defaultShippingPaiseTc11: int = 5000
defaultDiscountPaiseTc11: int = 2000
fixedTimestampTc11: int = 1750000000
expectedAuditHashLength: int = 64
globalDiscountTc12: int = 15000
unitPriceItem1Tc12: int = 33333
unitPriceItem2Tc12: int = 55555
unitPriceItem3Tc12: int = 77777


def _createFourSlabLineItems() -> list[CartItemSchema]:
    """Constructs 4 line items spanning GST slabs 0%, 5%, 18%, 28%."""
    return [
        CartItemSchema(
            skuId="SKU-GST-0",
            quantity=1,
            unitPricePaise=100000,
            hsnCode="0101",
            gstRatePercent=0,
            lineTotalPaise=100000,
        ),
        CartItemSchema(
            skuId="SKU-GST-5",
            quantity=2,
            unitPricePaise=100000,
            hsnCode="1001",
            gstRatePercent=5,
            lineTotalPaise=200000,
        ),
        CartItemSchema(
            skuId="SKU-GST-18",
            quantity=1,
            unitPricePaise=300000,
            hsnCode="8504",
            gstRatePercent=18,
            lineTotalPaise=300000,
        ),
        CartItemSchema(
            skuId="SKU-GST-28",
            quantity=1,
            unitPricePaise=400000,
            hsnCode="8703",
            gstRatePercent=28,
            lineTotalPaise=400000,
        ),
    ]


def _setupSignedMandatesTc11(
    items: list[CartItemSchema],
    taxableSubtotal: int,
    totalTax: int,
    grossTotal: int,
) -> Tuple[IntentMandate, CartMandate, ExecutionMandate]:
    """Generates valid cryptographic mandate triplet for TC-11."""
    userPriv, _ = generateKeyPair()
    merchantPriv, _ = generateKeyPair()
    agentPriv, _ = generateKeyPair()

    userSigner = Ed25519Signer(userPriv)
    merchantSigner = Ed25519Signer(merchantPriv)
    agentSigner = Ed25519Signer(agentPriv)

    intentMandate = createSignedIntentMandate(
        mandateId="M-I-TC11-01",
        userSigner=userSigner,
        delegatedAgentDid=agentSigner.getAgentDid(),
        maxBudgetPaise=2000000,
        upiCircleDelegationToken="upi_tok_tc11",
        singleTransactionLimitPaise=2000000,
    )

    taxBreakdown = TaxBreakdownSchema(
        cgstPaise=0,
        sgstPaise=0,
        igstPaise=totalTax,
        totalTaxPaise=totalTax,
    )

    cartMandate = createSignedCartMandate(
        cartId="M-C-TC11-01",
        merchantSigner=merchantSigner,
        merchantGstin=sampleMerchantGstin,
        merchantStateCode=karnatakaStateCode,
        buyerDeliveryPincode=deliveryPincodeMumbai,
        buyerDeliveryStateCode=maharashtraStateCode,
        items=items,
        taxableSubtotalPaise=taxableSubtotal,
        taxBreakdown=taxBreakdown,
        shippingPaise=defaultShippingPaiseTc11,
        discountPaise=defaultDiscountPaiseTc11,
        totalPaise=grossTotal,
        inventoryLockToken="lock_tok_tc11",
        inventoryLockExpiresAt=2000000000,
    )

    executionMandate = createSignedExecutionMandate(
        executionId="M-E-TC11-01",
        buyerAgentSigner=agentSigner,
        intentMandate=intentMandate,
        cartMandate=cartMandate,
        settlementAmountPaise=grossTotal,
        upiCircleToken="upi_tok_tc11",
        timestamp=fixedTimestampTc11,
    )

    return intentMandate, cartMandate, executionMandate


def testTc11MultiItemInterStateGstr1MixedTaxReconciliation() -> None:
    """TC-11: 4-item inter-state GSTR-1 mixed tax reconciliation and Section 52 TCS."""
    assert not isPlaceOfSupplyIntraState(karnatakaStateCode, maharashtraStateCode)

    lineItems = _createFourSlabLineItems()
    taxableSubtotal = sum(computeLineItemTotal(i.unitPricePaise, i.quantity) for i in lineItems)
    assert taxableSubtotal == 1000000

    expectedPerLineIgst = [0, 10000, 54000, 112000]
    totalIgst = sum(expectedPerLineIgst)
    assert totalIgst == 176000

    grossTotal = computeCartSettlementTotal(
        taxableSubtotalPaise=taxableSubtotal,
        totalTaxPaise=totalIgst,
        shippingPaise=defaultShippingPaiseTc11,
        discountPaise=defaultDiscountPaiseTc11,
    )
    assert grossTotal == 1179000

    _, cartMandate, executionMandate = _setupSignedMandatesTc11(
        lineItems, taxableSubtotal, totalIgst, grossTotal
    )

    invoice = generateGstrInvoice(
        cartMandate=cartMandate,
        executionMandate=executionMandate,
        invoiceNumber=sampleInvoiceNumberTc11,
        invoiceTimestamp=fixedTimestampTc11,
    )

    assert isinstance(invoice, GstrInvoicePayload)
    assert invoice.isIntraState is False
    assert invoice.totalCgstPaise == 0
    assert invoice.totalSgstPaise == 0
    assert invoice.totalIgstPaise == 176000
    assert invoice.totalTaxPaise == 176000

    tcsResult = computeTcsWithholding(taxableSubtotal, isIntraState=False)
    assert tcsResult["tcsIgstPaise"] == 10000
    assert invoice.totalTcsPaise == 10000
    assert invoice.grandTotalPaise == 1179000
    assert len(invoice.cryptographicAuditHash) == expectedAuditHashLength

    for idx, item in enumerate(invoice.lineItems):
        assert item.cgstPaise == 0
        assert item.sgstPaise == 0
        assert item.igstPaise == expectedPerLineIgst[idx]


def testTc12AsymmetricDiscountAllocationAndPennyConservation() -> None:
    """TC-12: Zero penny drift (Δ = 0) in global discount allocation over odd-priced items."""
    # Test case 1: Odd ratio with non-zero remainder (10000 paise across 33333, 55555, 77777)
    itemPrices = [unitPriceItem1Tc12, unitPriceItem2Tc12, unitPriceItem3Tc12]
    cartSubtotal = sum(itemPrices)
    assert cartSubtotal == 166665

    discountPaise = 10000
    rawDiscounts = [(discountPaise * price) // cartSubtotal for price in itemPrices]
    assert rawDiscounts == [2000, 3333, 4666]
    allocatedSum = sum(rawDiscounts)
    driftRemainder = discountPaise - allocatedSum
    assert driftRemainder == 1

    # Penny conservation rule: Allocate remainder to the highest priced item
    finalDiscounts = list(rawDiscounts)
    finalDiscounts[-1] += driftRemainder
    assert finalDiscounts == [2000, 3333, 4667]
    assert sum(finalDiscounts) == discountPaise

    netLineTotals = [price - disc for price, disc in zip(itemPrices, finalDiscounts)]
    assert netLineTotals == [31333, 52222, 73110]
    expectedNetSubtotal = cartSubtotal - discountPaise
    assert sum(netLineTotals) == expectedNetSubtotal

    # Test case 2: 15000 paise discount with 3:5:7 exact ratio
    raw15k = [(globalDiscountTc12 * price) // cartSubtotal for price in itemPrices]
    assert raw15k == [3000, 5000, 7000]
    assert sum(raw15k) == globalDiscountTc12

    grossSettlement = computeCartSettlementTotal(
        taxableSubtotalPaise=cartSubtotal,
        totalTaxPaise=0,
        shippingPaise=1000,
        discountPaise=globalDiscountTc12,
    )
    assert grossSettlement == (cartSubtotal - globalDiscountTc12 + 1000)


def testTc12OddTaxFloorDivisionConservation() -> None:
    """TC-12: Odd-tax GST floor division conservation without penny loss."""
    gst101 = computeGstBreakdown(101, 5, isIntraState=True)
    assert gst101["totalTaxPaise"] == 5
    assert gst101["cgstPaise"] == 2
    assert gst101["sgstPaise"] == 3
    assert gst101["cgstPaise"] + gst101["sgstPaise"] == gst101["totalTaxPaise"]

    gst33333 = computeGstBreakdown(33333, 5, isIntraState=True)
    assert gst33333["totalTaxPaise"] == 1666
    assert gst33333["cgstPaise"] == 666
    assert gst33333["sgstPaise"] == 1000
    assert gst33333["cgstPaise"] + gst33333["sgstPaise"] == gst33333["totalTaxPaise"]

    gst77777 = computeGstBreakdown(77777, 18, isIntraState=False)
    assert gst77777["totalTaxPaise"] == 13999
    assert gst77777["igstPaise"] == 13999
    assert gst77777["cgstPaise"] == 0
    assert gst77777["sgstPaise"] == 0

