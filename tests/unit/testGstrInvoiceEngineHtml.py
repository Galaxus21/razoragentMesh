"""Unit tests for GSTR-1 HTML invoice generation, responsive CSS, and XSS sanitization."""

import pytest

from razoragentMesh.packages.mandateEngine.tax.gstrInvoiceEngine import (
    GstrInvoicePayload,
    GstrLineItem,
)
from razoragentMesh.packages.mandateEngine.tax.gstrInvoiceHtmlRenderer import (
    formatPaiseToInr,
    renderGstrInvoiceHtml,
)


@pytest.fixture
def sampleIntraStateInvoice() -> GstrInvoicePayload:
    """Deterministic intra-state GSTR-1 invoice payload fixture."""
    line = GstrLineItem(
        skuId="SKU-CHAIR-001", hsnCode="9401", quantity=2, unitPricePaise=200000,
        taxableAmountPaise=400000, gstRatePercent=18, cgstPaise=36000,
        sgstPaise=36000, igstPaise=0, totalLinePaise=472000,
    )
    return GstrInvoicePayload(
        invoiceNumber="INV-2026-INTRA-001", invoiceDate="2026-08-24T12:00:00+00:00",
        sellerGstin="29AAAAA0000A1ZY", merchantStateCode="29", placeOfSupplyStateCode="29",
        isIntraState=True, lineItems=[line], taxableAmountPaise=400000,
        totalCgstPaise=36000, totalSgstPaise=36000, totalIgstPaise=0,
        totalTaxPaise=72000, totalTcsPaise=4000, shippingPaise=5000,
        discountPaise=2000, grandTotalPaise=475000,
        cryptographicAuditHash="a1b2c3d4e5f60718293a4b5c6d7e8f90a1b2c3d4e5f60718293a4b5c6d7e8f90",
    )


@pytest.fixture
def sampleInterStateMultiSlabInvoice() -> GstrInvoicePayload:
    """4-slab inter-state GSTR-1 invoice payload fixture."""
    lines = [
        GstrLineItem(
            skuId="SKU-GRAIN-000", hsnCode="1001", quantity=1, unitPricePaise=50000,
            taxableAmountPaise=50000, gstRatePercent=0, cgstPaise=0, sgstPaise=0,
            igstPaise=0, totalLinePaise=50000,
        ),
        GstrLineItem(
            skuId="SKU-MED-005", hsnCode="3004", quantity=2, unitPricePaise=100000,
            taxableAmountPaise=200000, gstRatePercent=5, cgstPaise=0, sgstPaise=0,
            igstPaise=10000, totalLinePaise=210000,
        ),
        GstrLineItem(
            skuId="SKU-ELEC-018", hsnCode="8504", quantity=1, unitPricePaise=300000,
            taxableAmountPaise=300000, gstRatePercent=18, cgstPaise=0, sgstPaise=0,
            igstPaise=54000, totalLinePaise=354000,
        ),
        GstrLineItem(
            skuId="SKU-AUTO-028", hsnCode="8703", quantity=1, unitPricePaise=400000,
            taxableAmountPaise=400000, gstRatePercent=28, cgstPaise=0, sgstPaise=0,
            igstPaise=112000, totalLinePaise=512000,
        ),
    ]
    return GstrInvoicePayload(
        invoiceNumber="INV-2026-INTER-4SLAB", invoiceDate="2026-08-24T14:30:00+00:00",
        sellerGstin="29AAAAA0000A1ZY", merchantStateCode="29", placeOfSupplyStateCode="27",
        isIntraState=False, lineItems=lines, taxableAmountPaise=950000,
        totalCgstPaise=0, totalSgstPaise=0, totalIgstPaise=176000,
        totalTaxPaise=176000, totalTcsPaise=9500, shippingPaise=0,
        discountPaise=0, grandTotalPaise=1126000,
        cryptographicAuditHash="f0e1d2c3b4a5968778695a4b3c2d1e0ff0e1d2c3b4a5968778695a4b3c2d1e0f",
    )


def testRenderGstrInvoiceHtmlDocStructure(sampleIntraStateInvoice: GstrInvoicePayload) -> None:
    """Verifies valid HTML5 boilerplate, UTF-8 meta, and @media print CSS styles."""
    htmlDoc = renderGstrInvoiceHtml(sampleIntraStateInvoice)
    assert htmlDoc.startswith("<!DOCTYPE html>")
    assert '<html lang="en">' in htmlDoc
    assert '<meta charset="UTF-8">' in htmlDoc
    assert '<meta name="viewport"' in htmlDoc
    assert "<style>" in htmlDoc
    assert "@media print" in htmlDoc
    assert "@page {" in htmlDoc
    assert "-webkit-print-color-adjust: exact;" in htmlDoc
    assert "page-break-inside: avoid;" in htmlDoc


