"use client";

import { useEffect, useRef, useState, useCallback } from "react";
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
} from "@/types/telemetryEventTypes";

export interface UseSseStreamOptions {
  readonly endpointUrl?: string;
  readonly filterType?: TelemetryEventType;
  readonly autoConnect?: boolean;
  readonly enableMockFallback?: boolean;
}

export interface UseSseStreamResult {
  readonly events: ReadonlyArray<TelemetryEvent>;
  readonly latestEvent: TelemetryEvent | null;
  readonly connectionState: SseConnectionState;
  readonly reconnectCount: number;
  readonly isConnected: boolean;
  readonly isMockActive: boolean;
  readonly clearEvents: () => void;
  readonly toggleMockMode: () => void;
  readonly injectMockEvent: (event: TelemetryEvent) => void;
}

export function useSseStream(options: UseSseStreamOptions = {}): UseSseStreamResult {
  const {
    endpointUrl = defaultSseUrl,
    filterType,
    autoConnect = true,
    enableMockFallback = true,
  } = options;

  const [events, setEvents] = useState<ReadonlyArray<TelemetryEvent>>([]);
  const [latestEvent, setLatestEvent] = useState<TelemetryEvent | null>(null);
  const [connectionState, setConnectionState] = useState<SseConnectionState>("DISCONNECTED");
  const [reconnectCount, setReconnectCount] = useState<number>(0);
  const [isMockActive, setIsMockActive] = useState<boolean>(false);

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

  const injectMockEvent = useCallback(
    (event: TelemetryEvent) => {
      handleIncomingEvent(event);
    },
    [handleIncomingEvent]
  );

  const toggleMockMode = useCallback(() => {
    setIsMockActive((prev) => !prev);
  }, []);

  const connectToStream = useCallback(() => {
    if (typeof window === "undefined" || isMockActive) {
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
        } catch {
          // Ignore parse errors on keepalive comments or non-JSON frames
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
          if (enableMockFallback) {
            setIsMockActive(true);
          }
        }
      };
    } catch {
      setConnectionState("ERROR");
    }
  }, [endpointUrl, isMockActive, handleIncomingEvent, enableMockFallback]);

  useEffect(() => {
    if (autoConnect && !isMockActive) {
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
  }, [autoConnect, isMockActive, connectToStream]);

  return {
    events,
    latestEvent,
    connectionState: isMockActive ? "CONNECTED" : connectionState,
    reconnectCount,
    isConnected: isMockActive || connectionState === "CONNECTED",
    isMockActive,
    clearEvents,
    toggleMockMode,
    injectMockEvent,
  };
}
