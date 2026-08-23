import { TelemetryEventType } from "@/types/telemetryEventTypes";

const hashTruncatePrefixLength = 8;
const hashTruncateSuffixLength = 6;
const defaultUnknownLabel = "UNKNOWN";

export interface EventMetaStyle {
  readonly label: string;
  readonly badgeBg: string;
  readonly badgeText: string;
  readonly borderColor: string;
  readonly dotColor: string;
}

const eventStyleMap: Record<TelemetryEventType, EventMetaStyle> = {
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

export function getEventStyle(eventType: TelemetryEventType): EventMetaStyle {
  return (
    eventStyleMap[eventType] ?? {
      label: defaultUnknownLabel,
      badgeBg: "bg-slate-900",
      badgeText: "text-slate-300",
      borderColor: "border-slate-700",
      dotColor: "bg-slate-400",
    }
  );
}

export function formatTimestampToTime(timestampMs: number): string {
  const date = new Date(timestampMs);
  const hours = String(date.getHours()).padStart(2, "0");
  const minutes = String(date.getMinutes()).padStart(2, "0");
  const seconds = String(date.getSeconds()).padStart(2, "0");
  const ms = String(date.getMilliseconds()).padStart(3, "0");
  return `${hours}:${minutes}:${seconds}.${ms}`;
}

export function truncateHash(hashString: string | undefined | null): string {
  if (!hashString) {
    return "—";
  }
  if (hashString.length <= hashTruncatePrefixLength + hashTruncateSuffixLength) {
    return hashString;
  }
  const prefix = hashString.slice(0, hashTruncatePrefixLength);
  const suffix = hashString.slice(-hashTruncateSuffixLength);
  return `${prefix}...${suffix}`;
}

export function formatPrettyJson(data: unknown): string {
  try {
    return JSON.stringify(data, null, 2);
  } catch {
    return String(data);
  }
}
