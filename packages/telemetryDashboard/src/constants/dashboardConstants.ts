import {
  MandateKind,
  RouteTransferItem,
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
  CONNECTED: "bg-emerald-500 text-emerald-300 border-emerald-500/30",
  CONNECTING: "bg-amber-500 text-amber-300 border-amber-500/30",
  DISCONNECTED: "bg-slate-600 text-slate-300 border-slate-600/30",
  ERROR: "bg-rose-500 text-rose-300 border-rose-500/30",
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
export const defaultTotalMicroFeesPaise = 150;
export const defaultFallbackBidPaise = 335000;
export const defaultFallbackAskPaise = 335000;
export const maxNegotiationTurns = 5;
export const defaultTurnNumberFallback = 3;
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
export const defaultOriginalPricePaise = 420000;
export const defaultSubstitutePricePaise = 425000;
export const defaultCosineSimilarity = 0.924;
export const defaultHealingDurationMs = 214;
export const defaultOriginalSkuId = "SKU-101";
export const defaultSubstituteSkuId = "SKU-104";
export const healingSimilarityThresholdPercentage = 85.0;

// Razorpay Live Webhook Feed Constants
export const defaultTransfers: ReadonlyArray<RouteTransferItem> = [
  {
    transferId: "trf_merchant_001",
    recipientAccountId: "acc_merchant_nexus_01",
    amountPaise: 380000,
    feePaise: 0,
  },
  {
    transferId: "trf_platform_002",
    recipientAccountId: "acc_razoragent_protocol",
    amountPaise: 2000,
    feePaise: 0,
  },
  {
    transferId: "trf_logistics_003",
    recipientAccountId: "acc_delhivery_direct",
    amountPaise: 38000,
    feePaise: 0,
  },
];
export const defaultPaymentId = "pay_A2A_Live_982341";
export const defaultSettledAmountPaise = 420000;
export const defaultGstrInvoiceHash = "0xfa9812bc67de45fe9812bc67de45fe9812bc67de45fe";

// Event Formatter and Truncation Constants
export const hashTruncatePrefixLength = 8;
export const hashTruncateSuffixLength = 6;
export const defaultUnknownLabel = "UNKNOWN";

export const defaultFallbackEventStyle: EventMetaStyle = {
  label: defaultUnknownLabel,
  badgeBg: "bg-slate-900",
  badgeText: "text-slate-300",
  borderColor: "border-slate-700",
  dotColor: "bg-slate-400",
};

export const defaultEventStyleMap: Record<TelemetryEventType, EventMetaStyle> = {
  MCP_TOOL_CALL: {
    label: "MCP CALL",
    badgeBg: "bg-cyan-950/60",
    badgeText: "text-cyan-400",
    borderColor: "border-cyan-500/30",
    dotColor: "bg-cyan-400",
  },
  MCP_TOOL_RESULT: {
    label: "MCP RESULT",
    badgeBg: "bg-teal-950/60",
    badgeText: "text-teal-300",
    borderColor: "border-teal-500/30",
    dotColor: "bg-teal-400",
  },
  BID_TURN_COMPLETED: {
    label: "BID TURN",
    badgeBg: "bg-violet-950/60",
    badgeText: "text-violet-300",
    borderColor: "border-violet-500/30",
    dotColor: "bg-violet-400",
  },
  NEGOTIATION_CONVERGED: {
    label: "CONVERGED",
    badgeBg: "bg-emerald-950/60",
    badgeText: "text-emerald-300",
    borderColor: "border-emerald-500/40",
    dotColor: "bg-emerald-400",
  },
  MANDATE_SIGNED: {
    label: "AP2 SIGNED",
    badgeBg: "bg-indigo-950/60",
    badgeText: "text-indigo-300",
    borderColor: "border-indigo-500/30",
    dotColor: "bg-indigo-400",
  },
  PAYMENT_CAPTURED: {
    label: "SETTLED",
    badgeBg: "bg-emerald-950/60",
    badgeText: "text-emerald-400",
    borderColor: "border-emerald-500/50",
    dotColor: "bg-emerald-400",
  },
  OOS_HEALED: {
    label: "OOS HEALED",
    badgeBg: "bg-amber-950/60",
    badgeText: "text-amber-300",
    borderColor: "border-amber-500/30",
    dotColor: "bg-amber-400",
  },
  BUDGET_BLOCKED: {
    label: "BUDGET BLOCKED",
    badgeBg: "bg-rose-950/60",
    badgeText: "text-rose-400",
    borderColor: "border-rose-500/40",
    dotColor: "bg-rose-400",
  },
  POW_CHALLENGE_SOLVED: {
    label: "POW VERIFIED",
    badgeBg: "bg-sky-950/60",
    badgeText: "text-sky-300",
    borderColor: "border-sky-500/30",
    dotColor: "bg-sky-400",
  },
  INVENTORY_LOCKED: {
    label: "INV LOCKED",
    badgeBg: "bg-blue-950/60",
    badgeText: "text-blue-300",
    borderColor: "border-blue-500/30",
    dotColor: "bg-blue-400",
  },
  ROUTE_ROLLBACK_TRIGGERED: {
    label: "2PC ROLLBACK",
    badgeBg: "bg-red-950/60",
    badgeText: "text-red-400",
    borderColor: "border-red-500/50",
    dotColor: "bg-red-400",
  },
  HEARTBEAT: {
    label: "HEARTBEAT",
    badgeBg: "bg-slate-900/60",
    badgeText: "text-slate-400",
    borderColor: "border-slate-700/30",
    dotColor: "bg-slate-500",
  },
};

// Mock Scenario Agent Identifiers
export const defaultBuyerAgentDid = "did:agent:procurement-bot-01";
export const defaultUserCfoDid = "did:agent:user-cfo-01";
export const defaultMerchantDid = "did:agent:merchant-nexus-01";
