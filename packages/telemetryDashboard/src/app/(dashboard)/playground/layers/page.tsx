"use client";

import React, { useCallback, useEffect, useMemo, useState } from "react";
import { AlertTriangle, MousePointerClick, Play } from "lucide-react";
import { PackagePipeline } from "@/components/layerExplorer/packagePipeline";
import { PackagesTouchedStrip } from "@/components/layerExplorer/packagesTouchedStrip";
import { RunInputsForm } from "@/components/layerExplorer/runInputsForm";
import { ScenarioSelector } from "@/components/layerExplorer/scenarioSelector";
import { StepDetailPanel } from "@/components/playground/stepDetailPanel";
import { panelClass, runOutcomePresentation } from "@/constants/playgroundConstants";
import { buildDefaultFormValues } from "@/constants/runParameterFields";
import { scenarioSummaries } from "@/constants/scenarioCatalog";
import { useProtocolRun } from "@/hooks/useProtocolRun";
import { hasValidationErrors, validateRunParameters } from "@/lib/runParameterValidation";

const pageTitle = "Layer & Package Explorer";
const pageDescription =
  "Every scenario, every stage, and the package that does the work at each one. Edit the run inputs and press Run: the edited values are sent to the live services, so what you see is what the packages actually did.";
const runLabel = "Run against live mesh";
const runningLabel = "Running…";
const blockedLabel = "Fix the highlighted inputs first";

export default function LayerExplorerPage(): React.JSX.Element {
  const run = useProtocolRun();
  const [selectedScenarioId, setSelectedScenarioId] = useState<string>(
    scenarioSummaries[0]?.scenarioId ?? ""
  );
  const [formValues, setFormValues] = useState<Record<string, string>>(buildDefaultFormValues);
  const [selectedStepId, setSelectedStepId] = useState<string | null>(null);
  const [isFollowingRun, setIsFollowingRun] = useState<boolean>(true);

  const validation = useMemo(() => validateRunParameters(formValues), [formValues]);
  const isBlocked = hasValidationErrors(validation);

  const latestStepId = run.steps[run.steps.length - 1]?.stepId ?? null;
  useEffect(() => {
    if (isFollowingRun && latestStepId) {
      setSelectedStepId(latestStepId);
    }
  }, [isFollowingRun, latestStepId]);

  const selectedStep = useMemo(
    () => run.steps.find((step) => step.stepId === selectedStepId) ?? null,
    [run.steps, selectedStepId]
  );

  const handleFieldChange = useCallback((fieldName: string, value: string) => {
    setFormValues((previous) => ({ ...previous, [fieldName]: value }));
  }, []);

  const handleReset = useCallback(() => {
    setFormValues(buildDefaultFormValues());
  }, []);

  const handleRun = useCallback(() => {
    if (isBlocked) {
      return;
    }
    setSelectedStepId(null);
    setIsFollowingRun(true);
    void run.startRun(selectedScenarioId, validation.overrides);
  }, [isBlocked, run, selectedScenarioId, validation.overrides]);

  const outcome = run.finished ? runOutcomePresentation[run.finished.outcome] : null;

  return (
    <div className="mx-auto max-w-[1600px] space-y-4">
      <header className="flex flex-wrap items-start justify-between gap-3">
        <div>
          <h2 className="text-headline-sm text-textPrimary">{pageTitle}</h2>
          <p className="mt-1 max-w-3xl text-body-sm text-textSecondary">{pageDescription}</p>
        </div>
        <button
          type="button"
          onClick={handleRun}
          disabled={run.isRunning || isBlocked}
          title={isBlocked ? blockedLabel : undefined}
          className="inline-flex items-center gap-1.5 rounded-md bg-accentPrimary px-3 py-1.5 text-label-sm font-semibold text-white transition-opacity hover:opacity-90 disabled:cursor-not-allowed disabled:opacity-40"
        >
          <Play className="h-3.5 w-3.5" />
          {run.isRunning ? runningLabel : runLabel}
        </button>
      </header>

      {run.errorMessage && (
        <div className="flex items-start gap-2 rounded-xl border border-statusError/30 bg-statusError/5 p-4">
          <AlertTriangle className="mt-0.5 h-4 w-4 shrink-0 text-statusError" />
          <div>
            <p className="text-body-md font-semibold text-textPrimary">The run could not start</p>
            <p className="mt-1 text-body-sm text-textSecondary">{run.errorMessage}</p>
            <p className="mt-1.5 text-[11px] text-textMuted">
              The mesh services must be running: <code className="font-mono">docker compose up</code>
            </p>
          </div>
        </div>
      )}

      {run.finished && outcome && (
        <div className={`${panelClass} flex flex-wrap items-center gap-3 p-4`}>
          <span
            className={`rounded-full border px-2.5 py-0.5 text-label-sm font-semibold ${outcome.badgeClass}`}
          >
            {outcome.label}
          </span>
          <p className="min-w-0 flex-1 text-body-sm text-textSecondary">
            {run.finished.outcomeNarrative}
          </p>
          <span className="font-mono text-[11px] text-textMuted">
            {run.finished.totalDurationMs}ms total
          </span>
        </div>
      )}

      <div className="flex flex-col gap-4 xl:flex-row">
        <div className="w-full shrink-0 space-y-4 xl:w-[340px]">
          <ScenarioSelector
            scenarios={scenarioSummaries}
            selectedScenarioId={selectedScenarioId}
            isDisabled={run.isRunning}
            onSelect={setSelectedScenarioId}
          />
          <RunInputsForm
            values={formValues}
            errors={validation.errors}
            changedCount={validation.changedFieldNames.length}
            isDisabled={run.isRunning}
            onChange={handleFieldChange}
            onReset={handleReset}
          />
        </div>

        <section className={`${panelClass} min-w-0 flex-1 p-4`}>
          <PackagesTouchedStrip steps={run.steps} />
          <div className="mt-4">
            {run.totalSteps === 0 && !run.isRunning ? (
              <p className="px-1 py-6 text-body-sm text-textMuted">
                No run yet. Pick a scenario, adjust the inputs if you want, then press Run.
              </p>
            ) : (
              <PackagePipeline
                steps={run.steps}
                totalSteps={run.totalSteps}
                selectedStepId={selectedStepId}
                onSelectStep={(stepId) => {
                  setIsFollowingRun(false);
                  setSelectedStepId(stepId);
                }}
              />
            )}
          </div>
        </section>

        <section className={`${panelClass} w-full shrink-0 p-4 xl:w-[420px]`}>
          {selectedStep ? (
            <StepDetailPanel step={selectedStep} />
          ) : (
            <div className="flex h-full min-h-[240px] flex-col items-center justify-center gap-2 text-center">
              <MousePointerClick className="h-5 w-5 text-textMuted" />
              <p className="text-body-md text-textSecondary">
                {run.isRunning ? "Waiting for the first stage…" : "Nothing to inspect yet"}
              </p>
              <p className="max-w-sm text-body-sm text-textMuted">
                Select any stage to see the SDK call, the wire traffic, and the signatures that
                stage produced.
              </p>
            </div>
          )}
        </section>
      </div>
    </div>
  );
}
