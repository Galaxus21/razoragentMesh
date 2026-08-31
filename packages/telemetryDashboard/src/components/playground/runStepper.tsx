"use client";

import React from "react";
import { stepStatusPresentation } from "@/constants/playgroundConstants";
import type { ProtocolStepRecord, ProtocolStepStatus } from "@/types/protocolRunTypes";

// Fixed-width rail listing every step in the scenario. Steps that have not arrived yet are
// rendered as PENDING placeholders so the reader can see the shape of the whole run from the
// first frame, rather than watching a list grow from nothing.

export interface RunStepperProps {
  readonly steps: readonly ProtocolStepRecord[];
  readonly totalSteps: number;
  readonly isRunning: boolean;
  readonly selectedStepId: string | null;
  readonly onSelectStep: (stepId: string) => void;
}

interface StepperRow {
  readonly key: string;
  readonly ordinal: number;
  readonly title: string;
  readonly status: ProtocolStepStatus;
  readonly durationMs: number | null;
  readonly isSelectable: boolean;
}

function buildRows(
  steps: readonly ProtocolStepRecord[],
  totalSteps: number,
  isRunning: boolean
): readonly StepperRow[] {
  const completedRows: StepperRow[] = steps.map((step) => ({
    key: step.stepId,
    ordinal: step.ordinal,
    title: step.title,
    status: step.status,
    durationMs: step.durationMs,
    isSelectable: true
  }));

  const runHalted = steps.some((step) => step.status === "REFUSED" || step.status === "FAILED");
  if (runHalted) {
    return completedRows;
  }

  const placeholderRows: StepperRow[] = [];
  for (let ordinal = steps.length + 1; ordinal <= totalSteps; ordinal += 1) {
    const isInFlight = isRunning && ordinal === steps.length + 1;
    placeholderRows.push({
      key: `pending-${ordinal}`,
      ordinal,
      title: isInFlight ? "Running…" : "Waiting",
      status: isInFlight ? "RUNNING" : "PENDING",
      durationMs: null,
      isSelectable: false
    });
  }
  return [...completedRows, ...placeholderRows];
}

export function RunStepper({
  steps,
  totalSteps,
  isRunning,
  selectedStepId,
  onSelectStep
}: RunStepperProps): React.JSX.Element {
  const rows = buildRows(steps, totalSteps, isRunning);

  return (
    <ol className="space-y-1">
      {rows.map((row) => {
        const presentation = stepStatusPresentation[row.status];
        const isSelected = row.key === selectedStepId;
        return (
          <li key={row.key}>
            <button
              type="button"
              disabled={!row.isSelectable}
              onClick={() => row.isSelectable && onSelectStep(row.key)}
              className={`flex w-full items-start gap-2.5 rounded-md border-l-2 px-2.5 py-2 text-left transition-colors ${presentation.accentBorderClass} ${
                isSelected ? "bg-bgSurfaceHover" : "bg-transparent"
              } ${row.isSelectable ? "hover:bg-bgSurfaceHover cursor-pointer" : "cursor-default opacity-60"}`}
            >
              <span
                className={`mt-1.5 h-1.5 w-1.5 shrink-0 rounded-full ${presentation.dotClass}`}
                aria-hidden="true"
              />
              <span className="min-w-0 flex-1">
                <span className="block text-body-sm text-textPrimary leading-snug">
                  <span className="text-textMuted tabular-nums">{row.ordinal}. </span>
                  {row.title}
                </span>
                {row.durationMs !== null && (
                  <span className="mt-0.5 block text-[11px] font-mono text-textMuted">
                    {presentation.label} · {row.durationMs}ms
                  </span>
                )}
              </span>
            </button>
          </li>
        );
      })}
    </ol>
  );
}
