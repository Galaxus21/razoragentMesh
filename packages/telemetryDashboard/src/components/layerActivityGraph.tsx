"use client";

// The six-layer stack, lit up live while an agent works.
//
// Reading a run as a flat list of tool calls hides the thing the architecture is actually about:
// each call belongs to a layer, and the layers have an order. Drawn as a chain -- L0 through L5,
// each node carrying its own status, its own event count and its own log -- the same stream
// answers "where is the agent right now" at a glance, and an empty node is as informative as a
// busy one. Resilience staying dark means the healer genuinely never fired.
//
// The node statuses decay: a layer reads as working for `layerActiveWindowMs` after its last
// event and then settles to done. That needs a clock the component owns, which is why `nowMs`
// ticks here rather than being derived once per render.

import React, { useEffect, useMemo, useState } from "react";
import { ChevronRight, Circle, Network } from "lucide-react";
import {
  buildLayerActivity,
  type LayerActivity,
  type LayerLogOutcome,
  type LayerStatus
} from "@/lib/layerActivity";
import { panelClass } from "@/constants/playgroundConstants";
import type { TelemetryEvent } from "@/types/telemetryEventTypes";

const tickIntervalMs = 1_000;

interface StatusPresentation {
  readonly label: string;
  readonly dotClass: string;
  readonly nodeClass: string;
  readonly countClass: string;
}

const statusPresentation: Readonly<Record<LayerStatus, StatusPresentation>> = {
  idle: {
    label: "idle",
    dotClass: "text-textMuted",
    nodeClass: "border-borderSubtle bg-bgSurface",
    countClass: "text-textMuted"
  },
  active: {
    label: "working",
    dotClass: "text-accentPrimary animate-pulseFast",
    nodeClass: "border-accentPrimary bg-accentPrimary/10 ring-1 ring-accentPrimary/40",
    countClass: "text-accentPrimary"
  },
  done: {
    label: "done",
    dotClass: "text-statusSuccess",
    nodeClass: "border-statusSuccess/40 bg-statusSuccess/5",
    countClass: "text-statusSuccess"
  },
  refused: {
    label: "refused",
    dotClass: "text-statusError",
    nodeClass: "border-statusError/50 bg-statusError/5",
    countClass: "text-statusError"
  }
};

function formatClock(timestampMs: number): string {
  return new Date(timestampMs).toLocaleTimeString("en-IN", { hour12: false });
}

function LayerNode({
  activity,
  isSelected,
  onSelect
}: {
  readonly activity: LayerActivity;
  readonly isSelected: boolean;
  readonly onSelect: () => void;
}): React.JSX.Element {
  const presentation = statusPresentation[activity.status];
  const newest = activity.log[0];

  return (
    <button
      type="button"
      onClick={onSelect}
      aria-pressed={isSelected}
      className={`w-full rounded-lg border p-3 text-left transition-all ${presentation.nodeClass} ${
        isSelected ? "ring-2 ring-accentPrimary/60" : "hover:border-borderStrong"
      }`}
    >
      <div className="flex items-center justify-between gap-2">
        <span className="rounded bg-surfaceContainer px-1.5 py-0.5 font-mono text-[10px] font-semibold text-textSecondary">
          L{activity.node.ordinal}
        </span>
        <Circle className={`h-2.5 w-2.5 fill-current ${presentation.dotClass}`} />
      </div>

      <div className="mt-1.5 truncate text-label-sm font-semibold text-textPrimary">
        {activity.node.title}
      </div>

      <div className="mt-1 flex items-center justify-between gap-2">
        <span className={`font-mono text-[11px] ${presentation.countClass}`}>
          {presentation.label}
        </span>
        <span className="font-mono text-[11px] text-textMuted">
          {activity.eventCount} {activity.eventCount === 1 ? "event" : "events"}
        </span>
      </div>

      <p className="mt-1 truncate text-[11px] text-textMuted">
        {newest ? newest.title : "no traffic yet"}
      </p>

      <span className="mt-1.5 flex flex-wrap gap-1">
        {activity.refusalCount > 0 && (
          <span className="inline-block rounded-full border border-statusError/40 bg-statusError/10 px-1.5 py-0.5 text-[10px] font-semibold text-statusError">
            {activity.refusalCount} refused
          </span>
        )}
        {/* Kept off the refusal badge on purpose: an agent getting an argument wrong is not the
            mesh turning it down, and colouring the two alike claims a guard fired when none did. */}
        {activity.invalidRequestCount > 0 && (
          <span className="inline-block rounded-full border border-borderSubtle bg-surfaceContainer px-1.5 py-0.5 text-[10px] font-semibold text-textMuted">
            {activity.invalidRequestCount} invalid call
            {activity.invalidRequestCount === 1 ? "" : "s"}
          </span>
        )}
      </span>
    </button>
  );
}

const outcomeLabels: Record<LayerLogOutcome, string> = {
  call: "call",
  ok: "ok",
  invalid: "invalid",
  refused: "refused",
  event: ""
};

const outcomeToneClass: Record<LayerLogOutcome, string> = {
  call: "text-textMuted",
  ok: "text-statusSuccess",
  invalid: "text-statusWarning",
  refused: "text-statusError",
  event: "text-textMuted"
};

