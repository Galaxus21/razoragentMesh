"use client";

import React from "react";
import { usePersistentState } from "@/hooks/usePersistentState";
import Link from "next/link";
import { ChevronRight, Play, ShieldAlert, ShieldCheck } from "lucide-react";
import { panelClass } from "@/constants/playgroundConstants";
import { scenarioSummaries } from "@/constants/scenarioCatalog";
import { useProtocolRun } from "@/hooks/useProtocolRun";
import type { ProtocolStepRecord } from "@/types/protocolRunTypes";

const pageTitle = "Adversarial Playground";
const pageDescription =
  "Each card below attacks the protocol for real. A refusal is the success condition here — it means the mesh rejected the attack before any money moved.";

function findDecisiveStep(steps: readonly ProtocolStepRecord[]): ProtocolStepRecord | null {
  return (
    steps.find((step) => step.status === "REFUSED") ??
    steps.find((step) => step.status === "FAILED") ??
    null
  );
}

export default function AdversarialPlaygroundPage(): React.JSX.Element {
  const run = useProtocolRun("razoragent.adversarialRun.v1");
  // Persisted alongside the run itself: this is the only thing that says which card the
  // restored result belongs to.
  const [activeScenarioId, setActiveScenarioId] = usePersistentState<string | null>(
    "razoragent.adversarialActiveScenario.v1",
    null
  );

  const adversarialScenarios = scenarioSummaries.filter(
    (scenario) => scenario.kind === "ADVERSARIAL"
  );
  const decisiveStep = findDecisiveStep(run.steps);

  return (
    <div className="mx-auto max-w-7xl space-y-4">
      <nav className="flex items-center gap-1 text-[11px] uppercase tracking-wide text-textMuted">
        <Link href="/visualise/run" className="hover:text-textSecondary transition-colors">
          Protocol Playground
        </Link>
        <ChevronRight className="h-3 w-3" />
        <span className="text-textSecondary">Adversarial</span>
      </nav>

      <header>
        <h2 className="text-headline-sm text-textPrimary">{pageTitle}</h2>
        <p className="mt-1 max-w-3xl text-body-sm text-textSecondary">{pageDescription}</p>
      </header>

      <div className="grid grid-cols-1 gap-3 md:grid-cols-2 xl:grid-cols-3">
        {adversarialScenarios.map((scenario) => {
          const isActive = activeScenarioId === scenario.scenarioId;
          const result = isActive && run.finished ? decisiveStep : null;
          const wasRefused = result?.status === "REFUSED";

          return (
            <article
              key={scenario.scenarioId}
              className={`${panelClass} flex flex-col p-4 ${
                isActive && wasRefused ? "border-accentPrimary/40" : ""
              }`}
            >
              {/* Named guarantees, not codes. These badges used to carry two-part identifiers
                  that required a legend the page never showed -- and pointed at the wrong entry in
                  the docs' invariant table often enough to mislead anyone who chased one down. */}
              <div className="flex flex-wrap items-center gap-1.5">
                {scenario.invariants.map((invariant) => (
                  <span
                    key={invariant}
                    className="rounded-full border border-borderSubtle bg-surfaceContainer px-2 py-0.5 text-[10px] text-textSecondary"
                  >
                    {invariant}
                  </span>
                ))}
              </div>

              <h3 className="mt-2.5 text-body-md font-semibold text-textPrimary">
                {scenario.label}
              </h3>
              <p className="mt-1.5 flex-1 text-body-sm leading-relaxed text-textSecondary">
                {scenario.premise}
              </p>

              <button
                type="button"
                disabled={run.isRunning}
                onClick={() => {
                  setActiveScenarioId(scenario.scenarioId);
                  void run.startRun(scenario.scenarioId);
                }}
                className={`mt-3 inline-flex items-center justify-center gap-1.5 rounded-md border px-3 py-1.5 text-label-sm font-semibold transition-colors ${
                  run.isRunning
                    ? "cursor-not-allowed border-borderSubtle bg-surfaceContainer text-textMuted"
                    : "cursor-pointer border-accentPrimary/30 bg-accentPrimary/10 text-accentPrimary hover:bg-accentPrimary/20"
                }`}
              >
                <Play className="h-3.5 w-3.5" />
                {isActive && run.isRunning ? "Attacking…" : "Run this attack"}
              </button>

              {result && (
                <div
                  className={`mt-3 rounded-lg border p-3 ${
                    wasRefused
                      ? "border-accentPrimary/30 bg-accentPrimary/5"
                      : "border-statusError/30 bg-statusError/5"
                  }`}
                >
                  <div
                    className={`inline-flex items-center gap-1.5 rounded-full border px-2 py-0.5 text-[10px] font-semibold ${
                      wasRefused
                        ? "border-accentPrimary/30 bg-accentPrimary/10 text-accentPrimary"
                        : "border-statusError/30 bg-statusError/10 text-statusError"
                    }`}
                  >
                    {wasRefused ? (
                      <ShieldCheck className="h-3 w-3" />
                    ) : (
                      <ShieldAlert className="h-3 w-3" />
                    )}
                    {wasRefused ? "REFUSED — PROTOCOL WORKED" : "FAILED"}
                  </div>
                  <p className="mt-2 text-[11px] text-textMuted">
                    Stopped at step {result.ordinal}: {result.title}
                  </p>
                  <p className="mt-1 break-words text-body-sm text-textSecondary">
                    {result.refusal?.message}
                  </p>
                  {result.refusal?.invariantViolated && (
                    <p className="mt-1.5 text-[11px] text-textMuted">
                      Caught by{" "}
                      <span className="font-mono font-semibold text-textSecondary">
                        {result.refusal.invariantViolated}
                      </span>
                    </p>
                  )}
                </div>
              )}
            </article>
          );
        })}
      </div>

      <p className="text-[11px] text-textMuted">
        Every attack runs against the live services — the refusal text above is the error the mesh
        actually returned, not a canned message.
      </p>
    </div>
  );
}
