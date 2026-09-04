// Shared shapes for a recorded protocol run. Imported by both the server-side driver and the
// client components, so this file must stay free of any Node-only import.

export type ProtocolStepStatus =
  | "PENDING"
  | "RUNNING"
  | "SUCCEEDED"
  | "REFUSED"
  | "FAILED";

// REFUSED means the mesh correctly rejected the step (budget cap, replayed nonce, bad
// signature). It is a passing outcome for an adversarial scenario and must never be
// rendered as a crash -- FAILED is for genuinely unexpected errors.
export interface StepRefusal {
  readonly errorName: string;
  readonly message: string;
  /** The guarantee that caught this, named in words. Never a bare code. */
  readonly invariantViolated?: string;
  readonly statusCode?: number;
}

export interface WireExchange {
  readonly method: string;
  readonly url: string;
  readonly requestHeaders: Readonly<Record<string, string>>;
  readonly requestBody: unknown;
  readonly statusCode: number;
  readonly responseHeaders: Readonly<Record<string, string>>;
  readonly responseBody: unknown;
  readonly durationMs: number;
}

// Everything needed to re-verify a signature in the browser without trusting the server.
export interface CryptoArtifact {
  readonly artifactId: string;
  readonly label: string;
  readonly signerRole: string;
  readonly signerDid: string;
  readonly payload: unknown;
  readonly canonicalJson: string;
  readonly canonicalByteLength: number;
  readonly sha256Digest: string;
  readonly signatureHex: string;
  readonly signatureFieldName: string;
  readonly linkedHashes?: Readonly<Record<string, string>>;
}

export interface SdkCallRecord {
  readonly methodName: string;
  readonly argumentSummary: Readonly<Record<string, unknown>>;
  readonly isPureCrypto: boolean;
}

export interface ProtocolStepRecord {
  readonly stepId: string;
  readonly ordinal: number;
  readonly title: string;
  readonly narrative: string;
  readonly protocolLayer: string;
  readonly implementedBy: string;
  /** What this step guarantees, in words a reader can act on without a legend. */
  readonly invariant?: string;
  readonly sdkCall: SdkCallRecord;
  readonly status: ProtocolStepStatus;
  readonly durationMs: number;
  readonly exchanges: readonly WireExchange[];
  readonly artifacts: readonly CryptoArtifact[];
  readonly refusal?: StepRefusal;
  readonly resultSummary?: Readonly<Record<string, unknown>>;
}

export type ScenarioKind = "HAPPY_PATH" | "ADVERSARIAL";

export interface ScenarioSummary {
  readonly scenarioId: string;
  readonly label: string;
  readonly kind: ScenarioKind;
  readonly premise: string;
  readonly expectedOutcome: string;
  /**
   * The guarantees this scenario exercises, in words.
   *
   * Held as prose rather than as INV-xx codes: the codes were rendered as badges with no
   * legend on the page, and half of them pointed at the wrong invariant in the docs table.
   * A sibling testCaseRefs field carried TC-xx benchmark filenames, which said nothing to
   * anyone who was not editing tests/benchmarkHarness; it is gone.
   */
  readonly invariants: readonly string[];
}

export type RunEventType = "RUN_STARTED" | "STEP_COMPLETED" | "RUN_FINISHED" | "RUN_ERROR";

export interface RunStartedEvent {
  readonly type: "RUN_STARTED";
  readonly runId: string;
  readonly scenario: ScenarioSummary;
  readonly totalSteps: number;
  readonly startedAtMs: number;
}

export interface StepCompletedEvent {
  readonly type: "STEP_COMPLETED";
  readonly runId: string;
  readonly step: ProtocolStepRecord;
}

export interface RunFinishedEvent {
  readonly type: "RUN_FINISHED";
  readonly runId: string;
  readonly outcome: "EXPECTED" | "UNEXPECTED";
  readonly outcomeNarrative: string;
  readonly totalDurationMs: number;
}

export interface RunErrorEvent {
  readonly type: "RUN_ERROR";
  readonly runId: string;
  readonly message: string;
}

export type ProtocolRunEvent =
  | RunStartedEvent
  | StepCompletedEvent
  | RunFinishedEvent
  | RunErrorEvent;