def testRenderGstrInvoiceHtmlHeaderMetadata(sampleIntraStateInvoice: GstrInvoicePayload) -> None:
    """Verifies Tax Invoice title, invoice number, date, GSTIN, and merchant state resolution."""
    htmlDoc = renderGstrInvoiceHtml(sampleIntraStateInvoice)
    assert "<h1>Tax Invoice</h1>" in htmlDoc
    assert "Invoice #: INV-2026-INTRA-001" in htmlDoc
    assert "Date: 2026-08-24T12:00:00+00:00" in htmlDoc
    assert "29AAAAA0000A1ZY" in htmlDoc
    assert "29 - Karnataka" in htmlDoc


def testRenderGstrInvoiceHtmlIntraStateClassification(sampleIntraStateInvoice: GstrInvoicePayload) -> None:
    """Verifies intra-state supply label, CGST + SGST tax split, and Section 52 TCS split."""
    htmlDoc = renderGstrInvoiceHtml(sampleIntraStateInvoice)
    assert "INTRA-STATE (CGST + SGST)" in htmlDoc
    assert "0.25% CGST + 0.25% SGST (50 bps)" in htmlDoc
    assert "₹360.00" in htmlDoc
    assert "₹40.00" in htmlDoc


def testRenderGstrInvoiceHtmlInterStateClassification(
    sampleInterStateMultiSlabInvoice: GstrInvoicePayload,
) -> None:
    """Verifies inter-state supply label, POS state Maharashtra (27), and 100% IGST allocation."""
    htmlDoc = renderGstrInvoiceHtml(sampleInterStateMultiSlabInvoice)
    assert "INTER-STATE (IGST)" in htmlDoc
    assert "27 - Maharashtra" in htmlDoc
    assert "0.5% IGST (50 bps)" in htmlDoc
    assert "₹1760.00" in htmlDoc
    assert "₹95.00" in htmlDoc


def testRenderGstrInvoiceHtmlItemizedLineItemsTable(
    sampleInterStateMultiSlabInvoice: GstrInvoicePayload,
) -> None:
    """Verifies 4-slab itemized table contains all HSN codes, rates, and paise formatted values."""
    htmlDoc = renderGstrInvoiceHtml(sampleInterStateMultiSlabInvoice)
    for expectedHsn in ["1001", "3004", "8504", "8703"]:
        assert expectedHsn in htmlDoc
    for expectedSku in ["SKU-GRAIN-000", "SKU-MED-005", "SKU-ELEC-018", "SKU-AUTO-028"]:
        assert expectedSku in htmlDoc
    assert "0%" in htmlDoc
    assert "5%" in htmlDoc
    assert "18%" in htmlDoc
    assert "28%" in htmlDoc
    assert "₹9500.00" in htmlDoc


def testRenderGstrInvoiceHtmlZeroTaxAndExemptGoods() -> None:
    """Verifies 0% exempt goods invoice produces zero tax without arithmetic drift."""
    line = GstrLineItem(
        skuId="SKU-ORGANIC-MILK", hsnCode="0401", quantity=5, unitPricePaise=6000,
        taxableAmountPaise=30000, gstRatePercent=0, cgstPaise=0, sgstPaise=0,
        igstPaise=0, totalLinePaise=30000,
    )
    inv = GstrInvoicePayload(
        invoiceNumber="INV-EXEMPT-001", invoiceDate="2026-08-24T10:00:00+00:00",
        sellerGstin="29AAAAA0000A1ZY", merchantStateCode="29", placeOfSupplyStateCode="29",
        isIntraState=True, lineItems=[line], taxableAmountPaise=30000,
        totalCgstPaise=0, totalSgstPaise=0, totalIgstPaise=0, totalTaxPaise=0,
        totalTcsPaise=300, shippingPaise=4000, discountPaise=0,
        grandTotalPaise=34000, cryptographicAuditHash="00" * 32,
    )
    htmlDoc = renderGstrInvoiceHtml(inv)
    assert "SKU-ORGANIC-MILK" in htmlDoc
    assert "0401" in htmlDoc
    assert "₹300.00" in htmlDoc
    assert "₹340.00" in htmlDoc


def testRenderGstrInvoiceHtmlFinancialSummaryAndTotals(sampleIntraStateInvoice: GstrInvoicePayload) -> None:
    """Verifies taxable subtotal, GST total, shipping, discount subtraction, and grand total."""
    htmlDoc = renderGstrInvoiceHtml(sampleIntraStateInvoice)
    assert "Taxable Subtotal:</span><span>₹4000.00" in htmlDoc
    assert "Total GST Amount:</span><span>₹720.00" in htmlDoc
    assert "Shipping &amp; Handling:</span><span>₹50.00" in htmlDoc
    assert "Promotional Discount:</span><span>-₹20.00" in htmlDoc
    assert "Grand Total:</span><span>₹4750.00" in htmlDoc


