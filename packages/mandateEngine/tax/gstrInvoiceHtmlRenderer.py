"""Print-ready GSTR-1 compliant HTML invoice generator with integer paise arithmetic."""

import html

from .gstrInvoiceEngine import GstrInvoicePayload, GstrLineItem
from .gstrInvoiceHtmlStyles import invoiceBaseStyles, resolveStateName


def renderGstrInvoiceHtml(
    invoice: GstrInvoicePayload,
    merchantLegalName: str = "RazorAgent Verified Merchant",
    buyerLegalName: str = "Autonomous Agent Buyer",
) -> str:
    """Renders an audit-ready, print-compliant HTML GSTR-1 tax invoice document."""
    headerHtml = _renderHeader(invoice, merchantLegalName, buyerLegalName)
    tableHtml = _renderLineItemsTable(invoice.lineItems, invoice)
    summaryHtml = _renderSummaryAndTcs(invoice)
    stampHtml = _renderAuditVerificationStamp(invoice)

    return f"""<!DOCTYPE html>
<html lang="en">
<head>
  <meta charset="UTF-8">
  <meta name="viewport" content="width=device-width, initial-scale=1.0">
  <title>Tax Invoice - {html.escape(invoice.invoiceNumber, quote=True)}</title>
  <style>
{invoiceBaseStyles}
  </style>
</head>
<body>
  <div class="invoice-card">
    {headerHtml}
    {tableHtml}
    {summaryHtml}
    {stampHtml}
  </div>
</body>
</html>"""


def formatPaiseToInr(paiseAmount: int) -> str:
    """Formats integer paise into an Indian Rupee string without floating point arithmetic."""
    if paiseAmount < 0:
        absPaise = abs(paiseAmount)
        return f"-₹{absPaise // 100}.{absPaise % 100:02d}"
    return f"₹{paiseAmount // 100}.{paiseAmount % 100:02d}"


def _renderHeader(invoice: GstrInvoicePayload, merchantLegalName: str, buyerLegalName: str) -> str:
    """Renders invoice top header and legal entity blocks."""
    invNum = html.escape(invoice.invoiceNumber, quote=True)
    invDate = html.escape(invoice.invoiceDate, quote=True)
    mName = html.escape(merchantLegalName, quote=True)
    mGstin = html.escape(invoice.sellerGstin, quote=True)
    mState = html.escape(f"{invoice.merchantStateCode} - {resolveStateName(invoice.merchantStateCode)}", quote=True)
    bName = html.escape(buyerLegalName, quote=True)
    posState = html.escape(f"{invoice.placeOfSupplyStateCode} - {resolveStateName(invoice.placeOfSupplyStateCode)}", quote=True)
    supplyType = "INTRA-STATE (CGST + SGST)" if invoice.isIntraState else "INTER-STATE (IGST)"

    return f"""
    <div class="header-grid">
      <div class="title-area">
        <h1>Tax Invoice</h1>
        <p>Issued under Section 31 of CGST Act, 2017 &amp; Rule 46 of CGST Rules</p>
      </div>
      <div class="meta-badge">
        <div class="invoice-num">Invoice #: {invNum}</div>
        <div>Date: {invDate}</div>
        <div>Supply Classification: <strong>{supplyType}</strong></div>
      </div>
    </div>
    <div class="details-grid">
      <div class="section-box">
        <h3>Seller / Supplier Details</h3>
        <div><strong>Legal Name:</strong> {mName}</div>
        <div><strong>GSTIN:</strong> {mGstin}</div>
        <div><strong>State &amp; Code:</strong> {mState}</div>
      </div>
      <div class="section-box">
        <h3>Recipient / Place of Supply</h3>
        <div><strong>Recipient:</strong> {bName}</div>
        <div><strong>Place of Supply (POS):</strong> {posState}</div>
        <div><strong>Settlement Protocol:</strong> RazorAgent Mesh v2.0</div>
      </div>
    </div>
    """


def _renderLineItemRow(index: int, item: GstrLineItem) -> str:
    """Renders a single table row for an itemized line item."""
    sku = html.escape(item.skuId, quote=True)
    hsn = html.escape(item.hsnCode, quote=True)
    unitPrice = formatPaiseToInr(item.unitPricePaise)
    taxable = formatPaiseToInr(item.taxableAmountPaise)
    cgst = formatPaiseToInr(item.cgstPaise)
    sgst = formatPaiseToInr(item.sgstPaise)
    igst = formatPaiseToInr(item.igstPaise)
    total = formatPaiseToInr(item.totalLinePaise)

    return f"""
      <tr>
        <td>{index}</td>
        <td>{sku}</td>
        <td>{hsn}</td>
        <td>{item.quantity}</td>
        <td>{unitPrice}</td>
        <td>{taxable}</td>
        <td>{item.gstRatePercent}%</td>
        <td>{cgst}</td>
        <td>{sgst}</td>
        <td>{igst}</td>
        <td>{total}</td>
      </tr>
    """


