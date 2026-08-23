"use client";

import React, { useMemo } from "react";
import { AlertTriangle, CheckCircle, FileSpreadsheet, Radio, Split, Undo2 } from "lucide-react";
import {
  defaultGstrInvoiceHash,
  defaultPaymentId,
  defaultSettledAmountPaise,
  defaultTransfers,
} from "@/constants/dashboardConstants";
import { formatPaiseToInr } from "@/lib/currencyUtils";
import { truncateHash } from "@/lib/eventFormatter";
import {
  PaymentCapturedPayload,
  RouteRollbackTriggeredPayload,
  TelemetryEvent,
} from "@/types/telemetryEventTypes";

export interface WebhookFeedProps {
  readonly events: ReadonlyArray<TelemetryEvent>;
}

export function WebhookFeed({ events }: WebhookFeedProps): React.JSX.Element {
  const { paymentPayload, rollbackPayload } = useMemo(() => {
    let payment: PaymentCapturedPayload | null = null;
    let rollback: RouteRollbackTriggeredPayload | null = null;

    for (const evt of events) {
      if (evt.eventType === "PAYMENT_CAPTURED") {
        payment = evt.payload;
      } else if (evt.eventType === "ROUTE_ROLLBACK_TRIGGERED") {
        rollback = evt.payload;
      }
    }

    return { paymentPayload: payment, rollbackPayload: rollback };
  }, [events]);

  const transfers = paymentPayload?.transfers ?? defaultTransfers;

  return (
    <div className="flex h-full flex-col rounded-xl border border-slate-800 bg-slate-950/70 p-4 shadow-xl backdrop-blur-md">
      <div className="flex items-center justify-between border-b border-slate-800/80 pb-3">
        <div className="flex items-center gap-2">
          <Radio className="h-4 w-4 text-emerald-400 animate-pulse" />
          <h2 className="text-sm font-semibold text-white">Live Razorpay Webhook & 2PC Split</h2>
          <span className="rounded bg-emerald-950/70 px-1.5 py-0.5 text-[11px] font-mono text-emerald-300">
            Route API
          </span>
        </div>
      </div>

      {rollbackPayload && (
        <div className="mt-3 flex items-center justify-between rounded-lg border border-rose-500/50 bg-rose-950/50 p-2.5">
          <div className="flex items-center gap-2">
            <AlertTriangle className="h-4 w-4 text-rose-400" />
            <div>
              <span className="text-xs font-semibold text-rose-300">2PC Rollback Executed</span>
              <p className="text-[11px] text-slate-300">
                Reason: {rollbackPayload.failureReason}
              </p>
            </div>
          </div>
          <span className="flex items-center gap-1 rounded bg-rose-900/60 px-2 py-0.5 text-[10px] font-mono font-bold text-rose-200">
            <Undo2 className="h-3 w-3" /> REVERSED
          </span>
        </div>
      )}

      <div className="mt-3 rounded-lg border border-slate-800 bg-slate-900/60 p-3">
        <div className="flex items-center justify-between text-xs">
          <span className="font-mono text-slate-400">
            Payment ID:{" "}
            <span className="font-bold text-white">
              {paymentPayload?.paymentId ?? defaultPaymentId}
            </span>
          </span>
          <span className="flex items-center gap-1 rounded bg-emerald-950 px-2 py-0.5 text-[10px] font-bold text-emerald-300">
            <CheckCircle className="h-3 w-3" /> CAPTURED
          </span>
        </div>
        <div className="mt-2 flex items-center justify-between font-mono text-xs">
          <span className="text-slate-400">Settled Amount:</span>
          <span className="text-sm font-bold text-emerald-400">
            {formatPaiseToInr(paymentPayload?.amountPaise ?? defaultSettledAmountPaise)}
          </span>
        </div>
      </div>

      <div className="mt-3 flex-1">
        <div className="flex items-center gap-1.5 text-xs font-semibold text-slate-300 pb-1.5">
          <Split className="h-3.5 w-3.5 text-cyan-400" />
          <span>Multi-Party 2PC Split Transfers</span>
        </div>

        <div className="space-y-1.5 font-mono text-xs">
          {transfers.map((item) => (
            <div
              key={item.transferId}
              className="flex items-center justify-between rounded border border-slate-800/80 bg-slate-900/40 px-2.5 py-1.5"
            >
              <div className="flex flex-col">
                <span className="text-[11px] text-slate-300">{item.recipientAccountId}</span>
                <span className="text-[10px] text-slate-500">{item.transferId}</span>
              </div>
              <span className="font-bold text-white">
                {formatPaiseToInr(item.amountPaise)}
              </span>
            </div>
          ))}
        </div>
      </div>

      <div className="mt-3 rounded-lg border border-slate-800 bg-slate-900/80 p-2.5">
        <div className="flex items-center justify-between text-xs font-mono">
          <div className="flex items-center gap-1.5 text-slate-300">
            <FileSpreadsheet className="h-3.5 w-3.5 text-violet-400" />
            <span>GSTR-1 Invoicing Hash:</span>
          </div>
          <span className="text-cyan-300">
            {truncateHash(paymentPayload?.gstrInvoiceHash ?? defaultGstrInvoiceHash)}
          </span>
        </div>
      </div>
    </div>
  );
}
