"use client";

import React from "react";
import { Activity, Moon, Play, Sun, Trash2 } from "lucide-react";
import {
  connectionStatusColors,
  connectionStatusLabels,
} from "@/constants/dashboardConstants";
import { SseConnectionState } from "@/types/telemetryEventTypes";

export interface DashboardHeaderProps {
  readonly connectionState: SseConnectionState;
  readonly isConnected: boolean;
  readonly totalEventsCount: number;
  readonly onClearEvents: () => void;
  readonly theme?: "light" | "dark";
  readonly onToggleTheme?: () => void;
}

const headerTitle = "Autonomous Settlement Enclave";
const headerBadge = "Razorpay Route Rails";
const eventsSuffix = "events";
const clearLabel = "Clear";
const clearTitle = "Clear Event Stream";
const lightModeTitle = "Switch to dark mode";
const darkModeTitle = "Switch to light mode";

export function DashboardHeader({
  connectionState,
  isConnected,
  totalEventsCount,
  onClearEvents,
  theme = "dark",
  onToggleTheme,
}: DashboardHeaderProps): React.JSX.Element {
  return (
    <header className="flex h-14 shrink-0 items-center justify-between border-b border-borderSubtle bg-bgSurface px-6">
      <div className="flex items-center gap-3">
        <h1 className="text-sm font-semibold text-textPrimary">
          {headerTitle}
        </h1>
        <span className="rounded-md border border-accentPrimary/20 bg-accentSubtle px-2 py-0.5 text-[11px] font-mono font-medium text-accentPrimary">
          {headerBadge}
        </span>
      </div>

      <div className="flex items-center gap-2.5">
        <div
          className={`flex items-center gap-1.5 rounded-full border px-2.5 py-0.5 text-[11px] font-medium ${
            connectionStatusColors[connectionState]
          }`}
        >
          <span
            className={`h-1.5 w-1.5 rounded-full ${
              isConnected ? "bg-statusSuccess animate-pulseFast" : "bg-statusError"
            }`}
          />
          <span>{connectionStatusLabels[connectionState]}</span>
        </div>

        <div className="flex items-center gap-1 rounded-md border border-borderSubtle bg-bgBase px-2.5 py-1 text-xs text-textSecondary font-mono">
          <Activity className="h-3.5 w-3.5 text-accentPrimary" />
          <span className="font-semibold text-textPrimary">{totalEventsCount}</span>
          <span className="text-textMuted">{eventsSuffix}</span>
        </div>

        <button
          type="button"
          onClick={onClearEvents}
          title={clearTitle}
          className="flex items-center gap-1 rounded-md border border-borderSubtle bg-bgSurface px-2 py-1 text-xs text-textSecondary transition hover:bg-bgSurfaceHover hover:text-textPrimary"
        >
          <Trash2 className="h-3.5 w-3.5" />
          <span className="sr-only sm:not-sr-only">{clearLabel}</span>
        </button>

        {onToggleTheme && (
          <button
            type="button"
            onClick={onToggleTheme}
            title={theme === "dark" ? darkModeTitle : lightModeTitle}
            className="flex h-7 w-7 items-center justify-center rounded-md border border-borderSubtle bg-bgSurface text-textSecondary transition hover:bg-bgSurfaceHover hover:text-textPrimary"
          >
            {theme === "dark" ? (
              <Sun className="h-3.5 w-3.5 text-statusWarning" />
            ) : (
              <Moon className="h-3.5 w-3.5 text-accentPrimary" />
            )}
          </button>
        )}
      </div>
    </header>
  );
}
