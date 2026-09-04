"use client";

import React, { useEffect, useMemo, useState } from "react";
import { AlertTriangle, ListOrdered, MousePointerClick } from "lucide-react";
import { RunStepper } from "@/components/playground/runStepper";
import { ScenarioPicker } from "@/components/playground/scenarioPicker";
import { StepDetailPanel } from "@/components/playground/stepDetailPanel";
import {
  panelClass,
  runOutcomePresentation,
  stepperWidthClass
} from "@/constants/playgroundConstants";
import { findScenarioSummary, scenarioSummaries } from "@/constants/scenarioCatalog";
import { useProtocolRun } from "@/hooks/useProtocolRun";

const pageTitle = "Protocol Playground";
const pageDescription =
  "Press Run and the buyer SDK executes against the live mesh. Every step below shows the request that was actually sent and the cryptography it actually produced.";

export default function PlaygroundPage(): React.JSX.Element {
  const run = useProtocolRun();
  const [selectedScenarioId, setSelectedScenarioId] = useState<string>(
    scenarioSummaries[0]?.scenarioId ?? ""
  );
  const [selectedStepId, setSelectedStepId] = useState<string | null>(null);

  // Preselects the scenario named by ?scenario=..., which is how the Protocol Map's
  // "Exercise this layer" link arrives here. Read from window rather than useSearchParams so
  // this page does not need a Suspense boundary purely to look at one query parameter.
  useEffect(() => {
    const requestedScenarioId = new URLSearchParams(window.location.search).get("scenario");
    if (requestedScenarioId && findScenarioSummary(requestedScenarioId)) {
      setSelectedScenarioId(requestedScenarioId);
    }
  }, []);

  // Follow the run as it advances, but stop hijacking the selection once the reader has
  // clicked a step themselves.
  const [isFollowingRun, setIsFollowingRun] = useState<boolean>(true);
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

  const handleRun = (scenarioId: string) => {
    setSelectedScenarioId(scenarioId);
    setSelectedStepId(null);
    setIsFollowingRun(true);
    void run.startRun(scenarioId);
  };

  const outcome = run.finished ? runOutcomePresentation[run.finished.outcome] : null;

  return (
    <div className="mx-auto max-w-7xl space-y-4">
      <header>
        <h2 className="text-headline-sm text-textPrimary">{pageTitle}</h2>
        <p className="mt-1 max-w-3xl text-body-sm text-textSecondary">{pageDescription}</p>
      </header>

      <ScenarioPicker
        scenarios={scenarioSummaries}
        selectedScenarioId={selectedScenarioId}
        isRunning={run.isRunning}
        onSelect={setSelectedScenarioId}
        onRun={handleRun}
      />

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
          <span className="text-[11px] font-mono text-textMuted">
            {run.finished.totalDurationMs}ms total
          </span>
        </div>
      )}

      <div className="flex flex-col gap-4 lg:flex-row">
        <section className={`${panelClass} ${stepperWidthClass} p-3`}>
          <div className="mb-2 flex items-center justify-between px-1">
            <div className="flex items-center gap-1.5">
              <ListOrdered className="h-3.5 w-3.5 text-accentPrimary" />
              <span className="text-label-caps uppercase text-textMuted">Protocol steps</span>
            </div>
            {run.totalSteps > 0 && (
              <span className="text-[11px] font-mono text-textMuted">
                {run.steps.length}/{run.totalSteps}
              </span>
            )}
          </div>

          {run.totalSteps === 0 && !run.isRunning ? (
            <p className="px-1 py-6 text-body-sm text-textMuted">
              No run yet. Pick a scenario above and press Run.
            </p>
          ) : (
            <RunStepper
              steps={run.steps}
              totalSteps={run.totalSteps}
              isRunning={run.isRunning}
              selectedStepId={selectedStepId}
              onSelectStep={(stepId) => {
                setIsFollowingRun(false);
                setSelectedStepId(stepId);
              }}
            />
          )}
        </section>

        <section className={`${panelClass} min-w-0 flex-1 p-5`}>
          {selectedStep ? (
            <StepDetailPanel step={selectedStep} />
          ) : (
            <div className="flex h-full min-h-[280px] flex-col items-center justify-center gap-2 text-center">
              <MousePointerClick className="h-5 w-5 text-textMuted" />
              <p className="text-body-md text-textSecondary">
                {run.isRunning ? "Waiting for the first step…" : "Nothing to inspect yet"}
              </p>
              <p className="max-w-sm text-body-sm text-textMuted">
                Run a scenario, then select any step to see the SDK call, the wire traffic, and the
                signatures it produced.
              </p>
            </div>
          )}
        </section>
      </div>
    </div>
  );
}
