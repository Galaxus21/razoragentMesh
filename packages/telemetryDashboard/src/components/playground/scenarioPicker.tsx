"use client";

import React from "react";
import { Play } from "lucide-react";
import { scenarioKindPresentation } from "@/constants/playgroundConstants";
import type { ScenarioSummary } from "@/types/protocolRunTypes";

const scenarioGroupLabel = "Protocol scenarios";

export interface ScenarioPickerProps {
  readonly scenarios: readonly ScenarioSummary[];
  readonly selectedScenarioId: string | null;
  readonly isRunning: boolean;
  readonly onSelect: (scenarioId: string) => void;
  readonly onRun: (scenarioId: string) => void;
}

export function ScenarioPicker({
  scenarios,
  selectedScenarioId,
  isRunning,
  onSelect,
  onRun
}: ScenarioPickerProps): React.JSX.Element {
  return (
    <div
      role="radiogroup"
      aria-label={scenarioGroupLabel}
      className="grid grid-cols-1 gap-3 md:grid-cols-3"
    >
      {scenarios.map((scenario) => {
        const kind = scenarioKindPresentation[scenario.kind];
        const isSelected = scenario.scenarioId === selectedScenarioId;
        return (
          // A selectable card, not a <button>. The Run control inside it is a real button, and
          // a button nested inside a button is invalid HTML: the browser delivered the click to
          // the outer element instead, so pressing Run sometimes only re-selected the card.
          <div
            key={scenario.scenarioId}
            role="radio"
            aria-checked={isSelected}
            tabIndex={0}
            onClick={() => onSelect(scenario.scenarioId)}
            onKeyDown={(event) => {
              if (event.key === "Enter" || event.key === " ") {
                event.preventDefault();
                onSelect(scenario.scenarioId);
              }
            }}
            className={`flex flex-col rounded-xl border p-4 text-left transition-colors cursor-pointer ${
              isSelected
                ? "border-accentPrimary bg-accentSubtle/40"
                : "border-borderSubtle bg-bgSurface hover:bg-bgSurfaceHover"
            }`}
          >
            <div className="flex flex-wrap items-center gap-1.5">
              <span
                className={`rounded-full border px-2 py-0.5 text-[10px] font-semibold ${kind.badgeClass}`}
              >
                {kind.label}
              </span>
              {scenario.invariants.map((invariant) => (
                <span
                  key={invariant}
                  className="rounded-full border border-borderSubtle bg-surfaceContainer px-1.5 py-0.5 text-[10px] font-mono text-textSecondary"
                >
                  {invariant}
                </span>
              ))}
            </div>

            <h3 className="mt-2.5 text-body-md font-semibold text-textPrimary">{scenario.label}</h3>
            <p className="mt-1.5 flex-1 text-body-sm leading-relaxed text-textSecondary">
              {scenario.premise}
            </p>
            <p className="mt-2 text-[11px] leading-relaxed text-textMuted">
              <span className="font-semibold uppercase tracking-wide">Expect: </span>
              {scenario.expectedOutcome}
            </p>

            <button
              type="button"
              disabled={isRunning}
              onClick={(event) => {
                // Selecting the card is the outer handler's job; running it is this button's.
                event.stopPropagation();
                onRun(scenario.scenarioId);
              }}
              className={`mt-3 inline-flex items-center justify-center gap-1.5 rounded-md border px-3 py-1.5 text-label-sm font-semibold transition-colors ${
                isRunning
                  ? "cursor-not-allowed border-borderSubtle bg-surfaceContainer text-textMuted"
                  : "cursor-pointer border-accentPrimary/30 bg-accentPrimary/10 text-accentPrimary hover:bg-accentPrimary/20"
              }`}
            >
              <Play className="h-3.5 w-3.5" />
              {isRunning ? "Running…" : "Run this scenario"}
            </button>
          </div>
        );
      })}
    </div>
  );
}
