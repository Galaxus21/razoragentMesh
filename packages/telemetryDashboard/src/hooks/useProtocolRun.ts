"use client";

import { useCallback, useRef } from "react";
import { usePersistentState } from "./usePersistentState";
import { runEndpointPath } from "@/constants/playgroundConstants";
import type { RunParameters } from "@/server/protocolDriver/driverConfig";
import type {
  ProtocolRunEvent,
  ProtocolStepRecord,
  RunFinishedEvent,
  ScenarioSummary
} from "@/types/protocolRunTypes";

// The run endpoint streams SSE over a POST, which EventSource cannot do (it is GET-only), so
// this reads the response body directly. Steps are appended as they arrive rather than after
// the run finishes -- watching the protocol advance is the whole point of the page.

const sseDataPrefix = "data: ";
const sseFrameSeparator = "\n\n";

export interface ProtocolRunState {
  readonly isRunning: boolean;
  readonly scenario: ScenarioSummary | null;
  readonly steps: readonly ProtocolStepRecord[];
  readonly totalSteps: number;
  readonly finished: RunFinishedEvent | null;
  readonly errorMessage: string | null;
}

export interface UseProtocolRunResult extends ProtocolRunState {
  readonly startRun: (scenarioId: string, parameters?: Partial<RunParameters>) => Promise<void>;
  readonly reset: () => void;
}

const idleState: ProtocolRunState = {
  isRunning: false,
  scenario: null,
  steps: [],
  totalSteps: 0,
  finished: null,
  errorMessage: null
};

function applyRunEvent(previous: ProtocolRunState, event: ProtocolRunEvent): ProtocolRunState {
  if (event.type === "RUN_STARTED") {
    return {
      ...previous,
      scenario: event.scenario,
      totalSteps: event.totalSteps,
      steps: [],
      finished: null,
      errorMessage: null
    };
  }
  if (event.type === "STEP_COMPLETED") {
    return { ...previous, steps: [...previous.steps, event.step] };
  }
  if (event.type === "RUN_FINISHED") {
    return { ...previous, finished: event, isRunning: false };
  }
  return { ...previous, errorMessage: event.message, isRunning: false };
}

/**
 * @param persistKey Distinct sessionStorage key per calling page. The Adversarial page and the
 *   Protocol Playground both run through this hook, so a shared key would show one page the
 *   other page's last run.
 */
export function useProtocolRun(persistKey: string): UseProtocolRunResult {
  // isRunning is forced false on restore: the fetch that set it did not survive the navigation,
  // so a restored true would render a spinner that never resolves.
  const [state, setState] = usePersistentState<ProtocolRunState>(persistKey, idleState, (stored) => ({
    ...stored,
    isRunning: false,
  }));
  const abortControllerRef = useRef<AbortController | null>(null);

  const reset = useCallback(() => {
    abortControllerRef.current?.abort();
    abortControllerRef.current = null;
    setState(idleState);
  }, []);

  // `parameters` carries only the fields a visitor actually overrode. Omitting the key entirely
  // when nothing was edited keeps an untouched run byte-for-byte identical to the default run,
  // rather than sending a redundant copy of the defaults back to the driver.
  const startRun = useCallback(
    async (scenarioId: string, parameters?: Partial<RunParameters>) => {
    abortControllerRef.current?.abort();
    const controller = new AbortController();
    abortControllerRef.current = controller;
    setState({ ...idleState, isRunning: true });

    const requestBody =
      parameters && Object.keys(parameters).length > 0
        ? { scenarioId, parameters }
        : { scenarioId };

    try {
      const response = await fetch(runEndpointPath, {
        method: "POST",
        headers: { "Content-Type": "application/json" },
        body: JSON.stringify(requestBody),
        signal: controller.signal
      });

      if (!response.ok || !response.body) {
        const detail = await response.text();
        setState((previous) => ({
          ...previous,
          isRunning: false,
          errorMessage: `Run could not start (HTTP ${response.status}). ${detail}`
        }));
        return;
      }

      const reader = response.body.pipeThrough(new TextDecoderStream()).getReader();
      let buffer = "";

      for (;;) {
        const { done, value } = await reader.read();
        if (done) {
          break;
        }
        buffer += value;

        // Frames can split across chunks, so only consume complete ones and keep the remainder.
        let separatorIndex = buffer.indexOf(sseFrameSeparator);
        while (separatorIndex !== -1) {
          const frame = buffer.slice(0, separatorIndex).trim();
          buffer = buffer.slice(separatorIndex + sseFrameSeparator.length);
          if (frame.startsWith(sseDataPrefix)) {
            try {
              const event = JSON.parse(frame.slice(sseDataPrefix.length)) as ProtocolRunEvent;
              setState((previous) => applyRunEvent(previous, event));
            } catch {
              // A single malformed frame should not abort a run that is otherwise progressing.
            }
          }
          separatorIndex = buffer.indexOf(sseFrameSeparator);
        }
      }

      setState((previous) => (previous.isRunning ? { ...previous, isRunning: false } : previous));
    } catch (error) {
      if (controller.signal.aborted) {
        return;
      }
      const failure = error as Error;
      setState((previous) => ({
        ...previous,
        isRunning: false,
        errorMessage: `Could not reach the run endpoint: ${failure.message}`
      }));
    }
    },
    []
  );

  return { ...state, startRun, reset };
}
