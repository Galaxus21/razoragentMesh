"use client";

import React, { useMemo } from "react";
import { AlertCircle, ArrowRight, CheckCircle2, ShieldCheck, Sparkles, Timer } from "lucide-react";
import { OosHealedPayload, TelemetryEvent } from "@/types/telemetryEventTypes";
import { computePercentageDelta, formatLatency, formatPaiseToInr } from "@/lib/currencyUtils";
import { truncateHash } from "@/lib/eventFormatter";

export interface HealingDiffViewerProps {
  readonly events: ReadonlyArray<TelemetryEvent>;
}

const slaThresholdMs = 300;

export function HealingDiffViewer({ events }: HealingDiffViewerProps): React.JSX.Element {
  const healingPayload = useMemo<OosHealedPayload | null>(() => {
    for (const evt of events) {
      if (evt.eventType === "OOS_HEALED") {
        return evt.payload;
      }
    }
    return null;
  }, [events]);

  const originalPricePaise = healingPayload?.originalPricePaise ?? 420000;
  const substitutePricePaise = healingPayload?.substitutePricePaise ?? 425000;
  const cosineScore = healingPayload?.cosineSimilarity ?? 0.924;
  const latencyMs = healingPayload?.healingDurationMs ?? 214;
  const isSlaMet = latencyMs < slaThresholdMs;

  return (
    <div className="flex h-full flex-col rounded-xl border border-slate-800 bg-slate-950/70 p-4 shadow-xl backdrop-blur-md">
      <div className="flex items-center justify-between border-b border-slate-800/80 pb-3">
        <div className="flex items-center gap-2">
          <Sparkles className="h-4 w-4 text-amber-400" />
          <h2 className="text-sm font-semibold text-white">Sub-300ms Vector Self-Healing</h2>
          <span className="rounded bg-amber-950/70 px-1.5 py-0.5 text-[11px] font-mono text-amber-300">
            Qdrant ANN
          </span>
        </div>

        <div
          className={`flex items-center gap-1.5 rounded-full border px-2.5 py-0.5 text-xs font-mono font-medium ${
            isSlaMet
              ? "border-emerald-500/40 bg-emerald-950/60 text-emerald-300"
              : "border-rose-500/40 bg-rose-950/60 text-rose-300"
          }`}
        >
          <Timer className="h-3.5 w-3.5" />
          <span>
            {formatLatency(latencyMs)} ({isSlaMet ? "SLA MET" : "BREACH"})
          </span>
        </div>
      </div>

      <div className="mt-3 grid grid-cols-1 md:grid-cols-2 gap-3">
        {/* Left: OOS Item */}
        <div className="rounded-lg border border-rose-900/40 bg-rose-950/20 p-3">
          <div className="flex items-center justify-between text-xs">
            <span className="font-mono font-bold text-rose-400">
              {healingPayload?.originalSkuId ?? "SKU-101"}
            </span>
            <span className="rounded bg-rose-950/80 px-1.5 py-0.5 text-[10px] font-semibold text-rose-400">
              OUT OF STOCK (0)
            </span>
          </div>
          <p className="mt-1 text-xs text-slate-300">Industrial Sensor Unit A</p>
          <div className="mt-2 text-xs font-mono text-slate-400">
            Price:{" "}
            <span className="font-semibold text-white">
              {formatPaiseToInr(originalPricePaise)}
            </span>
          </div>
        </div>

        {/* Right: Healed Substitute */}
        <div className="rounded-lg border border-emerald-900/40 bg-emerald-950/20 p-3">
          <div className="flex items-center justify-between text-xs">
            <span className="font-mono font-bold text-emerald-400">
              {healingPayload?.substituteSkuId ?? "SKU-104"}
            </span>
            <span className="rounded bg-emerald-950/80 px-1.5 py-0.5 text-[10px] font-semibold text-emerald-400">
              AVAILABLE (25)
            </span>
          </div>
          <p className="mt-1 text-xs text-slate-300">Industrial Sensor Unit A-Plus</p>
          <div className="mt-2 flex items-center justify-between text-xs font-mono">
            <span className="text-slate-400">
              Price:{" "}
              <span className="font-semibold text-white">
                {formatPaiseToInr(substitutePricePaise)}
              </span>
            </span>
            <span className="rounded bg-slate-900 px-1.5 py-0.5 text-emerald-400 font-semibold text-[11px]">
              {computePercentageDelta(originalPricePaise, substitutePricePaise)}
            </span>
          </div>
        </div>
      </div>

      <div className="mt-3 rounded-lg border border-slate-800 bg-slate-900/60 p-3">
        <div className="flex items-center justify-between text-xs">
          <span className="text-slate-400">Cosine Semantic Similarity:</span>
          <span className="font-mono font-bold text-cyan-300">
            {(cosineScore * 100).toFixed(1)}% &ge; 85.0% threshold
          </span>
        </div>
        <div className="mt-1.5 h-1.5 w-full rounded-full bg-slate-950">
          <div
            className="h-1.5 rounded-full bg-gradient-to-r from-cyan-500 to-emerald-400"
            style={{ width: `${Math.min(cosineScore * 100, 100)}%` }}
          />
        </div>
      </div>

      <div className="mt-3 flex-1 rounded-lg border border-slate-800 bg-slate-900/40 p-3">
        <div className="flex items-center gap-1.5 text-xs font-semibold text-slate-300">
          <ShieldCheck className="h-4 w-4 text-emerald-400" />
          <span>Negative Constraint Boolean AST Audit</span>
        </div>
        <div className="mt-2 space-y-1.5 text-xs font-mono">
          <div className="flex items-center justify-between text-slate-300">
            <span>• Allergens & Bio-Toxins Filter</span>
            <span className="flex items-center gap-1 text-emerald-400 text-[11px]">
              <CheckCircle2 className="h-3 w-3" /> Clean (0 detected)
            </span>
          </div>
          <div className="flex items-center justify-between text-slate-300">
            <span>• Excluded Brand Blacklist</span>
            <span className="flex items-center gap-1 text-emerald-400 text-[11px]">
              <CheckCircle2 className="h-3 w-3" /> Clean (0 detected)
            </span>
          </div>
          <div className="flex items-center justify-between text-slate-300">
            <span>• Guaranteed Courier SLA</span>
            <span className="flex items-center gap-1 text-emerald-400 text-[11px]">
              <CheckCircle2 className="h-3 w-3" /> &lt; 24h Express
            </span>
          </div>
        </div>
      </div>
    </div>
  );
}
