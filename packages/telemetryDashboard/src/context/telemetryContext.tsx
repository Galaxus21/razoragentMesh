"use client";

import React, { createContext, useContext, useMemo } from "react";
import { useSseStream } from "@/hooks/useSseStream";
import type { StreamProvenanceCounts } from "@/lib/streamModeResolver";
import {
  SseConnectionState,
  TelemetryEvent,
  TelemetryStreamMode,
} from "@/types/telemetryEventTypes";

export interface TelemetryContextValue {
  readonly events: ReadonlyArray<TelemetryEvent>;
  readonly latestEvent: TelemetryEvent | null;
  readonly connectionState: SseConnectionState;
  readonly streamMode: TelemetryStreamMode;
  readonly provenanceCounts: StreamProvenanceCounts;
  readonly clearEvents: () => void;
}

export interface TelemetryProviderProps {
  readonly children: React.ReactNode;
}

const TelemetryContext = createContext<TelemetryContextValue | null>(null);

export function TelemetryProvider({ children }: TelemetryProviderProps): React.JSX.Element {
  const stream = useSseStream({
    autoConnect: true,
  });

  const value = useMemo<TelemetryContextValue>(() => ({
    events: stream.events,
    latestEvent: stream.latestEvent,
    connectionState: stream.connectionState,
    streamMode: stream.streamMode,
    provenanceCounts: stream.provenanceCounts,
    clearEvents: stream.clearEvents,
  }), [
    stream.events,
    stream.latestEvent,
    stream.connectionState,
    stream.streamMode,
    stream.provenanceCounts,
    stream.clearEvents,
  ]);

  return (
    <TelemetryContext.Provider value={value}>
      {children}
    </TelemetryContext.Provider>
  );
}

export function useTelemetry(): TelemetryContextValue {
  const context = useContext(TelemetryContext);
  if (!context) {
    throw new Error("useTelemetry must be used within a TelemetryProvider");
  }
  return context;
}
