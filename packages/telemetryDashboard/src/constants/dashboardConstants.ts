import {
  MandateKind,
  SseConnectionState,
  TelemetryEventType,
  TelemetryStreamMode,
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
// NEXT_PUBLIC_ prefix makes Next.js statically inline this at `next build` time --
// it is baked into the client bundle, not read at container runtime. The Dockerfile's
// builder stage must therefore receive it as a build ARG (see packages/telemetryDashboard/
// Dockerfile and the telemetry-dashboard service's `build.args` in docker-compose.yml).
export const defaultSseUrl = process.env.NEXT_PUBLIC_TELEMETRY_SSE_URL || "http://localhost:8000/api/v1/telemetry/stream";

// Transport-level status only: whether the EventSource socket is open. This deliberately no
// longer says "LIVE" -- an open socket proves nothing about whether the events crossing it are
// real. That claim is made by the stream mode below, and only it may say LIVE.
export const connectionStatusLabels: Record<SseConnectionState, string> = {
  CONNECTED: "SSE CONNECTED",
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

// Stream Mode Badge -- what the header is allowed to claim about the events themselves.
export interface StreamModePresentation {
  readonly label: string;
  readonly badgeClass: string;
  readonly dotClass: string;
  readonly isPulsing: boolean;
  readonly description: string;
}

export const streamModePresentation: Record<TelemetryStreamMode, StreamModePresentation> = {
  LIVE: {
    label: "LIVE RUN",
    badgeClass: "bg-statusSuccess/10 text-statusSuccess border-statusSuccess/30",
    dotClass: "bg-statusSuccess",
    isPulsing: true,
    description: "Every event here was produced by a real protocol run against the mesh.",
  },
  REPLAY: {
    label: "REPLAY",
    badgeClass: "bg-statusWarning/10 text-statusWarning border-statusWarning/30",
    dotClass: "bg-statusWarning",
    isPulsing: false,
    description:
      "These events are scripted fixtures, or carry no provenance stamp. Nothing shown came from a verified live run.",
  },
  MIXED: {
    label: "MIXED",
    badgeClass: "bg-statusWarning/10 text-statusWarning border-statusWarning/30",
    dotClass: "bg-statusWarning",
    isPulsing: false,
    description:
      "This buffer holds both real run events and scripted fixtures. Clear the stream to see a run on its own.",
  },
  IDLE: {
    label: "IDLE",
    badgeClass: "bg-bgSurface text-textMuted border-borderSubtle",
    dotClass: "bg-textMuted",
    isPulsing: false,
    description:
      "Connected to the telemetry stream, but no protocol events have arrived. Run a scenario from the Protocol Playground.",
  },
  CONNECTING: {
    label: "CONNECTING...",
    badgeClass: "bg-statusWarning/10 text-statusWarning border-statusWarning/30",
    dotClass: "bg-statusWarning",
    isPulsing: true,
    description: "Opening the telemetry stream.",
  },
  OFFLINE: {
    label: "OFFLINE",
    badgeClass: "bg-statusError/10 text-statusError border-statusError/30",
    dotClass: "bg-statusError",
    isPulsing: false,
    description:
      "Not receiving telemetry. The mesh services may not be running: docker compose up.",
  },
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