export function LayerActivityGraph({
  events
}: {
  readonly events: readonly TelemetryEvent[];
}): React.JSX.Element {
  const [nowMs, setNowMs] = useState<number>(() => Date.now());
  const [pinnedLayerId, setPinnedLayerId] = useState<string | null>(null);

  useEffect(() => {
    const timer = setInterval(() => setNowMs(Date.now()), tickIntervalMs);
    return () => clearInterval(timer);
  }, []);

  const activities = useMemo(() => buildLayerActivity(events, nowMs), [events, nowMs]);

  // Follow the newest working layer until the reader pins one, so the log below tracks the agent
  // without any interaction -- the same follow-then-yield rule the session view uses.
  const busiest = useMemo(() => {
    const withTraffic = activities.filter((activity) => activity.lastEventAtMs !== null);
    if (withTraffic.length === 0) {
      return null;
    }
    return withTraffic.reduce((latest, candidate) =>
      (candidate.lastEventAtMs ?? 0) > (latest.lastEventAtMs ?? 0) ? candidate : latest
    );
  }, [activities]);

  const selectedLayerId = pinnedLayerId ?? busiest?.node.layerId ?? null;
  const selected =
    activities.find((activity) => activity.node.layerId === selectedLayerId) ?? null;

  return (
    <div className={`${panelClass} p-4`}>
      <div className="flex flex-wrap items-center justify-between gap-2 border-b border-borderSubtle pb-3">
        <h3 className="text-label-sm font-semibold text-textPrimary">Protocol stack, live</h3>
        <p className="text-[11px] text-textMuted">
          Each node lights while that stage is handling traffic. Select one to read its log.
        </p>
      </div>

      {/*
        Grid when the nodes have to wrap, a flex row when all six fit. The container SWITCHES
        display rather than keeping a six-column grid, because the arrows are siblings of the
        nodes: as grid items they consume columns, and eleven children in six columns wraps into
        a shape that reads as neither a chain nor a grid.
      */}
      <div className="mt-4 grid grid-cols-2 items-stretch gap-2 sm:grid-cols-3 xl:flex xl:gap-0">
        {activities.map((activity, index) => (
          <React.Fragment key={activity.node.layerId}>
            <div className="min-w-0 xl:flex-1 xl:px-1">
              <LayerNode
                activity={activity}
                isSelected={activity.node.layerId === selectedLayerId}
                onSelect={() =>
                  setPinnedLayerId((current) =>
                    current === activity.node.layerId ? null : activity.node.layerId
                  )
                }
              />
            </div>
            {index < activities.length - 1 && (
              <ChevronRight
                aria-hidden="true"
                className={`hidden h-4 w-4 shrink-0 self-center xl:block ${
                  activity.eventCount > 0 ? "text-accentPrimary" : "text-borderSubtle"
                }`}
              />
            )}
          </React.Fragment>
        ))}
      </div>

      {selected && (
        <div className="mt-4 rounded-lg border border-borderSubtle bg-surfaceContainer/40 p-3">
          <div className="flex flex-wrap items-baseline justify-between gap-2">
            <h4 className="text-label-sm font-semibold text-textPrimary">
              L{selected.node.ordinal} · {selected.node.title}
              {pinnedLayerId && (
                <span className="ml-2 font-normal text-[11px] text-textMuted">
                  pinned — select again to follow the agent
                </span>
              )}
            </h4>
            <span className="font-mono text-[11px] text-textMuted">
              {selected.lastEventAtMs ? `last ${formatClock(selected.lastEventAtMs)}` : "no traffic"}
            </span>
          </div>

          <p className="mt-1 text-[11px] leading-relaxed text-textSecondary">
            {selected.node.tagline}
          </p>

          {selected.log.length === 0 ? (
            <p className="mt-3 text-[11px] text-textMuted">
              Nothing has reached this stage in the current stream. It is not hidden and it is not
              waiting — no event of its kind has arrived.
            </p>
          ) : (
            <ul className="mt-3 max-h-56 space-y-1 overflow-y-auto pr-1">
              {selected.log.map((entry) => (
                <li
                  key={entry.eventId}
                  className={`flex items-baseline gap-2 rounded px-2 py-1 font-mono text-[11px] ${
                    entry.isRefusal
                      ? "bg-statusError/10 text-statusError"
                      : "text-textSecondary"
                  }`}
                >
                  <span className="shrink-0 text-textMuted">{formatClock(entry.timestampMs)}</span>
                  <span className="shrink-0 font-semibold">{entry.detail}</span>
                  <span className="truncate">{entry.title}</span>
                  {/* Every tool invocation publishes a call and a result. Without this tag the two
                      rows are identical and the log reads as if each step happened twice. */}
                  <span
                    className={`ml-auto shrink-0 text-[10px] uppercase ${outcomeToneClass[entry.outcome]}`}
                  >
                    {outcomeLabels[entry.outcome]}
                  </span>
                </li>
              ))}
            </ul>
          )}

          <div className="mt-3 border-t border-borderSubtle pt-2">
            <span className="text-[10px] uppercase tracking-wider text-textMuted">
              Implemented by
            </span>
            <ul className="mt-1 space-y-0.5">
              {selected.node.implementedBy.map((path) => (
                <li key={path} className="break-all font-mono text-[10px] text-textMuted">
                  {path}
                </li>
              ))}
            </ul>
          </div>
        </div>
      )}
    </div>
  );
}
