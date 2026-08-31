// Executes a scenario step by step against the live mesh, yielding one event per completed
// step so the UI can render progress as it happens rather than after the whole run.
//
// A scenario is just an ordered list of ExecutableSteps plus the metadata in
// src/constants/scenarioCatalog.ts. Adversarial scenarios reuse the same steps as the happy
// path -- only the inputs differ -- so the refusal a visitor sees comes from the same code
// that runs the successful case.

import { AgentKeyManager, RazorAgentClient } from "@razorpay/agent-buyer-sdk";
import { scenarioHappyPath, findScenarioSummary } from "@/constants/scenarioCatalog";
import type { ProtocolRunEvent, ProtocolStepRecord } from "@/types/protocolRunTypes";
import {
  defaultRunParameters,
  resolveServiceUrls,
  type RunParameters
} from "./driverConfig";
import { buildScenarioSteps } from "./scenarioSteps";
import { assembleStepRecord, createRecordingFetch } from "./stepRecorder";
import type { ExecutableStep, RunContext } from "./stepContext";
import type { StepDefinition } from "./stepRecorder";

function buildRunContext(parameters: RunParameters): {
  context: RunContext;
  drainExchanges: () => readonly import("@/types/protocolRunTypes").WireExchange[];
} {
  const serviceUrls = resolveServiceUrls();
  const recording = createRecordingFetch();

  // Three distinct keypairs, because the protocol's whole point is that these are three
  // separate parties. Generated per run so nothing is reused between visitors.
  const userSigner = AgentKeyManager.generate();
  const buyerSigner = AgentKeyManager.generate();
  const merchantSigner = AgentKeyManager.generate();

  const client = new RazorAgentClient({
    mcpServerUrl: serviceUrls.mcpServerUrl,
    mandateEngineUrl: serviceUrls.mandateEngineUrl,
    x402GatewayUrl: serviceUrls.x402GatewayUrl,
    buyerKeyManager: buyerSigner,
    customFetch: recording.fetchImpl
  });

  return {
    context: { client, userSigner, merchantSigner, parameters, state: {} },
    drainExchanges: recording.drainExchanges
  };
}

async function executeSingleStep(
  step: ExecutableStep,
  ordinal: number,
  context: RunContext,
  drainExchanges: () => readonly import("@/types/protocolRunTypes").WireExchange[]
): Promise<ProtocolStepRecord> {
  const startedAtMs = performance.now();
  try {
    const outcome = await step.execute(context);
    return assembleStepRecord(
      step.definition,
      ordinal,
      outcome,
      drainExchanges(),
      Math.round(performance.now() - startedAtMs)
    );
  } catch (error) {
    const failure = error as Error & { statusCode?: number };
    return assembleStepRecord(
      step.definition,
      ordinal,
      {
        status: "FAILED",
        refusal: {
          errorName: failure.name,
          message: failure.message,
          ...(failure.statusCode ? { statusCode: failure.statusCode } : {})
        }
      },
      drainExchanges(),
      Math.round(performance.now() - startedAtMs)
    );
  }
}

function summariseOutcome(
  scenarioId: string,
  steps: readonly ProtocolStepRecord[]
): { outcome: "EXPECTED" | "UNEXPECTED"; narrative: string } {
  const failed = steps.find((step) => step.status === "FAILED");
  const refused = steps.find((step) => step.status === "REFUSED");
  const isAdversarial = scenarioId !== scenarioHappyPath;

  if (failed) {
    return {
      outcome: "UNEXPECTED",
      narrative: `'${failed.title}' could not complete: ${failed.refusal?.message ?? "unknown error"}. This is a real failure, not a protocol refusal.`
    };
  }
  if (isAdversarial && refused) {
    return {
      outcome: "EXPECTED",
      narrative: `The mesh refused at '${refused.title}' — ${refused.refusal?.message ?? ""} This is the correct result: the attack was rejected before settlement.`
    };
  }
  if (isAdversarial) {
    return {
      outcome: "UNEXPECTED",
      narrative: "The adversarial run completed without being refused. That is a defect worth investigating."
    };
  }
  if (refused) {
    return {
      outcome: "UNEXPECTED",
      narrative: `The happy path was refused at '${refused.title}', which should not happen with valid mandates.`
    };
  }
  return {
    outcome: "EXPECTED",
    narrative: "Every mandate verified and the settlement saga completed."
  };
}

const runIdPrefix = "run_";
const runIdRandomLength = 12;

function generateRunId(): string {
  const randomBytes = new Uint8Array(runIdRandomLength);
  crypto.getRandomValues(randomBytes);
  const suffix = Array.from(randomBytes, (byte) => byte.toString(16).padStart(2, "0")).join("");
  return `${runIdPrefix}${suffix}`;
}

export interface RunScenarioOptions {
  readonly scenarioId: string;
  readonly parameters?: Partial<RunParameters>;
}

export async function* runScenario(
  options: RunScenarioOptions
): AsyncGenerator<ProtocolRunEvent> {
  const scenario = findScenarioSummary(options.scenarioId);
  const runId = generateRunId();

  if (!scenario) {
    yield { type: "RUN_ERROR", runId, message: `Unknown scenario '${options.scenarioId}'` };
    return;
  }

  const parameters: RunParameters = { ...defaultRunParameters, ...options.parameters };
  const steps = buildScenarioSteps(scenario.scenarioId);
  const { context, drainExchanges } = buildRunContext(parameters);
  const startedAtMs = Date.now();

  yield {
    type: "RUN_STARTED",
    runId,
    scenario,
    totalSteps: steps.length,
    startedAtMs
  };

  const completed: ProtocolStepRecord[] = [];
  for (let index = 0; index < steps.length; index += 1) {
    const step = steps[index];
    if (!step) {
      continue;
    }
    const record = await executeSingleStep(step, index + 1, context, drainExchanges);
    completed.push(record);
    yield { type: "STEP_COMPLETED", runId, step: record };

    // A refusal or a hard failure ends the run: continuing would execute steps whose
    // preconditions the mesh has just rejected.
    if (record.status === "REFUSED" || record.status === "FAILED") {
      break;
    }
  }

  const { outcome, narrative } = summariseOutcome(scenario.scenarioId, completed);
  yield {
    type: "RUN_FINISHED",
    runId,
    outcome,
    outcomeNarrative: narrative,
    totalDurationMs: Date.now() - startedAtMs
  };
}

// The step list a scenario will run, without running it. Documentation prose embeds individual
// steps via <RunStep>, and it must describe the step the driver actually executes -- not a
// hand-copied paragraph that drifts the moment a step is reordered or renamed. This reuses
// buildScenarioSteps rather than restating it, so the two cannot disagree.
export function describeScenarioSteps(scenarioId: string): readonly StepDefinition[] {
  if (!findScenarioSummary(scenarioId)) {
    return [];
  }
  return buildScenarioSteps(scenarioId).map((step) => step.definition);
}
