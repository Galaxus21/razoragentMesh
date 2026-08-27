"use client";

import React, { useMemo } from "react";
import { AlertTriangle, CheckCircle, FileSpreadsheet, Radio, Split, Undo2 } from "lucide-react";
import { formatPaiseToInr } from "@/lib/currencyFormatter";
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

  if (!paymentPayload && !rollbackPayload) {
    return (
      <div className="flex h-full flex-col rounded-lg border border-borderSubtle bg-bgSurface p-4">
        <div className="flex items-center justify-between border-b border-borderSubtle pb-3">
          <div className="flex items-center gap-2">
            <Radio className="h-4 w-4 text-statusSuccess animate-pulse" />
            <h2 className="text-sm font-semibold text-textPrimary">Live Razorpay Webhook & 2PC Split</h2>
            <span className="rounded bg-statusSuccess/10 border border-statusSuccess/30 px-1.5 py-0.5 text-xs font-mono text-statusSuccess">
              Route API
            </span>
          </div>
        </div>
        <div className="flex flex-1 flex-col items-center justify-center text-center p-6 space-y-2">
          <Radio className="h-8 w-8 text-textMuted" />
          <span className="text-xs font-semibold text-textPrimary">Awaiting 2PC Settlement Webhooks</span>
          <p className="text-xs text-textMuted max-w-xs leading-relaxed">
            Razorpay Route multi-party transfer splits and GSTR-1 tax hashes will stream here upon payment capture.
          </p>
        </div>
      </div>
    );
  }

  const transfers = paymentPayload?.transfers ?? [];

  return (
    <div className="flex h-full flex-col rounded-lg border border-borderSubtle bg-bgSurface p-4">
      <div className="flex items-center justify-between border-b border-borderSubtle pb-3">
        <div className="flex items-center gap-2">
          <Radio className="h-4 w-4 text-statusSuccess animate-pulse" />
          <h2 className="text-sm font-semibold text-textPrimary">Live Razorpay Webhook & 2PC Split</h2>
          <span className="rounded bg-statusSuccess/10 border border-statusSuccess/30 px-1.5 py-0.5 text-xs font-mono text-statusSuccess">
            Route API
          </span>
        </div>
      </div>

      {rollbackPayload && (
        <div className="mt-3 flex items-center justify-between rounded-lg border border-statusError/30 bg-statusError/10 p-2.5">
          <div className="flex items-center gap-2">
            <AlertTriangle className="h-4 w-4 text-statusError" />
            <div>
              <span className="text-xs font-semibold text-statusError">2PC Rollback Executed</span>
              <p className="text-xs text-textSecondary">
                Reason: {rollbackPayload.failureReason}
              </p>
            </div>
          </div>
          <span className="flex items-center gap-1 rounded bg-statusError/20 px-2 py-0.5 text-[10px] font-mono font-bold text-statusError">
            <Undo2 className="h-3 w-3" /> REVERSED
          </span>
        </div>
      )}

      {paymentPayload && (
        <>
          <div className="mt-3 rounded-md border border-borderSubtle bg-surfaceContainer p-3">
            <div className="flex items-center justify-between text-xs">
              <span className="font-mono text-textSecondary">
                Payment ID:{" "}
                <span className="font-bold text-textPrimary">
                  {paymentPayload.paymentId}
                </span>
              </span>
              <span className="flex items-center gap-1 rounded bg-statusSuccess/10 border border-statusSuccess/30 px-2 py-0.5 text-[10px] font-bold text-statusSuccess">
                <CheckCircle className="h-3 w-3" /> CAPTURED
              </span>
            </div>
            <div className="mt-2 flex items-center justify-between font-mono text-xs">
              <span className="text-textSecondary">Settled Amount:</span>
              <span className="text-sm font-bold text-statusSuccess">
                {formatPaiseToInr(paymentPayload.amountPaise)}
              </span>
            </div>
          </div>

          <div className="mt-3 flex-1">
            <div className="flex items-center gap-1.5 text-xs font-semibold text-textPrimary pb-1.5">
              <Split className="h-3.5 w-3.5 text-accentPrimary" />
              <span>Multi-Party 2PC Split Transfers</span>
            </div>

            <div className="space-y-1.5 font-mono text-xs">
              {transfers.map((item) => (
                <div
                  key={item.transferId}
                  className="flex items-center justify-between rounded border border-borderSubtle bg-bgSurface px-2.5 py-1.5"
                >
                  <div className="flex flex-col">
                    <span className="text-xs text-textPrimary">{item.recipientAccountId}</span>
                    <span className="text-[10px] text-textMuted">{item.transferId}</span>
                  </div>
                  <span className="font-bold text-textPrimary">
                    {formatPaiseToInr(item.amountPaise)}
                  </span>
                </div>
              ))}
            </div>
          </div>

          {paymentPayload.gstrInvoiceHash && (
            <div className="mt-3 rounded-md border border-borderSubtle bg-surfaceContainer p-2.5">
              <div className="flex items-center justify-between text-xs font-mono">
                <div className="flex items-center gap-1.5 text-textSecondary">
                  <FileSpreadsheet className="h-3.5 w-3.5 text-statusInfo" />
                  <span>GSTR-1 Invoicing Hash:</span>
                </div>
                <span className="text-statusInfo">
                  {truncateHash(paymentPayload.gstrInvoiceHash)}
                </span>
              </div>
            </div>
          )}
        </>
      )}
    </div>
  );
}