def _renderLineItemsTable(lineItems: list[GstrLineItem], invoice: GstrInvoicePayload) -> str:
    """Renders full itemized tax breakdown table with totals footer."""
    rows = "\n".join(_renderLineItemRow(i + 1, item) for i, item in enumerate(lineItems))
    footer = _renderTableFooter(invoice)

    return f"""
    <table class="data-table">
      <thead>
        <tr>
          <th>#</th>
          <th>SKU Identifier</th>
          <th>HSN</th>
          <th>Qty</th>
          <th>Unit Price</th>
          <th>Taxable Amt</th>
          <th>Rate</th>
          <th>CGST</th>
          <th>SGST</th>
          <th>IGST</th>
          <th>Line Total</th>
        </tr>
      </thead>
      <tbody>
        {rows}
      </tbody>
      {footer}
    </table>
    """


def _renderTableFooter(invoice: GstrInvoicePayload) -> str:
    """Renders table footer row with aggregated taxable and tax sums."""
    totTaxable = formatPaiseToInr(invoice.taxableAmountPaise)
    totCgst = formatPaiseToInr(invoice.totalCgstPaise)
    totSgst = formatPaiseToInr(invoice.totalSgstPaise)
    totIgst = formatPaiseToInr(invoice.totalIgstPaise)
    totLineSum = formatPaiseToInr(invoice.taxableAmountPaise + invoice.totalTaxPaise)

    return f"""
      <tfoot>
        <tr>
          <td colspan="5">Total Taxable &amp; Taxes</td>
          <td>{totTaxable}</td>
          <td>-</td>
          <td>{totCgst}</td>
          <td>{totSgst}</td>
          <td>{totIgst}</td>
          <td>{totLineSum}</td>
        </tr>
      </tfoot>
    """


def _renderSummaryAndTcs(invoice: GstrInvoicePayload) -> str:
    """Renders Section 52 TCS breakdown and invoice financial summary."""
    tcsRateText = "0.5% CGST + 0.5% SGST (100 bps)" if invoice.isIntraState else "1.0% IGST (100 bps)"
    tcsPaiseStr = formatPaiseToInr(invoice.totalTcsPaise)
    taxableStr = formatPaiseToInr(invoice.taxableAmountPaise)
    taxStr = formatPaiseToInr(invoice.totalTaxPaise)
    shipStr = formatPaiseToInr(invoice.shippingPaise)
    discStr = formatPaiseToInr(invoice.discountPaise)
    grandStr = formatPaiseToInr(invoice.grandTotalPaise)

    discRow = (
        f'<div class="summary-row"><span>Promotional Discount:</span><span>-{discStr}</span></div>'
        if invoice.discountPaise > 0
        else ""
    )

    return f"""
    <div class="bottom-grid">
      <div class="tcs-card">
        <h3>Section 52 TCS Withholding Breakdown</h3>
        <p>E-Commerce Operator Tax Collection at Source on Net Taxable Supply:</p>
        <div class="summary-row" style="margin-top: 6px;"><span>Net Taxable Base:</span><span>{taxableStr}</span></div>
        <div class="summary-row"><span>TCS Statutory Rate:</span><span>{tcsRateText}</span></div>
        <div class="summary-row" style="font-weight: 700; color: #1e40af;"><span>Total TCS Withheld:</span><span>{tcsPaiseStr}</span></div>
      </div>
      <div class="summary-card">
        <div class="summary-row"><span>Taxable Subtotal:</span><span>{taxableStr}</span></div>
        <div class="summary-row"><span>Total GST Amount:</span><span>{taxStr}</span></div>
        <div class="summary-row"><span>Shipping &amp; Handling:</span><span>{shipStr}</span></div>
        {discRow}
        <div class="grand-total-row"><span>Grand Total:</span><span>{grandStr}</span></div>
      </div>
    </div>
    """


def _renderAuditVerificationStamp(invoice: GstrInvoicePayload) -> str:
    """Renders 64-character SHA-256 JCS cryptographic stamp."""
    hashVal = html.escape(invoice.cryptographicAuditHash, quote=True)
    dateVal = html.escape(invoice.invoiceDate, quote=True)

    return f"""
    <div class="audit-stamp">
      <h4>&#x2713; Cryptographic Verification &amp; Audit Stamp</h4>
      <div>Canonical JCS SHA-256 Digest (RFC 8785):</div>
      <code class="audit-hash-code">{hashVal}</code>
      <div style="margin-top: 6px;">Digitally signed and verifiable on the RazorAgent Mesh ledger &bull; Certified Timestamp: {dateVal}</div>
    </div>
    """


__all__ = [
    "formatPaiseToInr",
    "renderGstrInvoiceHtml",
]
