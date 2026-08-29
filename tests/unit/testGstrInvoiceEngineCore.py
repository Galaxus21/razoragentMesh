"""Unit tests for GSTR-1 Invoicing Engine, State Code Mapping, and Section 52 TCS."""

from typing import Any, Tuple
import pytest

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
from razoragentMesh.packages.mandateEngine.settlement.settlementExceptions import (
    InvalidPincodeException,
)
from razoragentMesh.packages.mandateEngine.tax.gstrInvoiceEngine import (
    GstrInvoicePayload,
    generateGstrInvoice,
    isPlaceOfSupplyIntraState,
)
from razoragentMesh.packages.mandateEngine.tax.stateCodeMapping import (
    deriveStateCodeFromPincode,
)

testMerchantGstin = "29AAAAA0000A1ZY"
testStateKarnataka = "29"
testStateMaharashtra = "27"


def _createBaseMandates(
    merchantState: str = "29", buyerState: str = "29", buyerPincode: str = "560001",
    unitPricePaise: int = 100000, shippingPaise: int = 2000, discountPaise: int = 0,
) -> Tuple[CartMandate, ExecutionMandate]:
    """Helper creating signed CartMandate and ExecutionMandate for GSTR testing."""
    uPriv, mPriv, aPriv = generateKeyPair()[0], generateKeyPair()[0], generateKeyPair()[0]
    uSigner, mSigner, aSigner = Ed25519Signer(uPriv), Ed25519Signer(mPriv), Ed25519Signer(aPriv)
    intentM = createSignedIntentMandate(
        mandateId="M-I-01", userSigner=uSigner, delegatedAgentDid=aSigner.getAgentDid(),
        maxBudgetPaise=500000, upiCircleDelegationToken="upi_tok", singleTransactionLimitPaise=500000,
    )
    intra = merchantState == buyerState
    taxTotal = (unitPricePaise * 18) // 100
    cgst, sgst, igst = (taxTotal // 2, taxTotal // 2, 0) if intra else (0, 0, taxTotal)
    item = CartItemSchema(
        skuId="SKU-CORE-01", quantity=1, unitPricePaise=unitPricePaise,
        hsnCode="84713010", gstRatePercent=18, lineTotalPaise=unitPricePaise,
    )
    taxBreakdown = TaxBreakdownSchema(cgstPaise=cgst, sgstPaise=sgst, igstPaise=igst, totalTaxPaise=taxTotal)
    grandTotal = unitPricePaise + taxTotal + shippingPaise - discountPaise
    cartM = createSignedCartMandate(
        cartId="M-C-01", merchantSigner=mSigner, merchantGstin=testMerchantGstin,
        merchantStateCode=merchantState, buyerDeliveryPincode=buyerPincode,
        buyerDeliveryStateCode=buyerState, items=[item], taxableSubtotalPaise=unitPricePaise,
        taxBreakdown=taxBreakdown, shippingPaise=shippingPaise, discountPaise=discountPaise,
        totalPaise=grandTotal, inventoryLockToken="lock_tok", inventoryLockExpiresAt=2000000000,
    )
    execM = createSignedExecutionMandate(
        executionId="M-E-01", buyerAgentSigner=aSigner, intentMandate=intentM,
        cartMandate=cartM, settlementAmountPaise=grandTotal, upiCircleToken="upi_tok",
    )
    return cartM, execM


def testDeriveStateCodeFromPincode() -> None:
    """Verifies postal PIN to GST State Code mapping and error handling."""
    assert deriveStateCodeFromPincode("560001") == "29"  # Karnataka
    assert deriveStateCodeFromPincode("110001") == "07"  # Delhi
    assert deriveStateCodeFromPincode("400001") == "27"  # Maharashtra
    assert deriveStateCodeFromPincode("600001") == "33"  # Tamil Nadu
    assert deriveStateCodeFromPincode("700001") == "19"  # West Bengal
    assert deriveStateCodeFromPincode("500001") == "36"  # Telangana
    assert deriveStateCodeFromPincode("800001") == "10"  # Bihar

    with pytest.raises(InvalidPincodeException):
        deriveStateCodeFromPincode("000123")
    with pytest.raises(InvalidPincodeException):
        deriveStateCodeFromPincode("ABCDEF")
    with pytest.raises(InvalidPincodeException):
        deriveStateCodeFromPincode("999999")


def testGstrInvoiceGenerationIntraState() -> None:
    """Verifies intra-state invoice generation and statutory 50/50 tax split."""
    cartM, execM = _createBaseMandates(
        merchantState="29", buyerState="29", buyerPincode="560001",
        unitPricePaise=100000, shippingPaise=2000,
    )
    invoice = generateGstrInvoice(cartM, execM, "INV-2026-INTRA", invoiceTimestamp=1750000000)

    assert isinstance(invoice, GstrInvoicePayload)
    assert invoice.isIntraState is True
    assert invoice.totalCgstPaise == 9000
    assert invoice.totalSgstPaise == 9000
    assert invoice.totalIgstPaise == 0
    assert invoice.totalTcsPaise == 500
    assert invoice.grandTotalPaise == 120000
    assert len(invoice.cryptographicAuditHash) == 64


def testGstrInvoiceGenerationInterState() -> None:
    """Verifies inter-state invoice generation and 100% IGST allocation."""
    cartM, execM = _createBaseMandates(
        merchantState="29", buyerState="27", buyerPincode="400001",
        unitPricePaise=100000, shippingPaise=0,
    )
    invoice = generateGstrInvoice(cartM, execM, "INV-2026-INTER", invoiceTimestamp=1750000000)

    assert isinstance(invoice, GstrInvoicePayload)
    assert invoice.isIntraState is False
    assert invoice.totalCgstPaise == 0
    assert invoice.totalSgstPaise == 0
    assert invoice.totalIgstPaise == 18000
    assert invoice.totalTcsPaise == 500
    assert invoice.grandTotalPaise == 118000
    assert len(invoice.cryptographicAuditHash) == 64


def testGstrInvoiceCryptographicAuditHash() -> None:
    """Verifies deterministic SHA-256 canonical JCS audit hash generation."""
    cartM, execM = _createBaseMandates()
    inv1 = generateGstrInvoice(cartM, execM, "INV-HASH-001", invoiceTimestamp=1750000000)
    inv2 = generateGstrInvoice(cartM, execM, "INV-HASH-001", invoiceTimestamp=1750000000)
    invDifferentNum = generateGstrInvoice(cartM, execM, "INV-HASH-002", invoiceTimestamp=1750000000)

    assert inv1.cryptographicAuditHash == inv2.cryptographicAuditHash
    assert inv1.cryptographicAuditHash != invDifferentNum.cryptographicAuditHash


def testGstrInvoiceMultiItemLineAggregation() -> None:
    """Verifies multi-item cart tax line compilation and aggregation across slabs."""
    uPriv, mPriv, aPriv = generateKeyPair()[0], generateKeyPair()[0], generateKeyPair()[0]
    uSigner, mSigner, aSigner = Ed25519Signer(uPriv), Ed25519Signer(mPriv), Ed25519Signer(aPriv)
    intentM = createSignedIntentMandate(
        mandateId="M-I-MULTI", userSigner=uSigner, delegatedAgentDid=aSigner.getAgentDid(),
        maxBudgetPaise=1000000, upiCircleDelegationToken="upi_tok", singleTransactionLimitPaise=1000000,
    )
    item1 = CartItemSchema(
        skuId="SKU-GRAIN", quantity=2, unitPricePaise=50000,
        hsnCode="1001", gstRatePercent=0, lineTotalPaise=100000,
    )
    item2 = CartItemSchema(
        skuId="SKU-CHAIR", quantity=1, unitPricePaise=200000,
        hsnCode="9401", gstRatePercent=18, lineTotalPaise=200000,
    )
    taxBreakdown = TaxBreakdownSchema(cgstPaise=18000, sgstPaise=18000, igstPaise=0, totalTaxPaise=36000)
    cartM = createSignedCartMandate(
        cartId="M-C-MULTI", merchantSigner=mSigner, merchantGstin=testMerchantGstin,
        merchantStateCode="29", buyerDeliveryPincode="560001", buyerDeliveryStateCode="29",
        items=[item1, item2], taxableSubtotalPaise=300000, taxBreakdown=taxBreakdown,
        shippingPaise=5000, discountPaise=1000, totalPaise=340000,
        inventoryLockToken="lock_multi", inventoryLockExpiresAt=2000000000,
    )
    execM = createSignedExecutionMandate(
        executionId="M-E-MULTI", buyerAgentSigner=aSigner, intentMandate=intentM,
        cartMandate=cartM, settlementAmountPaise=340000, upiCircleToken="upi_tok",
    )
    invoice = generateGstrInvoice(cartM, execM, "INV-MULTI-01", invoiceTimestamp=1750000000)

    assert len(invoice.lineItems) == 2
    assert invoice.taxableAmountPaise == 300000
    assert invoice.totalCgstPaise == 18000
    assert invoice.totalSgstPaise == 18000
    assert invoice.totalTcsPaise == 1500
    assert invoice.grandTotalPaise == 340000


def testIsPlaceOfSupplyIntraState() -> None:
    """Verifies place of supply intra-state classification helper."""
    assert isPlaceOfSupplyIntraState("29", "29") is True
    assert isPlaceOfSupplyIntraState(" 29 ", "29") is True
    assert isPlaceOfSupplyIntraState("29", "27") is False
    assert isPlaceOfSupplyIntraState("07", "29") is False
