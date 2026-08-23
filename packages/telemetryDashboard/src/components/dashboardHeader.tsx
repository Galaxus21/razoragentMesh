"use client";

import React from "react";
import { Activity, Play, RefreshCw, Trash2, Wifi, Zap } from "lucide-react";
import { SseConnectionState } from "@/types/telemetryEventTypes";

export interface DashboardHeaderProps {
  readonly connectionState: SseConnectionState;
  readonly isConnected: boolean;
  readonly isMockActive: boolean;
  readonly totalEventsCount: number;
  readonly onClearEvents: () => void;
  readonly onSimulateFlow: () => void;
}

const connectionStatusLabels: Record<SseConnectionState, string> = {
  CONNECTED: "LIVE MESH SSE",
  CONNECTING: "CONNECTING...",
  DISCONNECTED: "DISCONNECTED",
  ERROR: "FALLBACK / OFFLINE",
};

const connectionStatusColors: Record<SseConnectionState, string> = {
  CONNECTED: "bg-emerald-500 text-emerald-300 border-emerald-500/30",
  CONNECTING: "bg-amber-500 text-amber-300 border-amber-500/30",
  DISCONNECTED: "bg-slate-600 text-slate-300 border-slate-600/30",
  ERROR: "bg-rose-500 text-rose-300 border-rose-500/30",
};

export function DashboardHeader({
  connectionState,
  isConnected,
  isMockActive,
  totalEventsCount,
  onClearEvents,
  onSimulateFlow,
}: DashboardHeaderProps): React.JSX.Element {
  return (
    <header className="flex flex-col md:flex-row md:items-center justify-between gap-4 border-b border-slate-800/80 bg-slate-950/80 px-6 py-4 backdrop-blur-md">
      <div className="flex items-center gap-3">
        <div className="flex h-10 w-10 items-center justify-center rounded-xl bg-gradient-to-br from-cyan-500 to-violet-600 shadow-lg shadow-cyan-500/20">
          <Zap className="h-5 w-5 text-white" />
        </div>
        <div>
          <div className="flex items-center gap-2">
            <h1 className="text-xl font-bold tracking-tight text-white">RazorAgent Mesh</h1>
            <span className="rounded border border-cyan-500/40 bg-cyan-950/60 px-2 py-0.5 text-xs font-semibold text-cyan-300">
              v2.0 AP2
            </span>
          </div>
          <p className="text-xs text-slate-400">
            Autonomous M2M Settlement & Cryptographic Telemetry Enclave
          </p>
        </div>
      </div>

      <div className="flex flex-wrap items-center gap-3">
        <div
          className={`flex items-center gap-2 rounded-full border px-3 py-1 text-xs font-medium ${
            connectionStatusColors[connectionState]
          }`}
        >
          <span
            className={`h-2 w-2 rounded-full ${
              isConnected ? "bg-emerald-400 animate-pulseFast" : "bg-rose-400"
            }`}
          />
          <span>{connectionStatusLabels[connectionState]}</span>
          {isMockActive && <span className="text-[10px] opacity-75">(SIM)</span>}
        </div>

        <div className="flex items-center gap-1.5 rounded-lg border border-slate-800 bg-slate-900/90 px-3 py-1.5 text-xs text-slate-300">
          <Activity className="h-3.5 w-3.5 text-cyan-400" />
          <span className="font-mono text-cyan-300 font-semibold">{totalEventsCount}</span>
          <span className="text-slate-500">events</span>
        </div>

        <button
          type="button"
          onClick={onSimulateFlow}
          className="flex items-center gap-1.5 rounded-lg border border-violet-500/40 bg-violet-950/60 px-3 py-1.5 text-xs font-medium text-violet-200 transition hover:bg-violet-900/60 hover:border-violet-400"
        >
          <Play className="h-3.5 w-3.5 text-violet-400" />
          <span>Simulate Flow</span>
        </button>

        <button
          type="button"
          onClick={onClearEvents}
          title="Clear Event Stream"
          className="flex items-center gap-1.5 rounded-lg border border-slate-800 bg-slate-900 px-3 py-1.5 text-xs text-slate-400 transition hover:bg-slate-800 hover:text-slate-200"
        >
          <Trash2 className="h-3.5 w-3.5" />
          <span>Clear</span>
        </button>
      </div>
    </header>
  );
}
