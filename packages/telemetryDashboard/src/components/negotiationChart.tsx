"use client";

import React, { useMemo } from "react";
import { CheckCircle, Coins, GitCommit, Layers, TrendingDown } from "lucide-react";
import { BidTurnCompletedPayload, NegotiationConvergedPayload, TelemetryEvent } from "@/types/telemetryEventTypes";
import { formatPaiseToInr } from "@/lib/currencyUtils";
import { truncateHash } from "@/lib/eventFormatter";

export interface NegotiationChartProps {
  readonly events: ReadonlyArray<TelemetryEvent>;
}

export function NegotiationChart({ events }: NegotiationChartProps): React.JSX.Element {
  const { turns, convergedPayload, totalMicroFeesPaise } = useMemo(() => {
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

    const sortedTurns = [...turnList].sort((a, b) => a.turnNumber - b.turnNumber);
    return {
      turns: sortedTurns,
      convergedPayload: conv,
      totalMicroFeesPaise: microFees,
    };
  }, [events]);

  const latestTurn = turns.length > 0 ? turns[turns.length - 1] : null;

  return (
    <div className="flex h-full flex-col rounded-xl border border-slate-800 bg-slate-950/70 p-4 shadow-xl backdrop-blur-md">
      <div className="flex items-center justify-between border-b border-slate-800/80 pb-3">
        <div className="flex items-center gap-2">
          <Layers className="h-4 w-4 text-violet-400" />
          <h2 className="text-sm font-semibold text-white">B2B Dynamic Negotiation</h2>
          <span className="rounded bg-violet-950/70 px-1.5 py-0.5 text-[11px] font-mono text-violet-300">
            x402-INR
          </span>
        </div>
        <div className="flex items-center gap-1.5 rounded-md border border-violet-500/30 bg-violet-950/50 px-2 py-0.5 text-xs text-violet-300">
          <Coins className="h-3 w-3 text-amber-400" />
          <span>Micro-Fee: {formatPaiseToInr(totalMicroFeesPaise || 150)}</span>
        </div>
      </div>

      {convergedPayload && (
        <div className="mt-3 flex items-center justify-between rounded-lg border border-emerald-500/40 bg-emerald-950/40 p-2.5">
          <div className="flex items-center gap-2">
            <CheckCircle className="h-4 w-4 text-emerald-400" />
            <div>
              <span className="text-xs font-semibold text-emerald-300">Agreement Reached</span>
              <p className="font-mono text-xs text-slate-300">
                P* = {formatPaiseToInr(convergedPayload.finalAgreedUnitPricePaise)} / unit
              </p>
            </div>
          </div>
          <div className="text-right">
            <span className="text-[10px] text-slate-400">AST Contract Hash</span>
            <p className="font-mono text-xs text-emerald-400">
              {truncateHash(convergedPayload.contractAstHash)}
            </p>
          </div>
        </div>
      )}

      <div className="mt-3 flex items-center justify-around rounded-lg border border-slate-800 bg-slate-900/60 p-2.5 text-xs">
        <div className="text-center">
          <span className="text-[10px] text-cyan-400 font-semibold uppercase">Buyer Bid (Bt)</span>
          <p className="font-mono text-sm font-bold text-white">
            {formatPaiseToInr(latestTurn?.buyerBidPaise ?? 335000)}
          </p>
        </div>
        <div className="flex flex-col items-center">
          <TrendingDown className="h-3.5 w-3.5 text-slate-500" />
          <span className="font-mono text-[11px] text-slate-400">
            Spread: {formatPaiseToInr(latestTurn?.spreadPaise ?? 0)}
          </span>
        </div>
        <div className="text-center">
          <span className="text-[10px] text-violet-400 font-semibold uppercase">Seller Ask (St)</span>
          <p className="font-mono text-sm font-bold text-white">
            {formatPaiseToInr(latestTurn?.sellerAskPaise ?? 335000)}
          </p>
        </div>
      </div>

      <div className="mt-3 flex-1">
        <div className="flex items-center justify-between text-[11px] text-slate-400 pb-1">
          <span>Turn Bargaining Convergence Progression</span>
          <span>Max N=5 Turns</span>
        </div>
        <div className="space-y-1.5 pt-1">
          {[1, 2, 3, 4, 5].map((turnNum) => {
            const turnData = turns.find((t) => t.turnNumber === turnNum);
            const isFinished = !!turnData;
            const isTarget = isFinished || (turnNum <= (latestTurn?.turnNumber ?? 3));

            return (
              <div
                key={turnNum}
                className={`flex items-center justify-between rounded px-2.5 py-1.5 text-xs font-mono transition ${
                  isFinished
                    ? "border border-slate-800 bg-slate-900/80 text-slate-200"
                    : "border border-slate-900/40 bg-slate-950/40 text-slate-600"
                }`}
              >
                <div className="flex items-center gap-2">
                  <GitCommit
                    className={`h-3 w-3 ${
                      isFinished ? "text-violet-400" : "text-slate-700"
                    }`}
                  />
                  <span>Turn #{turnNum}</span>
                </div>
                {turnData ? (
                  <div className="flex items-center gap-3">
                    <span className="text-cyan-400">
                      {formatPaiseToInr(turnData.buyerBidPaise)}
                    </span>
                    <span className="text-slate-500">&harr;</span>
                    <span className="text-violet-400">
                      {formatPaiseToInr(turnData.sellerAskPaise)}
                    </span>
                    <span className="rounded bg-slate-800 px-1 py-0.5 text-[10px] text-emerald-400">
                      {turnData.status}
                    </span>
                  </div>
                ) : (
                  <span className="text-[10px] text-slate-600">Pending</span>
                )}
              </div>
            );
          })}
        </div>
      </div>
    </div>
  );
}
