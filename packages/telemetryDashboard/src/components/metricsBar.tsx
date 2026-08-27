"use client";

import React, { useMemo } from "react";
import { CheckCircle2, DollarSign, Layers, ShieldCheck, Zap } from "lucide-react";
import { TelemetryEvent } from "@/types/telemetryEventTypes";
import { formatLatency, formatPaiseToCompactInr } from "@/lib/currencyFormatter";

export interface MetricsBarProps {
  readonly events: ReadonlyArray<TelemetryEvent>;
}

export function MetricsBar({ events }: MetricsBarProps): React.JSX.Element {
  const metrics = useMemo(() => {
    let totalSettledPaise = 0;
    let paymentCount = 0;
    let negotiationCount = 0;
    let convergedCount = 0;
    let mandateSignedCount = 0;
    let healingCount = 0;
    let totalHealingMs = 0;

    for (const evt of events) {
      if (evt.eventType === "PAYMENT_CAPTURED") {
        totalSettledPaise += evt.payload.amountPaise;
        paymentCount += 1;
      } else if (evt.eventType === "BID_TURN_COMPLETED") {
        negotiationCount += 1;
      } else if (evt.eventType === "NEGOTIATION_CONVERGED") {
        convergedCount += 1;
      } else if (evt.eventType === "MANDATE_SIGNED") {
        mandateSignedCount += 1;
      } else if (evt.eventType === "OOS_HEALED") {
        healingCount += 1;
        totalHealingMs += evt.payload.healingDurationMs;
      }
    }

    const avgHealingMs = healingCount > 0 ? totalHealingMs / healingCount : 0;
    return {
      totalSettledPaise,
      paymentCount,
      negotiationCount,
      convergedCount,
      mandateSignedCount,
      healingCount,
      avgHealingMs,
    };
  }, [events]);

  return (
    <div className="grid grid-cols-1 sm:grid-cols-2 lg:grid-cols-4 gap-3 px-6 pt-4">
      <div className="rounded-lg border border-borderSubtle bg-bgSurface p-4">
        <div className="flex items-center justify-between">
          <span className="text-xs font-medium text-textSecondary">Total Settled Volume</span>
          <div className="rounded-md bg-statusSuccess/10 p-1.5 text-statusSuccess">
            <DollarSign className="h-4 w-4" />
          </div>
        </div>
        <div className="mt-2 flex items-baseline gap-2">
          <span className="font-mono text-xl font-bold text-textPrimary">
            {formatPaiseToCompactInr(metrics.totalSettledPaise)}
          </span>
          <span className="text-xs text-statusSuccess font-medium">100% 2PC</span>
        </div>
        <p className="mt-1 text-xs text-textMuted">
          {metrics.paymentCount} Razorpay Route settlements
        </p>
      </div>

      <div className="rounded-lg border border-borderSubtle bg-bgSurface p-4">
        <div className="flex items-center justify-between">
          <span className="text-xs font-medium text-textSecondary">Negotiation Bargaining</span>
          <div className="rounded-md bg-accentSubtle p-1.5 text-accentPrimary">
            <Layers className="h-4 w-4" />
          </div>
        </div>
        <div className="mt-2 flex items-baseline gap-2">
          <span className="font-mono text-xl font-bold text-textPrimary">
            {metrics.convergedCount} / {metrics.negotiationCount}
          </span>
          <span className="text-xs text-accentPrimary font-medium">x402-INR</span>
        </div>
        <p className="mt-1 text-xs text-textMuted">₹0.50 micro-escrow anti-spam</p>
      </div>

      <div className="rounded-lg border border-borderSubtle bg-bgSurface p-4">
        <div className="flex items-center justify-between">
          <span className="text-xs font-medium text-textSecondary">AP2 Mandate Integrity</span>
          <div className="rounded-md bg-statusInfo/10 p-1.5 text-statusInfo">
            <ShieldCheck className="h-4 w-4" />
          </div>
        </div>
        <div className="mt-2 flex items-baseline gap-2">
          <span className="font-mono text-xl font-bold text-textPrimary">
            {metrics.mandateSignedCount} Verified
          </span>
          <span className="text-xs text-statusInfo font-medium">Ed25519</span>
        </div>
        <p className="mt-1 text-xs text-textMuted">Zero floating-point arithmetic</p>
      </div>

      <div className="rounded-lg border border-borderSubtle bg-bgSurface p-4">
        <div className="flex items-center justify-between">
          <span className="text-xs font-medium text-textSecondary">Self-Healing SLA</span>
          <div className="rounded-md bg-statusWarning/10 p-1.5 text-statusWarning">
            <Zap className="h-4 w-4" />
          </div>
        </div>
        <div className="mt-2 flex items-baseline gap-2">
          <span className="font-mono text-xl font-bold text-textPrimary">
            {formatLatency(metrics.avgHealingMs)}
          </span>
          <span className="text-xs text-statusWarning font-medium">&lt; 300ms SLA</span>
        </div>
        <p className="mt-1 text-xs text-textMuted">Cosine sim &ge; 0.85 vector search</p>
      </div>
    </div>
  );
}
