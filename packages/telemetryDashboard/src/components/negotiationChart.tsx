"use client";

import React, { useMemo } from "react";
import { CheckCircle, Coins, Layers } from "lucide-react";
import { formatPaiseToInr } from "@/lib/currencyFormatter";
import { truncateHash } from "@/lib/eventFormatter";
import {
  BidTurnCompletedPayload,
  NegotiationConvergedPayload,
  TelemetryEvent,
} from "@/types/telemetryEventTypes";
import { ChartTooltip } from "./negotiationChart/chartTooltip";
import { ConcessionTimeline } from "./negotiationChart/concessionTimeline";

export interface NegotiationChartProps {
  readonly events: ReadonlyArray<TelemetryEvent>;
}

interface NegotiationSummary {
  readonly turns: ReadonlyArray<BidTurnCompletedPayload>;
  readonly convergedPayload: NegotiationConvergedPayload | null;
  readonly totalMicroFeesPaise: number;
}

export function NegotiationChart({ events }: NegotiationChartProps): React.JSX.Element {
  const { turns, convergedPayload, totalMicroFeesPaise } = useMemo(() => extractNegotiationData(events), [events]);
  const latestTurn = turns.length > 0 ? turns[turns.length - 1] : null;

  return (
    <div className="flex h-full flex-col rounded-lg border border-borderSubtle bg-bgSurface p-4">
      <div className="flex items-center justify-between border-b border-borderSubtle pb-3">
        <div className="flex items-center gap-2">
          <Layers className="h-4 w-4 text-accentPrimary" />
          <h2 className="text-sm font-semibold text-textPrimary">B2B Dynamic Negotiation</h2>
          <span className="rounded bg-accentSubtle px-1.5 py-0.5 text-xs font-mono text-accentPrimary">x402-INR</span>
        </div>
        <div className="flex items-center gap-1.5 rounded-md border border-accentPrimary/30 bg-accentSubtle px-2 py-0.5 text-xs text-accentPrimary">
          <Coins className="h-3 w-3 text-statusWarning" />
          <span>Micro-Fee: {formatPaiseToInr(totalMicroFeesPaise)}</span>
        </div>
      </div>
      {convergedPayload && (
        <div className="mt-3 flex items-center justify-between rounded-lg border border-statusSuccess/30 bg-statusSuccess/10 p-2.5">
          <div className="flex items-center gap-2">
            <CheckCircle className="h-4 w-4 text-statusSuccess" />
            <div>
              <span className="text-xs font-semibold text-statusSuccess">Agreement Reached</span>
              <p className="font-mono text-xs text-textSecondary">P* = {formatPaiseToInr(convergedPayload.finalAgreedUnitPricePaise)} / unit</p>
            </div>
          </div>
          <div className="text-right">
            <span className="text-xs text-textMuted">AST Contract Hash</span>
            <p className="font-mono text-xs text-statusSuccess">{truncateHash(convergedPayload.contractAstHash)}</p>
          </div>
        </div>
      )}
      <ChartTooltip latestTurn={latestTurn} />
      <ConcessionTimeline turns={turns} latestTurn={latestTurn} />
    </div>
  );
}

function extractNegotiationData(events: ReadonlyArray<TelemetryEvent>): NegotiationSummary {
  const turnList: BidTurnCompletedPayload[] = [];
  let conv: NegotiationConvergedPayload | null = null;
  let microFees = 0;
  for (const evt of events) {
    if (evt.eventType === "BID_TURN_COMPLETED") {
      turnList.push(evt.payload);
      microFees = Math.max(microFees, evt.payload.cumulativeMicroFeesPaise);
    } else if (evt.eventType === "NEGOTIATION_CONVERGED") {
      conv = evt.payload;
    }
  }
  return {
    turns: turnList.sort((a, b) => a.turnNumber - b.turnNumber),
    convergedPayload: conv,
    totalMicroFeesPaise: microFees,
  };
}
