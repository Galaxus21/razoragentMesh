// <RunStep scenario=".." step=".." /> -- the description of one step the protocol driver will
// actually execute, pulled from the driver itself.
//
// describeScenarioSteps returns the same StepDefinition list runScenario runs, in the same
// order, so a step that is renamed, reordered or removed changes this block too. Naming a step
// that the scenario does not contain throws, which fails the static build rather than
// rendering a paragraph about a step that no longer exists.

import React from "react";
import Link from "next/link";
import { PlayCircle } from "lucide-react";
import { describeScenarioSteps } from "@/server/protocolDriver/runScenario";

const playgroundRoute = "/visualise/run";

export interface RunStepProps {
  readonly scenario: string;
  readonly step: string;
}

export function RunStep({ scenario, step }: RunStepProps): React.JSX.Element {
  const definitions = describeScenarioSteps(scenario);
  if (definitions.length === 0) {
    throw new Error(`<RunStep scenario="${scenario}"> names no scenario in the driver catalog.`);
  }

  const index = definitions.findIndex((candidate) => candidate.stepId === step);
  if (index < 0) {
    throw new Error(
      `<RunStep step="${step}"> is not a step of '${scenario}'. ` +
        `Its steps are: ${definitions.map((candidate) => candidate.stepId).join(", ")}`
    );
  }

  const definition = definitions[index];

  return (
    <div className="doc-widget my-4 rounded-lg border border-borderSubtle bg-bgSurface p-3">
      <div className="flex flex-wrap items-baseline gap-2">
        <span className="text-label-caps uppercase text-textMuted">
          Step {index + 1} of {definitions.length}
        </span>
        <span className="text-body-sm font-semibold text-textPrimary">{definition.title}</span>
      </div>

      <p className="mt-1.5 text-body-sm leading-relaxed text-textSecondary">
        {definition.narrative}
      </p>

      <dl className="mt-2.5 grid grid-cols-1 gap-x-6 gap-y-1 text-[11px] sm:grid-cols-2">
        <div>
          <dt className="text-textMuted">SDK call</dt>
          <dd className="font-mono text-textSecondary">{definition.sdkCall.methodName}</dd>
        </div>
        <div>
          <dt className="text-textMuted">Protocol layer</dt>
          <dd className="text-textSecondary">{definition.protocolLayer}</dd>
        </div>
        <div>
          <dt className="text-textMuted">Implemented in</dt>
          <dd className="font-mono text-textSecondary">{definition.implementedBy}</dd>
        </div>
        {definition.invariant ? (
          <div>
            <dt className="text-textMuted">Invariant</dt>
            <dd className="text-textSecondary">{definition.invariant}</dd>
          </div>
        ) : null}
      </dl>

      <Link
        href={`${playgroundRoute}?scenario=${scenario}`}
        className="mt-3 inline-flex items-center gap-1.5 text-[11px] font-medium text-accentPrimary"
      >
        <PlayCircle className="h-3.5 w-3.5" />
        Run this scenario in the Playground
      </Link>
    </div>
  );
}
