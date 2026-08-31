// Shared plumbing for scenario steps: the mutable state a run threads through its steps, and
// the shape every step conforms to. Split out from the step implementations so no single file
// carries both the contract and every use of it.

import type {
  AgentKeyManager,
  CartMandate,
  ExecutionMandate,
  IntentMandate,
  InventoryLockResponse,
  RazorAgentClient,
  SkuQuote,
  SlaVerificationResponse
} from "@razorpay/agent-buyer-sdk";
import { millisPerSecond, type RunParameters } from "./driverConfig";
import type { StepDefinition, StepOutcome } from "./stepRecorder";

export interface RunState {
  quote?: SkuQuote;
  sla?: SlaVerificationResponse;
  lock?: InventoryLockResponse;
  intentMandate?: IntentMandate;
  cartMandate?: CartMandate;
  executionMandate?: ExecutionMandate;
}

export interface RunContext {
  readonly client: RazorAgentClient;
  readonly userSigner: AgentKeyManager;
  readonly merchantSigner: AgentKeyManager;
  readonly parameters: RunParameters;
  readonly state: RunState;
}

export interface ExecutableStep {
  readonly definition: StepDefinition;
  readonly execute: (context: RunContext) => Promise<StepOutcome>;
}

export const layerDiscovery = "Layer 1 - MCP discovery";
export const layerMandates = "Layer 4 - AP2 mandate chain";
export const layerSettlement = "Layer 4 - settlement saga";

export const packageMcpTools = "packages/mcpServer/src/tools/";
export const packageSdkMandates = "packages/buyerSdkTs/src/agentMandateBuilder.ts";
export const packageMandateEngine = "packages/mandateEngine/settlement/";

export const intentValiditySeconds = 86_400;
export const tamperReductionPaise = 100_000;

export function currentUnixSeconds(): number {
  return Math.floor(Date.now() / millisPerSecond);
}

// A step reading state its predecessor should have written means the scenario is mis-ordered.
// Fail loudly rather than silently producing a run with holes in it.
export function requireState<TValue>(value: TValue | undefined, stepName: string): TValue {
  if (value === undefined) {
    throw new Error(`Step '${stepName}' ran before the step that produces its input`);
  }
  return value;
}