def testRenderGstrInvoiceHtmlSection52TcsWithholding(sampleIntraStateInvoice: GstrInvoicePayload) -> None:
    """Verifies Section 52 TCS withholding breakdown box and net taxable base."""
    htmlDoc = renderGstrInvoiceHtml(sampleIntraStateInvoice)
    assert "Section 52 TCS Withholding Breakdown" in htmlDoc
    assert "Net Taxable Base:</span><span>₹4000.00" in htmlDoc
    assert "Total TCS Withheld:</span><span>₹40.00" in htmlDoc


def testRenderGstrInvoiceHtmlSha256AuditStamp(sampleIntraStateInvoice: GstrInvoicePayload) -> None:
    """Verifies 64-character SHA-256 cryptographic audit hash in monospace code badge."""
    htmlDoc = renderGstrInvoiceHtml(sampleIntraStateInvoice)
    assert "Cryptographic Verification &amp; Audit Stamp" in htmlDoc
    assert "Canonical JCS SHA-256 Digest (RFC 8785):" in htmlDoc
    assert sampleIntraStateInvoice.cryptographicAuditHash in htmlDoc
    assert f'<code class="audit-hash-code">{sampleIntraStateInvoice.cryptographicAuditHash}</code>' in htmlDoc


def testRenderGstrInvoiceHtmlRupeeFormattingHelper() -> None:
    """Verifies formatPaiseToInr integer paise to INR formatting with zero float math."""
    assert formatPaiseToInr(0) == "₹0.00"
    assert formatPaiseToInr(1) == "₹0.01"
    assert formatPaiseToInr(9) == "₹0.09"
    assert formatPaiseToInr(99) == "₹0.99"
    assert formatPaiseToInr(100) == "₹1.00"
    assert formatPaiseToInr(1050) == "₹10.50"
    assert formatPaiseToInr(4200) == "₹42.00"
    assert formatPaiseToInr(100000) == "₹1000.00"
    assert formatPaiseToInr(1179000) == "₹11790.00"
    assert formatPaiseToInr(-5000) == "-₹50.00"
    assert formatPaiseToInr(-5) == "-₹0.05"


def testRenderGstrInvoiceHtmlAdversarialEscapingAndXssPrevention() -> None:
    """Verifies html.escape sanitization prevents script injection and HTML breakout."""
    adversarialLine = GstrLineItem(
        skuId='SKU<script>alert("xss")</script>', hsnCode="9401", quantity=1,
        unitPricePaise=10000, taxableAmountPaise=10000, gstRatePercent=18,
        cgstPaise=900, sgstPaise=900, igstPaise=0, totalLinePaise=11800,
    )
    adversarialInvoice = GstrInvoicePayload(
        invoiceNumber='INV-" onload="alert(1)"', invoiceDate="2026-08-24T12:00:00Z",
        sellerGstin="29AAAAA0000A1ZY", merchantStateCode="29", placeOfSupplyStateCode="29",
        isIntraState=True, lineItems=[adversarialLine], taxableAmountPaise=10000,
        totalCgstPaise=900, totalSgstPaise=900, totalIgstPaise=0, totalTaxPaise=1800,
        totalTcsPaise=100, shippingPaise=0, discountPaise=0, grandTotalPaise=11800,
        cryptographicAuditHash="11" * 32,
    )
    htmlDoc = renderGstrInvoiceHtml(
        adversarialInvoice,
        merchantLegalName='Merchant<img src=x onerror=alert("hack")>',
        buyerLegalName="Buyer<b>Bold</b>",
    )
    assert "<script>" not in htmlDoc
    assert '<img src=x onerror=alert("hack")>' not in htmlDoc
    assert "&lt;script&gt;alert(&quot;xss&quot;)&lt;/script&gt;" in htmlDoc
    assert "Merchant&lt;img src=x onerror=alert(&quot;hack&quot;)&gt;" in htmlDoc
    assert "Buyer&lt;b&gt;Bold&lt;/b&gt;" in htmlDoc


def testRenderGstrInvoiceHtmlCustomPartyNamesAndExports(sampleIntraStateInvoice: GstrInvoicePayload) -> None:
    """Verifies custom merchant/buyer legal names and public package re-exports."""
    htmlDoc = renderGstrInvoiceHtml(
        sampleIntraStateInvoice,
        merchantLegalName="Acme Autonomous Supplies Pvt Ltd",
        buyerLegalName="Nexus Procurement AI Agent",
    )
    assert "Acme Autonomous Supplies Pvt Ltd" in htmlDoc
    assert "Nexus Procurement AI Agent" in htmlDoc

    from razoragentMesh.packages.mandateEngine.tax import (
        formatPaiseToInr as taxFormatPaise,
        renderGstrInvoiceHtml as taxRenderGstr,
    )
    assert taxFormatPaise is formatPaiseToInr
    assert taxRenderGstr is renderGstrInvoiceHtml
