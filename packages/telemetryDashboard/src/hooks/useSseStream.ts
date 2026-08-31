"use client";

import { useEffect, useMemo, useRef, useState, useCallback } from "react";
import {
  resolveStreamMode,
  summarizeStreamProvenance,
  type StreamProvenanceCounts,
} from "@/lib/streamModeResolver";
import {
  defaultSseUrl,
  maxEventBufferSize,
  maxReconnectAttempts,
  reconnectBackoffFactor,
  reconnectBaseDelayMs,
  reconnectMaxDelayMs,
} from "@/constants/dashboardConstants";
import {
  SseConnectionState,
  TelemetryEvent,
  TelemetryEventType,
  TelemetryStreamMode,
} from "@/types/telemetryEventTypes";

export interface UseSseStreamOptions {
  readonly endpointUrl?: string;
  readonly filterType?: TelemetryEventType;
  readonly autoConnect?: boolean;
}

export interface UseSseStreamResult {
  readonly events: ReadonlyArray<TelemetryEvent>;
  readonly latestEvent: TelemetryEvent | null;
  readonly connectionState: SseConnectionState;
  readonly reconnectCount: number;
  readonly streamMode: TelemetryStreamMode;
  readonly provenanceCounts: StreamProvenanceCounts;
  readonly clearEvents: () => void;
}

export function useSseStream(options: UseSseStreamOptions = {}): UseSseStreamResult {
  const {
    endpointUrl = defaultSseUrl,
    filterType,
    autoConnect = true,
  } = options;

  const [events, setEvents] = useState<ReadonlyArray<TelemetryEvent>>([]);
  const [latestEvent, setLatestEvent] = useState<TelemetryEvent | null>(null);
  const [connectionState, setConnectionState] = useState<SseConnectionState>("DISCONNECTED");
  const [reconnectCount, setReconnectCount] = useState<number>(0);

  const eventSourceRef = useRef<EventSource | null>(null);
  const reconnectTimeoutRef = useRef<NodeJS.Timeout | null>(null);
  const attemptsRef = useRef<number>(0);

  const handleIncomingEvent = useCallback(
    (event: TelemetryEvent) => {
      setLatestEvent(event);
      setEvents((prevEvents) => {
        if (filterType && event.eventType !== filterType) {
          return prevEvents;
        }
        const updated = [event, ...prevEvents];
        if (updated.length > maxEventBufferSize) {
          return updated.slice(0, maxEventBufferSize);
        }
        return updated;
      });
    },
    [filterType]
  );

  const clearEvents = useCallback(() => {
    setEvents([]);
    setLatestEvent(null);
  }, []);

  const connectToStream = useCallback(() => {
    if (typeof window === "undefined") {
      return;
    }

    if (eventSourceRef.current) {
      eventSourceRef.current.close();
    }

    setConnectionState("CONNECTING");
    try {
      const source = new EventSource(endpointUrl);
      eventSourceRef.current = source;

      source.onopen = () => {
        setConnectionState("CONNECTED");
        attemptsRef.current = 0;
        setReconnectCount(0);
      };

      source.onmessage = (messageEvent) => {
        try {
          const parsed = JSON.parse(messageEvent.data) as TelemetryEvent;
          handleIncomingEvent(parsed);
        } catch (error) {
          console.warn("Malformed catalog message:", error);
        }
      };

      source.onerror = () => {
        setConnectionState("ERROR");
        source.close();
        eventSourceRef.current = null;

        if (attemptsRef.current < maxReconnectAttempts) {
          const nextAttempt = attemptsRef.current + 1;
          attemptsRef.current = nextAttempt;
          setReconnectCount(nextAttempt);

          const delay = Math.min(
            reconnectBaseDelayMs * Math.pow(reconnectBackoffFactor, nextAttempt - 1),
            reconnectMaxDelayMs
          );

          reconnectTimeoutRef.current = setTimeout(() => {
            connectToStream();
          }, delay);
        } else {
          setConnectionState("DISCONNECTED");
        }
      };
    } catch {
      setConnectionState("ERROR");
    }
  }, [endpointUrl, handleIncomingEvent]);

  useEffect(() => {
    if (autoConnect) {
      connectToStream();
    }

    return () => {
      if (eventSourceRef.current) {
        eventSourceRef.current.close();
      }
      if (reconnectTimeoutRef.current) {
        clearTimeout(reconnectTimeoutRef.current);
      }
    };
  }, [autoConnect, connectToStream]);

  const streamMode = useMemo(
    () => resolveStreamMode(connectionState, events),
    [connectionState, events]
  );
  const provenanceCounts = useMemo(() => summarizeStreamProvenance(events), [events]);

  return {
    events,
    latestEvent,
    connectionState,
    reconnectCount,
    streamMode,
    provenanceCounts,
    clearEvents,
  };
}
