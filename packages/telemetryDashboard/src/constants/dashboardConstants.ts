import {
  MandateKind,
  SseConnectionState,
  TelemetryEventType,
} from "@/types/telemetryEventTypes";

export interface EventMetaStyle {
  readonly label: string;
  readonly badgeBg: string;
  readonly badgeText: string;
  readonly borderColor: string;
  readonly dotColor: string;
}

export interface MandateChainNodeConfig {
  readonly kind: MandateKind;
  readonly title: string;
  readonly signerRole: string;
  readonly description: string;
}

// SSE and Connection Stream Constants
export const maxEventBufferSize = 200;
export const reconnectBaseDelayMs = 1000;
export const reconnectMaxDelayMs = 10000;
export const reconnectBackoffFactor = 1.5;
export const maxReconnectAttempts = 10;
export const defaultSseUrl = "http://localhost:8000/api/v1/telemetry/stream";

// Connection Status Badge Labels and Styles
export const connectionStatusLabels: Record<SseConnectionState, string> = {
  CONNECTED: "LIVE MESH SSE",
  CONNECTING: "CONNECTING...",
  DISCONNECTED: "DISCONNECTED",
  ERROR: "FALLBACK / OFFLINE",
};

export const connectionStatusColors: Record<SseConnectionState, string> = {
  CONNECTED: "bg-statusSuccess/10 text-statusSuccess border-statusSuccess/30",
  CONNECTING: "bg-statusWarning/10 text-statusWarning border-statusWarning/30",
  DISCONNECTED: "bg-bgSurface text-textMuted border-borderSubtle",
  ERROR: "bg-statusError/10 text-statusError border-statusError/30",
};

// Agent Trace Panel Constants
export const traceEventTypes: ReadonlySet<TelemetryEventType> = new Set<TelemetryEventType>([
  "MCP_TOOL_CALL",
  "MCP_TOOL_RESULT",
  "INVENTORY_LOCKED",
  "POW_CHALLENGE_SOLVED",
  "BUDGET_BLOCKED",
]);

// Dynamic B2B Negotiation Constants
export const maxNegotiationTurns = 5;
export const negotiationTurnNumbers: ReadonlyArray<number> = [1, 2, 3, 4, 5];

// AP2 Mandate Chain Constants
export const defaultMandateChainNodes: ReadonlyArray<MandateChainNodeConfig> = [
  {
    kind: "INTENT",
    title: "IntentMandate (MI)",
    signerRole: "User CFO Key (Ed25519)",
    description: "Delegated budget & category authorization envelope",
  },
  {
    kind: "CART",
    title: "CartMandate (MC)",
    signerRole: "Merchant Key (Ed25519)",
    description: "Itemized pricing, HSN tax breakdown & lock token",
  },
  {
    kind: "EXECUTION",
    title: "ExecutionMandate (ME)",
    signerRole: "Buyer Agent Key (Ed25519)",
    description: "Hash-chain binding H(MI) || H(MC) & replay nonce",
  },
  {
    kind: "AMENDMENT",
    title: "AmendmentMandate (MA)",
    signerRole: "Merchant + Agent Re-sign",
    description: "Patched cart substitution with preserved budget cap",
  },
];
export const copyFeedbackTimeoutMs = 2000;

// Self-Healing Diff Viewer Constants
export const defaultHealingSlaThresholdMs = 300;
export const healingSimilarityThresholdPercentage = 85.0;

// Event Formatter and Truncation Constants
export const hashTruncatePrefixLength = 8;
export const hashTruncateSuffixLength = 6;
export const defaultUnknownLabel = "UNKNOWN";

export const defaultFallbackEventStyle: EventMetaStyle = {
  label: defaultUnknownLabel,
  badgeBg: "bg-surfaceContainer",
  badgeText: "text-textSecondary",
  borderColor: "border-borderSubtle",
  dotColor: "bg-textMuted",
};

export const defaultEventStyleMap: Record<TelemetryEventType, EventMetaStyle> = {
  MCP_TOOL_CALL: {
    label: "MCP CALL",
    badgeBg: "bg-statusInfo/10",
    badgeText: "text-statusInfo",
    borderColor: "border-statusInfo/30",
    dotColor: "bg-statusInfo",
  },
  MCP_TOOL_RESULT: {
    label: "MCP RESULT",
    badgeBg: "bg-statusInfo/10",
    badgeText: "text-statusInfo",
    borderColor: "border-statusInfo/30",
    dotColor: "bg-statusInfo",
  },
  BID_TURN_COMPLETED: {
    label: "BID TURN",
    badgeBg: "bg-accentSubtle",
    badgeText: "text-accentPrimary",
    borderColor: "border-accentPrimary/30",
    dotColor: "bg-accentPrimary",
  },
  NEGOTIATION_CONVERGED: {
    label: "CONVERGED",
    badgeBg: "bg-statusSuccess/10",
    badgeText: "text-statusSuccess",
    borderColor: "border-statusSuccess/30",
    dotColor: "bg-statusSuccess",
  },
  MANDATE_SIGNED: {
    label: "AP2 SIGNED",
    badgeBg: "bg-accentSubtle",
    badgeText: "text-accentPrimary",
    borderColor: "border-accentPrimary/30",
    dotColor: "bg-accentPrimary",
  },
  PAYMENT_CAPTURED: {
    label: "SETTLED",
    badgeBg: "bg-statusSuccess/10",
    badgeText: "text-statusSuccess",
    borderColor: "border-statusSuccess/30",
    dotColor: "bg-statusSuccess",
  },
  OOS_HEALED: {
    label: "OOS HEALED",
    badgeBg: "bg-statusWarning/10",
    badgeText: "text-statusWarning",
    borderColor: "border-statusWarning/30",
    dotColor: "bg-statusWarning",
  },
  BUDGET_BLOCKED: {
    label: "BUDGET BLOCKED",
    badgeBg: "bg-statusError/10",
    badgeText: "text-statusError",
    borderColor: "border-statusError/30",
    dotColor: "bg-statusError",
  },
  POW_CHALLENGE_SOLVED: {
    label: "POW VERIFIED",
    badgeBg: "bg-statusInfo/10",
    badgeText: "text-statusInfo",
    borderColor: "border-statusInfo/30",
    dotColor: "bg-statusInfo",
  },
  INVENTORY_LOCKED: {
    label: "INV LOCKED",
    badgeBg: "bg-statusInfo/10",
    badgeText: "text-statusInfo",
    borderColor: "border-statusInfo/30",
    dotColor: "bg-statusInfo",
  },
  ROUTE_ROLLBACK_TRIGGERED: {
    label: "2PC ROLLBACK",
    badgeBg: "bg-statusError/10",
    badgeText: "text-statusError",
    borderColor: "border-statusError/30",
    dotColor: "bg-statusError",
  },
  HEARTBEAT: {
    label: "HEARTBEAT",
    badgeBg: "bg-surfaceContainer",
    badgeText: "text-textMuted",
    borderColor: "border-borderSubtle",
    dotColor: "bg-textMuted",
  },
};
