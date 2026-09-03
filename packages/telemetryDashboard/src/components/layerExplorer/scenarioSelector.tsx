"use client";

import React from "react";
import { panelClass, scenarioKindPresentation } from "@/constants/playgroundConstants";
import type { ScenarioSummary } from "@/types/protocolRunTypes";

const cardTitle = "Scenario";

export interface ScenarioSelectorProps {
  readonly scenarios: readonly ScenarioSummary[];
  readonly selectedScenarioId: string;
  readonly isDisabled: boolean;
  readonly onSelect: (scenarioId: string) => void;
}

export function ScenarioSelector({
  scenarios,
  selectedScenarioId,
  isDisabled,
  onSelect,
}: ScenarioSelectorProps): React.JSX.Element {
  return (
    <section className={`${panelClass} p-4`}>
      <h3 className="text-label-caps uppercase text-textMuted">{cardTitle}</h3>
      <div className="mt-3 space-y-1.5" role="radiogroup" aria-label={cardTitle}>
        {scenarios.map((scenario) => {
          const isSelected = scenario.scenarioId === selectedScenarioId;
          const kind = scenarioKindPresentation[scenario.kind];
          return (
            <button
              key={scenario.scenarioId}
              type="button"
              role="radio"
              aria-checked={isSelected}
              disabled={isDisabled}
              onClick={() => onSelect(scenario.scenarioId)}
              className={`flex w-full items-start gap-2 rounded-md border border-l-2 p-2.5 text-left transition-colors hover:bg-bgSurfaceHover disabled:cursor-not-allowed ${
                isSelected
                  ? "border-borderSubtle border-l-accentPrimary bg-accentPrimary/5"
                  : "border-borderSubtle border-l-transparent"
              }`}
            >
              <span
                aria-hidden="true"
                className={`mt-1 h-2.5 w-2.5 shrink-0 rounded-full border ${
                  isSelected ? "border-accentPrimary bg-accentPrimary" : "border-textMuted"
                }`}
              />
              <span className="min-w-0 flex-1 text-body-sm font-medium leading-snug text-textPrimary">
                {scenario.label}
              </span>
              <span
                className={`shrink-0 rounded-full border px-1.5 py-0.5 text-[10px] font-semibold ${kind.badgeClass}`}
              >
                {kind.label}
              </span>
            </button>
          );
        })}
      </div>
    </section>
  );
}
