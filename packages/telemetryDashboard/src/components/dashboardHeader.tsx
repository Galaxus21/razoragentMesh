"use client";

import React from "react";
import { Moon, Sun, Trash2 } from "lucide-react";
import {
  connectionStatusLabels,
  streamModePresentation,
} from "@/constants/dashboardConstants";
import type { StreamProvenanceCounts } from "@/lib/streamModeResolver";
import { SseConnectionState, TelemetryStreamMode } from "@/types/telemetryEventTypes";

export interface DashboardHeaderProps {
  readonly connectionState: SseConnectionState;
  readonly streamMode: TelemetryStreamMode;
  readonly provenanceCounts: StreamProvenanceCounts;
  readonly totalEventsCount: number;
  /** The page the reader is on. Supplied by the shell, which knows the route. */
  readonly pageTitle: string;
  readonly pageSection?: string | null;
  readonly onClearEvents: () => void;
  readonly theme?: "light" | "dark";
  readonly onToggleTheme?: () => void;
}

const eventsSuffix = "events";
const clearLabel = "Clear";
const clearTitle = "Clear Event Stream";
const lightModeTitle = "Switch to dark mode";
const darkModeTitle = "Switch to light mode";

// The badge is deliberately terse, so the hover text carries the full claim: what the mode
// means, the transport state underneath it, and the counts the mode was derived from. A reader
// who doubts the label can check the arithmetic.
function buildStreamModeTitle(
  streamMode: TelemetryStreamMode,
  connectionState: SseConnectionState,
  counts: StreamProvenanceCounts,
): string {
  const { description } = streamModePresentation[streamMode];
  const transport = connectionStatusLabels[connectionState];
  const tally =
    `${counts.liveCount} live / ${counts.syntheticCount} fixture / ` +
    `${counts.unknownCount} unstamped`;
  return `${description}\nTransport: ${transport}\nBuffered events: ${tally}`;
}

export function DashboardHeader({
  connectionState,
  streamMode,
  provenanceCounts,
  totalEventsCount,
  pageTitle,
  pageSection = null,
  onClearEvents,
  theme = "dark",
  onToggleTheme,
}: DashboardHeaderProps): React.JSX.Element {
  const streamPresentation = streamModePresentation[streamMode];

  return (
    <header className="flex h-14 shrink-0 items-center justify-between border-b border-borderSubtle bg-bgSurface px-6">
      <div className="flex min-w-0 items-baseline gap-2">
        {pageSection && (
          <>
            <span className="shrink-0 text-sm text-textMuted">{pageSection}</span>
            <span className="shrink-0 text-sm text-textMuted">/</span>
          </>
        )}
        <h1 className="truncate text-sm font-semibold text-textPrimary">{pageTitle}</h1>
      </div>

      <div className="flex items-center gap-2.5">
        <div
          title={buildStreamModeTitle(streamMode, connectionState, provenanceCounts)}
          className={`flex items-center gap-1.5 rounded-md border px-2 py-1 text-[11px] font-medium ${streamPresentation.badgeClass}`}
        >
          <span
            className={`h-1.5 w-1.5 rounded-full ${streamPresentation.dotClass} ${
              streamPresentation.isPulsing ? "animate-pulseFast" : ""
            }`}
          />
          <span>{streamPresentation.label}</span>
        </div>

        <div className="flex items-center gap-1 rounded-md border border-borderSubtle bg-bgBase px-2 py-1 font-mono text-xs text-textSecondary">
          <span className="font-semibold tabular-nums text-textPrimary">{totalEventsCount}</span>
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
            {theme === "dark" ? <Sun className="h-3.5 w-3.5" /> : <Moon className="h-3.5 w-3.5" />}
          </button>
        )}
      </div>
    </header>
  );
}
