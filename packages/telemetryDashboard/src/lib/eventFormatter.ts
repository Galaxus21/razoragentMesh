import {
  defaultEventStyleMap,
  defaultFallbackEventStyle,
  EventMetaStyle,
  hashTruncatePrefixLength,
  hashTruncateSuffixLength,
} from "@/constants/dashboardConstants";
import { TelemetryEventType } from "@/types/telemetryEventTypes";

export type { EventMetaStyle };

export function getEventStyle(eventType: TelemetryEventType): EventMetaStyle {
  return defaultEventStyleMap[eventType] ?? defaultFallbackEventStyle;
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
