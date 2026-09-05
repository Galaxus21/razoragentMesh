"use client";

import React from "react";
import { FileText, Clock } from "lucide-react";
import { panelClass } from "@/constants/playgroundConstants";
import type { SettlementInvoice } from "@/types/telemetryEventTypes";
import { formatPaiseToInr } from "./settleConstants";

// The statutory invoice the settlement saga produced, on the screen where a person is asked to
// pay it.
//
// The buyer agent has always been told all of this -- execute_settlement returns the invoice
// number, the HSN line and the audit hash, and agents duly report them back to whoever asked.
// The human being asked to authorise the same charge saw an order id and a rupee figure. This
// closes that gap, and states plainly that nothing has been paid yet: the mesh opened a Razorpay
// order and computed the tax, but amount_paid is still zero until the button below is used.

interface InvoiceCardProps {
  readonly invoice: SettlementInvoice | null;
  readonly razorpayOrderId: string;
}

function TaxRow({
  label,
  valuePaise,
  muted = false,
}: {
  readonly label: string;
  readonly valuePaise: number;
  readonly muted?: boolean;
}): React.JSX.Element {
  return (
    <div className="flex items-baseline justify-between gap-3">
      <dt className={`text-body-sm ${muted ? "text-textMuted" : "text-textSecondary"}`}>{label}</dt>
      <dd className="font-mono text-body-sm tabular-nums text-textPrimary">
        {formatPaiseToInr(valuePaise)}
      </dd>
    </div>
  );
}

