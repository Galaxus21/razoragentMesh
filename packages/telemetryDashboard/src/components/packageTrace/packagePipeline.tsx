"use client";

import React from "react";
import { stepStatusPresentation } from "@/constants/playgroundConstants";
import { extractPackageName } from "@/lib/packagePipeline";
import type { ProtocolStepRecord } from "@/types/protocolRunTypes";

const ordinalPadLength = 2;
const ordinalPadCharacter = "0";
const pendingLabel = "PENDING";
const refusalNote =
  "Refusal is the expected result here — the attack was rejected before money moved.";

export interface PackagePipelineProps {
  readonly steps: readonly ProtocolStepRecord[];
  readonly totalSteps: number;
  readonly selectedStepId: string | null;
  readonly onSelectStep: (stepId: string) => void;
}

function formatOrdinal(ordinal: number): string {
  return String(ordinal).padStart(ordinalPadLength, ordinalPadCharacter);
}

function StageCard({
  step,
  isSelected,
  onSelectStep,
}: {
  readonly step: ProtocolStepRecord;
  readonly isSelected: boolean;
  readonly onSelectStep: (stepId: string) => void;
}): React.JSX.Element {
  const presentation = stepStatusPresentation[step.status];
  const isRefused = step.status === "REFUSED";

  return (
    <li className="relative pl-9">
      <span
        className={`absolute left-0 top-3 flex h-6 w-6 items-center justify-center rounded-full border border-borderSubtle bg-bgSurface font-mono text-[10px] ${
          isSelected ? "text-accentPrimary" : "text-textMuted"
        }`}
      >
        {formatOrdinal(step.ordinal)}
      </span>
      <button
        type="button"
        onClick={() => onSelectStep(step.stepId)}
        aria-current={isSelected}
        className={`w-full rounded-lg border border-l-2 bg-bgSurface p-3 text-left transition-colors hover:bg-bgSurfaceHover ${
          presentation.accentBorderClass
        } ${isSelected ? "border-accentPrimary/40" : "border-borderSubtle"}`}
      >
        <div className="flex items-start justify-between gap-2">
          <span className="text-body-md font-semibold text-textPrimary">{step.title}</span>
          <span
            className={`shrink-0 rounded-full border px-2 py-0.5 text-[10px] font-semibold ${presentation.badgeClass}`}
          >
            {presentation.label}
          </span>
        </div>

        <div className="mt-1.5 flex flex-wrap items-center gap-x-2 gap-y-1">
          <span className="rounded border border-borderSubtle px-1.5 py-0.5 text-[10px] uppercase tracking-wide text-textSecondary">
            {step.protocolLayer}
          </span>
          <span className="font-mono text-[11px] text-textMuted">{step.implementedBy}</span>
        </div>

        <p className="mt-1.5 text-body-sm leading-snug text-textSecondary">{step.narrative}</p>

        <div className="mt-1.5 flex items-center justify-between">
          <span className="font-mono text-[11px] text-textMuted">
            {extractPackageName(step.implementedBy)}
          </span>
          <span className="font-mono text-[11px] text-textMuted">{step.durationMs}ms</span>
        </div>

        {isRefused && (
          <p className="mt-2 rounded border border-accentPrimary/30 bg-accentPrimary/5 px-2 py-1.5 text-[11px] leading-snug text-textSecondary">
            {refusalNote}
          </p>
        )}
      </button>
    </li>
  );
}

function PendingCard({ ordinal }: { readonly ordinal: number }): React.JSX.Element {
  return (
    <li className="relative pl-9">
      <span className="absolute left-0 top-3 flex h-6 w-6 items-center justify-center rounded-full border border-borderSubtle bg-bgSurface font-mono text-[10px] text-textMuted">
        {formatOrdinal(ordinal)}
      </span>
      <div className="rounded-lg border border-dashed border-borderSubtle p-3">
        <span className="text-body-sm text-textMuted">{pendingLabel}</span>
      </div>
    </li>
  );
}

// The connector line is drawn behind the ordinal badges rather than between cards, so a run that
// stops early (a refusal ends the run) does not leave a line dangling into empty space.
export function PackagePipeline({
  steps,
  totalSteps,
  selectedStepId,
  onSelectStep,
}: PackagePipelineProps): React.JSX.Element {
  const pendingCount = Math.max(0, totalSteps - steps.length);
  const pendingOrdinals = Array.from(
    { length: pendingCount },
    (_unused, index) => steps.length + index + 1
  );

  return (
    <div className="relative">
      <span
        aria-hidden="true"
        className="absolute bottom-3 left-3 top-3 w-px bg-borderSubtle"
      />
      <ol className="relative space-y-2">
        {steps.map((step) => (
          <StageCard
            key={step.stepId}
            step={step}
            isSelected={step.stepId === selectedStepId}
            onSelectStep={onSelectStep}
          />
        ))}
        {pendingOrdinals.map((ordinal) => (
          <PendingCard key={`pending-${ordinal}`} ordinal={ordinal} />
        ))}
      </ol>
    </div>
  );
}
