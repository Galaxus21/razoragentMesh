"""Unit tests for GSTR-1 Invoicing Engine and State Code Mapping."""

import pytest
from razoragentMesh.packages.mandateEngine.mandates.cartMandateSchema import (
    CartItemSchema,
    CartMandate,
    TaxBreakdownSchema,
)
from razoragentMesh.packages.mandateEngine.crypto.cryptoKeyUtils import generateKeyPair
from razoragentMesh.packages.mandateEngine.crypto.ed25519Signer import Ed25519Signer
from razoragentMesh.packages.mandateEngine.mandates.executionMandateSchema import ExecutionMandate
from razoragentMesh.packages.mandateEngine.tax.gstrInvoiceEngine import (
    GstrInvoicePayload,
    generateGstrInvoice,
    isPlaceOfSupplyIntraState,
)
from razoragentMesh.packages.mandateEngine.mandates.intentMandateSchema import IntentMandate
from razoragentMesh.packages.mandateEngine.mandates.mandateFactory import (
    createSignedCartMandate,
    createSignedExecutionMandate,
    createSignedIntentMandate,
)
from razoragentMesh.packages.mandateEngine.settlement.settlementExceptions import (
    InvalidPincodeException,
)
from razoragentMesh.packages.mandateEngine.tax.stateCodeMapping import (
    deriveStateCodeFromPincode,
)


def testDeriveStateCodeFromPincode() -> None:
    """Verifies postal PIN to GST State Code mapping."""
    assert deriveStateCodeFromPincode("560001") == "29"  # Karnataka
    assert deriveStateCodeFromPincode("110001") == "07"  # Delhi
    assert deriveStateCodeFromPincode("400001") == "27"  # Maharashtra
    assert deriveStateCodeFromPincode("600001") == "33"  # Tamil Nadu
    assert deriveStateCodeFromPincode("700001") == "19"  # West Bengal

    with pytest.raises(InvalidPincodeException):
        deriveStateCodeFromPincode("000123")  # Bad PIN


def testGstrInvoiceGenerationIntraState() -> None:
    """Verifies intra-state invoice generation and cryptographic audit digest."""
    uPriv, _ = generateKeyPair()
    mPriv, _ = generateKeyPair()
    aPriv, _ = generateKeyPair()

    uSigner = Ed25519Signer(uPriv)
    mSigner = Ed25519Signer(mPriv)
    aSigner = Ed25519Signer(aPriv)

    intentM = createSignedIntentMandate(
        mandateId="M-I-01",
        userSigner=uSigner,
        delegatedAgentDid=aSigner.getAgentDid(),
        maxBudgetPaise=500000,
        upiCircleDelegationToken="upi_tok",
        singleTransactionLimitPaise=500000,
    )

    item = CartItemSchema(
        skuId="SKU-INTRA-01",
        quantity=1,
        unitPricePaise=100000,
        hsnCode="84713010",
        gstRatePercent=18,
        lineTotalPaise=100000,
    )
    taxBreakdown = TaxBreakdownSchema(
        cgstPaise=9000,
        sgstPaise=9000,
        igstPaise=0,
        totalTaxPaise=18000,
    )
    cartM = createSignedCartMandate(
        cartId="M-C-01",
        merchantSigner=mSigner,
        merchantGstin="29AAAAA0000A1Z5",
        merchantStateCode="29",
        buyerDeliveryPincode="560001",
        buyerDeliveryStateCode="29",
        items=[item],
        taxableSubtotalPaise=100000,
        taxBreakdown=taxBreakdown,
        shippingPaise=2000,
        discountPaise=0,
        totalPaise=120000,
        inventoryLockToken="lock_tok",
        inventoryLockExpiresAt=2000000000,
    )

    execM = createSignedExecutionMandate(
        executionId="M-E-01",
        buyerAgentSigner=aSigner,
        intentMandate=intentM,
        cartMandate=cartM,
        settlementAmountPaise=120000,
        upiCircleToken="upi_tok",
    )

    invoice = generateGstrInvoice(cartM, execM, "INV-2026-001", invoiceTimestamp=1750000000)
    assert isinstance(invoice, GstrInvoicePayload)
    assert invoice.isIntraState is True
    assert invoice.totalCgstPaise == 9000
    assert invoice.totalSgstPaise == 9000
    assert invoice.totalIgstPaise == 0
    assert invoice.totalTcsPaise == 1000  # 1% TCS on 100000 paise = 1000 paise
    assert len(invoice.cryptographicAuditHash) == 64
