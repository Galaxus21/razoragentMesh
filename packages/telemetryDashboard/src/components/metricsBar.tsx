"use client";

import React, { useMemo } from "react";
import { TelemetryEvent } from "@/types/telemetryEventTypes";
import { formatLatency, formatPaiseToCompactInr } from "@/lib/currencyFormatter";

// Events replayed from the seeder carry this. They are demo data, not measurements.
const syntheticProvenance = "SYNTHETIC";
// An em dash, not a zero: nothing has been measured, which is not the same as measuring nothing.
const unmeasuredValue = "--";

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
    let measuredHealingCount = 0;
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
        // Only measured events contribute to the latency figure. This tile sits next to a
        // "< 300ms SLA" label, so it reads as a measurement of the running system -- and the
        // seeded replay stream (scripts/seedTelemetryStream.py) emits a fixed 214ms. Averaging
        // that in published a constant as a measurement no matter what the code did.
        if (evt.provenance !== syntheticProvenance) {
          measuredHealingCount += 1;
          totalHealingMs += evt.payload.healingDurationMs;
        }
      }
    }

    const avgHealingMs =
      measuredHealingCount > 0 ? totalHealingMs / measuredHealingCount : 0;
    return {
      totalSettledPaise,
      paymentCount,
      negotiationCount,
      convergedCount,
      mandateSignedCount,
      healingCount,
      measuredHealingCount,
      avgHealingMs,
    };
  }, [events]);

  return (
    <dl className="grid grid-cols-2 gap-px overflow-hidden rounded-lg border border-borderSubtle bg-borderSubtle lg:grid-cols-4">
      <MetricTile
        label="Settled volume"
        value={formatPaiseToCompactInr(metrics.totalSettledPaise)}
        context={`${metrics.paymentCount} Razorpay Route settlements`}
      />
      <MetricTile
        label="Negotiations converged"
        value={`${metrics.convergedCount} / ${metrics.negotiationCount}`}
        context="x402-INR, ₹0.50 micro-escrow per turn"
      />
      <MetricTile
        label="Mandates verified"
        value={String(metrics.mandateSignedCount)}
        context="Ed25519 over RFC 8785 canonical JSON"
      />
      <MetricTile
        label="Mean heal time"
        value={metrics.measuredHealingCount > 0 ? formatLatency(metrics.avgHealingMs) : unmeasuredValue}
        // The SLA line only appears beside a real measurement. Printing "0ms, within the 300ms
        // SLA" when nothing has been measured is the same false claim in a cheerier form.
        context={
          metrics.measuredHealingCount > 0
            ? `${metrics.measuredHealingCount} measured, 300ms budget`
            : "no heals measured yet"
        }
      />
    </dl>
  );
}

interface MetricTileProps {
  readonly label: string;
  readonly value: string;
  readonly context: string;
}

// One tile, one number. The previous version hung a coloured lucide glyph in a tinted rounded
// square beside each label -- a dollar sign on a figure printed in rupees, a stack of sheets
// beside "negotiation" -- and painted the qualifier line in that same colour. Four different
// accent hues in one row is decoration competing with the four numbers underneath it, so the
// glyphs and the colour are gone and the reading order is label, figure, what it counts.
function MetricTile({ label, value, context }: MetricTileProps): React.JSX.Element {
  return (
    <div className="bg-bgSurface p-4">
      <dt className="text-[11px] font-medium text-textSecondary">{label}</dt>
      <dd className="mt-1.5 font-mono text-xl font-semibold tabular-nums text-textPrimary">{value}</dd>
      <p className="mt-1 text-[11px] text-textMuted">{context}</p>
    </div>
  );
}
