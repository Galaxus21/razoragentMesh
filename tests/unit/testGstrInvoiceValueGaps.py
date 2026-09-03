"""Value-assertion tests closing surviving mutants in the GSTR-1 invoice engine.

Each test pins an exact rupee/paise figure the existing suite never checked, so a
silent corruption of a tax line, an emptied invoice, or a zeroed money tuple is
caught instead of hashing cleanly against its own corrupted self.
"""

from typing import Tuple

from razoragentMesh.packages.mandateEngine.crypto.cryptoKeyUtils import generateKeyPair
from razoragentMesh.packages.mandateEngine.crypto.ed25519Signer import Ed25519Signer
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
from razoragentMesh.packages.mandateEngine.tax.gstrInvoiceEngine import (
    GstrLineItem,
    _buildInvoiceDict,
    generateGstrInvoice,
)

testMerchantGstin = "29AAAAA0000A1ZY"


def _buildTwoItemCart() -> Tuple[CartMandate, ExecutionMandate]:
    """Intra-state cart: SKU-A Rs.1,000 @ 18% and SKU-B Rs.2,000 @ 18%, both taxed."""
    uPriv, mPriv, aPriv = generateKeyPair()[0], generateKeyPair()[0], generateKeyPair()[0]
    uSigner, mSigner, aSigner = Ed25519Signer(uPriv), Ed25519Signer(mPriv), Ed25519Signer(aPriv)
    intentM = createSignedIntentMandate(
        mandateId="M-I-VG", userSigner=uSigner, delegatedAgentDid=aSigner.getAgentDid(),
        maxBudgetPaise=1000000, upiCircleDelegationToken="upi_tok", singleTransactionLimitPaise=1000000,
    )
    itemA = CartItemSchema(
        skuId="SKU-A", quantity=1, unitPricePaise=100000,
        hsnCode="84713010", gstRatePercent=18, lineTotalPaise=100000,
    )
    itemB = CartItemSchema(
        skuId="SKU-B", quantity=1, unitPricePaise=200000,
        hsnCode="84713010", gstRatePercent=18, lineTotalPaise=200000,
    )
    taxBreakdown = TaxBreakdownSchema(cgstPaise=27000, sgstPaise=27000, igstPaise=0, totalTaxPaise=54000)
    cartM = createSignedCartMandate(
        cartId="M-C-VG", merchantSigner=mSigner, merchantGstin=testMerchantGstin,
        merchantStateCode="29", buyerDeliveryPincode="560001", buyerDeliveryStateCode="29",
        items=[itemA, itemB], taxableSubtotalPaise=300000, taxBreakdown=taxBreakdown,
        shippingPaise=0, discountPaise=0, totalPaise=354000,
        inventoryLockToken="lock_vg", inventoryLockExpiresAt=2000000000,
    )
    execM = createSignedExecutionMandate(
        executionId="M-E-VG", buyerAgentSigner=aSigner, intentMandate=intentM,
        cartMandate=cartM, settlementAmountPaise=354000, upiCircleToken="upi_tok",
    )
    return cartM, execM


def testPerLineTotalEqualsTaxablePlusAllGstComponents() -> None:
    """Kills L131 '+' -> '-': the printed line total on a GST invoice must equal
    taxable + every GST component, else the customer is billed the wrong money and
    the seller's GSTR-1 line fails reconciliation. A Rs.1,000 line at 18% is 118000
    paise; the sign flip would silently produce 82000."""
    cartM, execM = _buildTwoItemCart()
    invoice = generateGstrInvoice(cartM, execM, "INV-VG-LINE", invoiceTimestamp=1750000000)

    for line in invoice.lineItems:
        assert line.totalLinePaise == (
            line.taxableAmountPaise + line.cgstPaise + line.sgstPaise + line.igstPaise
        )

    byId = {line.skuId: line for line in invoice.lineItems}
    # Exact anchors so the formula cannot drift in lockstep with the assertion.
    assert byId["SKU-A"].totalLinePaise == 118000
    assert byId["SKU-B"].totalLinePaise == 236000


def testInvoiceDictKeepsSuppliedLineItems() -> None:
    """Kills L156 'is not None' -> 'is None': that flip drops every line item,
    canonicalizing an invoice with zero lines. A GSTR-1 filing with no lines
    understates output tax and is legally void. Assert the passed lines survive
    by count and SKU id, not just by a self-consistent hash."""
    lineA = GstrLineItem(
        skuId="SKU-A", hsnCode="84713010", quantity=1, unitPricePaise=100000,
        taxableAmountPaise=100000, gstRatePercent=18, cgstPaise=9000, sgstPaise=9000,
        igstPaise=0, totalLinePaise=118000,
    )
    lineB = GstrLineItem(
        skuId="SKU-B", hsnCode="84713010", quantity=1, unitPricePaise=200000,
        taxableAmountPaise=200000, gstRatePercent=18, cgstPaise=18000, sgstPaise=18000,
        igstPaise=0, totalLinePaise=236000,
    )
    totals = (300000, 27000, 27000, 0, 54000, 354000)
    invoiceDict = _buildInvoiceDict(
        items=[lineA, lineB], totals=totals, invoiceNumber="INV-VG-ITEMS",
        invoiceDate="2026-01-01", isIntraState=True,
    )

    assert len(invoiceDict["lineItems"]) == 2
    assert [row["skuId"] for row in invoiceDict["lineItems"]] == ["SKU-A", "SKU-B"]


def testInvoiceDictKeepsSuppliedMoneyTotals() -> None:
    """Kills L157 'or' -> 'and': with both operands truthy, 'and' returns the
    right-hand zero tuple, so every money figure on the canonicalized invoice
    becomes zero while the hash still recomputes cleanly. Assert each supplied
    figure survives into the dict. Observability: confirmed directly through
    _buildInvoiceDict (see notes) -- the public payload reads totals separately,
    so only a direct call exposes this mutant on the money fields."""
    totals = (300000, 27000, 27000, 0, 54000, 354000)
    invoiceDict = _buildInvoiceDict(
        items=[], totals=totals, invoiceNumber="INV-VG-TOTALS",
        invoiceDate="2026-01-01", isIntraState=True,
    )

    assert invoiceDict["taxableAmountPaise"] == 300000
    assert invoiceDict["totalCgstPaise"] == 27000
    assert invoiceDict["totalSgstPaise"] == 27000
    assert invoiceDict["totalIgstPaise"] == 0
    assert invoiceDict["totalTaxPaise"] == 54000
    assert invoiceDict["grandTotalPaise"] == 354000