export function InvoiceCard({ invoice, razorpayOrderId }: InvoiceCardProps): React.JSX.Element {
  if (!invoice) {
    // A deep link carries only an id and an amount, and clearing the stream drops the event the
    // invoice rode in on. Say which it is rather than rendering an empty invoice shell.
    return (
      <div className={`${panelClass} p-4`}>
        <div className="mb-2 flex items-center gap-2">
          <FileText className="h-4 w-4 text-textMuted" />
          <h3 className="text-label-sm font-semibold text-textPrimary">Tax invoice</h3>
        </div>
        <p className="text-body-sm text-textSecondary">
          Not in this stream. The invoice travels on the settlement event, so it is shown for an
          order opened while this page was watching. Order{" "}
          <span className="font-mono text-textPrimary">{razorpayOrderId}</span> is still payable,
          and its invoice remains recoverable from the run that created it.
        </p>
      </div>
    );
  }

  const isIntraState = invoice.totalIgstPaise === 0;

  return (
    <div className={`${panelClass} p-4`}>
      <div className="mb-3 flex flex-wrap items-center justify-between gap-2">
        <div className="flex items-center gap-2">
          <FileText className="h-4 w-4 text-accentPrimary" />
          <h3 className="text-label-sm font-semibold text-textPrimary">
            Tax invoice {invoice.invoiceNumber}
          </h3>
        </div>
        {/* The honest status. The mesh computed and recorded all of this, but no rail has been
            charged: the Razorpay order sits at amount_paid 0 until a person authorises it. */}
        <span className="inline-flex items-center gap-1.5 rounded-full border border-statusWarning/30 bg-statusWarning/10 px-2.5 py-1 text-label-caps uppercase text-statusWarning">
          <Clock className="h-3 w-3" />
          Payment pending
        </span>
      </div>

      <dl className="mb-3 grid grid-cols-1 gap-x-6 gap-y-2 border-b border-borderSubtle pb-3 sm:grid-cols-2">
        <div className="flex items-baseline justify-between gap-3">
          <dt className="text-body-sm text-textSecondary">Invoice date</dt>
          <dd className="font-mono text-body-sm text-textPrimary">{invoice.invoiceDate}</dd>
        </div>
        <div className="flex items-baseline justify-between gap-3">
          <dt className="text-body-sm text-textSecondary">Seller GSTIN</dt>
          <dd className="font-mono text-body-sm text-textPrimary">{invoice.sellerGstin}</dd>
        </div>
        <div className="flex items-baseline justify-between gap-3">
          <dt className="text-body-sm text-textSecondary">Place of supply</dt>
          <dd className="font-mono text-body-sm text-textPrimary">
            {invoice.placeOfSupplyStateCode}
          </dd>
        </div>
        <div className="flex items-baseline justify-between gap-3">
          <dt className="text-body-sm text-textSecondary">Supply type</dt>
          <dd className="text-body-sm text-textPrimary">
            {isIntraState ? "Intra-state (CGST + SGST)" : "Inter-state (IGST)"}
          </dd>
        </div>
      </dl>

      <div className="mb-3 overflow-x-auto">
        <table className="w-full min-w-[34rem] border-collapse text-left">
          <thead>
            <tr className="text-label-caps uppercase text-textMuted">
              <th className="pb-1.5 pr-3 font-medium">SKU</th>
              <th className="pb-1.5 pr-3 font-medium">HSN</th>
              <th className="pb-1.5 pr-3 text-right font-medium">Qty</th>
              <th className="pb-1.5 pr-3 text-right font-medium">Unit</th>
              <th className="pb-1.5 pr-3 text-right font-medium">GST</th>
              <th className="pb-1.5 text-right font-medium">Line total</th>
            </tr>
          </thead>
          <tbody>
            {invoice.lineItems.map((item) => (
              <tr key={`${item.skuId}-${item.hsnCode}`} className="border-t border-borderSubtle">
                <td className="py-1.5 pr-3 font-mono text-body-sm text-textPrimary">
                  {item.skuId}
                </td>
                <td className="py-1.5 pr-3 font-mono text-body-sm text-textSecondary">
                  {item.hsnCode}
                </td>
                <td className="py-1.5 pr-3 text-right font-mono text-body-sm tabular-nums text-textPrimary">
                  {item.quantity}
                </td>
                <td className="py-1.5 pr-3 text-right font-mono text-body-sm tabular-nums text-textPrimary">
                  {formatPaiseToInr(item.unitPricePaise)}
                </td>
                <td className="py-1.5 pr-3 text-right font-mono text-body-sm tabular-nums text-textSecondary">
                  {item.gstRatePercent}%
                </td>
                <td className="py-1.5 text-right font-mono text-body-sm tabular-nums text-textPrimary">
                  {formatPaiseToInr(item.totalLinePaise)}
                </td>
              </tr>
            ))}
          </tbody>
        </table>
      </div>

      <dl className="grid grid-cols-1 gap-x-6 gap-y-1.5 sm:grid-cols-2">
        <TaxRow label="Taxable value" valuePaise={invoice.taxableAmountPaise} />
        {invoice.discountPaise > 0 && (
          <TaxRow label="Discount" valuePaise={invoice.discountPaise} muted />
        )}
        {isIntraState ? (
          <>
            <TaxRow label="CGST" valuePaise={invoice.totalCgstPaise} />
            <TaxRow label="SGST" valuePaise={invoice.totalSgstPaise} />
          </>
        ) : (
          <TaxRow label="IGST" valuePaise={invoice.totalIgstPaise} />
        )}
        <TaxRow label="Shipping" valuePaise={invoice.shippingPaise} />
        {invoice.totalTcsPaise > 0 && (
          <TaxRow label="TCS withheld (s.52)" valuePaise={invoice.totalTcsPaise} />
        )}
      </dl>

      <div className="mt-3 flex items-baseline justify-between gap-3 border-t border-borderSubtle pt-3">
        <span className="text-label-sm font-semibold text-textPrimary">Invoice total</span>
        <span className="font-mono text-lg font-bold tabular-nums text-textPrimary">
          {formatPaiseToInr(invoice.grandTotalPaise)}
        </span>
      </div>

      <div className="mt-3 border-t border-borderSubtle pt-3">
        <p className="text-label-caps uppercase text-textMuted">Cryptographic audit hash</p>
        <p className="mt-1 break-all font-mono text-body-sm text-textSecondary">
          {invoice.cryptographicAuditHash}
        </p>
      </div>
    </div>
  );
}
