"use client";

import React, { useMemo } from "react";
import { CheckCircle2, ShieldCheck, Sparkles, Timer, XCircle } from "lucide-react";
import {
  defaultHealingSlaThresholdMs,
  healingSimilarityThresholdPercentage,
} from "@/constants/dashboardConstants";
import { computePercentageDelta, formatLatency, formatPaiseToInr } from "@/lib/currencyFormatter";
import { OosHealedPayload, TelemetryEvent } from "@/types/telemetryEventTypes";

export interface HealingDiffViewerProps {
  readonly events: ReadonlyArray<TelemetryEvent>;
}

export function HealingDiffViewer({ events }: HealingDiffViewerProps): React.JSX.Element {
  const healingPayload = useMemo<OosHealedPayload | null>(() => {
    for (const evt of events) {
      if (evt.eventType === "OOS_HEALED") {
        return evt.payload;
      }
    }
    return null;
  }, [events]);

  if (!healingPayload) {
    return (
      <div className="flex h-full flex-col rounded-lg border border-borderSubtle bg-bgSurface p-4">
        <div className="flex items-center justify-between border-b border-borderSubtle pb-3">
          <div className="flex items-center gap-2">
            <Sparkles className="h-4 w-4 text-statusWarning" />
            <h2 className="text-sm font-semibold text-textPrimary">Sub-300ms Vector Self-Healing</h2>
            <span className="rounded bg-statusWarning/10 border border-statusWarning/30 px-1.5 py-0.5 text-xs font-mono text-statusWarning">
              Qdrant ANN
            </span>
          </div>
        </div>
        <div className="flex flex-1 flex-col items-center justify-center text-center p-6 space-y-2">
          <Sparkles className="h-8 w-8 text-textMuted" />
          <span className="text-xs font-semibold text-textPrimary">No Active Vector Self-Healing Events</span>
          <p className="text-xs text-textMuted max-w-xs leading-relaxed">
            Qdrant ANN semantic substitutions and AST constraint audits will display here when inventory locks trigger out-of-stock recovery.
          </p>
        </div>
      </div>
    );
  }

  const originalPricePaise = healingPayload.originalPricePaise;
  const substitutePricePaise = healingPayload.substitutePricePaise;
  const cosineScore = healingPayload.cosineSimilarity;
  const latencyMs = healingPayload.healingDurationMs;
  const isSlaMet = latencyMs < defaultHealingSlaThresholdMs;
  const constraintsPassed = healingPayload.negativeConstraintsPassed;

  return (
    <div className="flex h-full flex-col rounded-lg border border-borderSubtle bg-bgSurface p-4">
      <div className="flex items-center justify-between border-b border-borderSubtle pb-3">
        <div className="flex items-center gap-2">
          <Sparkles className="h-4 w-4 text-statusWarning" />
          <h2 className="text-sm font-semibold text-textPrimary">Sub-300ms Vector Self-Healing</h2>
          <span className="rounded bg-statusWarning/10 border border-statusWarning/30 px-1.5 py-0.5 text-xs font-mono text-statusWarning">
            Qdrant ANN
          </span>
        </div>

        <div
          className={`flex items-center gap-1.5 rounded-full border px-2.5 py-0.5 text-xs font-mono font-medium ${
            isSlaMet
              ? "border-statusSuccess/30 bg-statusSuccess/10 text-statusSuccess"
              : "border-statusError/30 bg-statusError/10 text-statusError"
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
        <div className="rounded-md border border-statusError/30 bg-statusError/5 p-3">
          <div className="flex items-center justify-between text-xs">
            <span className="font-mono font-bold text-statusError">
              {healingPayload.originalSkuId}
            </span>
            <span className="rounded bg-statusError/10 border border-statusError/30 px-1.5 py-0.5 text-[10px] font-semibold text-statusError">
              OUT OF STOCK (0)
            </span>
          </div>
          <p className="mt-1 text-xs text-textSecondary">Primary Requested SKU</p>
          <div className="mt-2 text-xs font-mono text-textMuted">
            Price:{" "}
            <span className="font-semibold text-textPrimary">
              {formatPaiseToInr(originalPricePaise)}
            </span>
          </div>
        </div>

        {/* Right: Healed Substitute */}
        <div className="rounded-md border border-statusSuccess/30 bg-statusSuccess/5 p-3">
          <div className="flex items-center justify-between text-xs">
            <span className="font-mono font-bold text-statusSuccess">
              {healingPayload.substituteSkuId}
            </span>
            <span className="rounded bg-statusSuccess/10 border border-statusSuccess/30 px-1.5 py-0.5 text-[10px] font-semibold text-statusSuccess">
              SUBSTITUTE (LOCKED)
            </span>
          </div>
          <p className="mt-1 text-xs text-textSecondary">Vector Substituted SKU</p>
          <div className="mt-2 flex items-center justify-between text-xs font-mono">
            <span className="text-textMuted">
              Price:{" "}
              <span className="font-semibold text-textPrimary">
                {formatPaiseToInr(substitutePricePaise)}
              </span>
            </span>
            <span className="rounded bg-surfaceContainer border border-borderSubtle px-1.5 py-0.5 text-statusSuccess font-semibold text-xs">
              {computePercentageDelta(originalPricePaise, substitutePricePaise)}
            </span>
          </div>
        </div>
      </div>

      <div className="mt-3 rounded-md border border-borderSubtle bg-surfaceContainer p-3">
        <div className="flex items-center justify-between text-xs">
          <span className="text-textSecondary">Cosine Semantic Similarity:</span>
          <span className="font-mono font-bold text-statusInfo">
            {(cosineScore * 100).toFixed(1)}% &ge; {healingSimilarityThresholdPercentage.toFixed(1)}% threshold
          </span>
        </div>
        <div className="mt-1.5 h-1.5 w-full rounded-full bg-bgBase border border-borderSubtle">
          <div
            className="h-1.5 rounded-full bg-statusSuccess"
            style={{ width: `${Math.min(cosineScore * 100, 100)}%` }}
          />
        </div>
      </div>

      <div className="mt-3 flex-1 rounded-md border border-borderSubtle bg-surfaceContainer p-3">
        <div className="flex items-center gap-1.5 text-xs font-semibold text-textPrimary">
          <ShieldCheck className="h-4 w-4 text-statusSuccess" />
          <span>Negative Constraint Boolean AST Audit</span>
        </div>
        <div className="mt-2 space-y-1.5 text-xs font-mono">
          <div className="flex items-center justify-between text-textSecondary">
            <span>• AST Constraints Audit</span>
            <span className={`flex items-center gap-1 text-xs ${constraintsPassed ? "text-statusSuccess" : "text-statusError"}`}>
              {constraintsPassed ? (
                <>
                  <CheckCircle2 className="h-3 w-3" /> Passed (0 violations)
                </>
              ) : (
                <>
                  <XCircle className="h-3 w-3" /> Failed
                </>
              )}
            </span>
          </div>
        </div>
      </div>
    </div>
  );
}
