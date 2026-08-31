// Shapes shared by the SDK console's form, its API route and its result panel. Kept free of
// Node-only imports so the client components can import it directly.

import type { WireExchange } from "./protocolRunTypes";

export type SdkParameterKind = "string" | "number";

export interface SdkParameterField {
  readonly name: string;
  readonly label: string;
  readonly kind: SdkParameterKind;
  readonly isRequired: boolean;
  readonly defaultValue: string;
  readonly helpText: string;
  readonly minimum?: number;
  readonly maximum?: number;
}

// A method the console is willing to invoke. Deliberately limited to the three discovery calls:
// executeSettlement needs a fully signed three-mandate chain, which is not something a visitor
// can type into a form -- that is what the Protocol Playground exists for.
export interface SdkMethodDescriptor {
  readonly methodId: string;
  readonly methodName: string;
  readonly label: string;
  readonly summary: string;
  readonly protocolLayer: string;
  readonly implementedBy: string;
  readonly transport: string;
  // Set when calling the method changes server state, so the UI can say so before the visitor
  // presses Send rather than after.
  readonly sideEffectWarning?: string;
  readonly parameters: readonly SdkParameterField[];
}

export type SdkInvocationStatus = "SUCCEEDED" | "FAILED";

export interface SdkInvocationFailure {
  readonly errorName: string;
  readonly message: string;
  readonly statusCode?: number;
}

export interface SdkInvocationResult {
  readonly methodId: string;
  readonly methodName: string;
  readonly status: SdkInvocationStatus;
  readonly durationMs: number;
  readonly argumentSummary: Readonly<Record<string, unknown>>;
  readonly exchanges: readonly WireExchange[];
  readonly returnValue?: unknown;
  readonly failure?: SdkInvocationFailure;
}

export interface SdkInvocationRequest {
  readonly methodId: string;
  readonly parameters: Readonly<Record<string, string>>;
}
