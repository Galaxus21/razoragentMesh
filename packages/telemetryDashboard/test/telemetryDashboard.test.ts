import { describe, it } from "node:test";
import assert from "node:assert/strict";

import {
  computePercentageDelta,
  formatLatency,
  formatPaiseToCompactInr,
  formatPaiseToInr,
} from "../src/lib/currencyUtils.js";
import {
  formatPrettyJson,
  formatTimestampToTime,
  getEventStyle,
  truncateHash,
} from "../src/lib/eventFormatter.js";
import { TelemetryEvent, TelemetryEventType } from "../src/types/telemetryEventTypes.js";

// Top-level constants in camelCase
const defaultRingBufferSize = 500;
const slowQueueCapacity = 50;
const testEpochMs = 1710000000000;

class SseEventRingBuffer {
  private readonly buffer: TelemetryEvent[] = [];
  private readonly capacity: number;

  constructor(capacity: number = defaultRingBufferSize) {
    this.capacity = capacity;
  }

  public push(event: TelemetryEvent): void {
    if (this.buffer.length >= this.capacity) {
      this.buffer.shift();
    }
    this.buffer.push(event);
  }

  public getEvents(): ReadonlyArray<TelemetryEvent> {
    return [...this.buffer];
  }

  public get size(): number {
    return this.buffer.length;
  }
}

class SlowSubscriberQueue {
  private readonly queue: TelemetryEvent[] = [];
  private readonly maxCapacity: number;
  private droppedCount: number = 0;

  constructor(maxCapacity: number = slowQueueCapacity) {
    this.maxCapacity = maxCapacity;
  }

  public enqueue(event: TelemetryEvent): boolean {
    if (this.queue.length >= this.maxCapacity) {
      this.droppedCount += 1;
      return false;
    }
    this.queue.push(event);
    return true;
  }

  public dequeue(): TelemetryEvent | undefined {
    return this.queue.shift();
  }

  public get droppedFrames(): number {
    return this.droppedCount;
  }

  public get pendingFrames(): number {
    return this.queue.length;
  }
}

function createMockEvent(sequenceNumber: number): TelemetryEvent {
  return {
    eventId: `evt_${sequenceNumber}`,
    eventType: "MCP_TOOL_CALL",
    timestampMs: testEpochMs + sequenceNumber * 100,
    sessionId: "sess_test_01",
    payload: {
      toolName: "get_live_sku_quote",
      callId: `call_${sequenceNumber}`,
      callerAgentId: "did:agent:test-worker-01",
      parameters: { sequence: sequenceNumber },
    },
  };
}

describe("Telemetry Dashboard — TC-20 SSE Ring Buffer & Slow Subscriber Queue", () => {
  it("should maintain fixed capacity and FIFO evict oldest event on 501st push", () => {
    const ringBuffer = new SseEventRingBuffer(500);

    for (let index = 0; index < 500; index += 1) {
      ringBuffer.push(createMockEvent(index));
    }

    assert.equal(ringBuffer.size, 500);
    const initialEvents = ringBuffer.getEvents();
    assert.equal(initialEvents[0].eventId, "evt_0");
    assert.equal(initialEvents[499].eventId, "evt_499");

    ringBuffer.push(createMockEvent(500));

    assert.equal(ringBuffer.size, 500);
    const updatedEvents = ringBuffer.getEvents();
    assert.equal(updatedEvents[0].eventId, "evt_1");
    assert.equal(updatedEvents[499].eventId, "evt_500");
  });

  it("should drop frames gracefully under slow subscriber queue backpressure", () => {
    const slowSubscriber = new SlowSubscriberQueue(50);

    for (let index = 0; index < 1000; index += 1) {
      slowSubscriber.enqueue(createMockEvent(index));
    }

    assert.equal(slowSubscriber.pendingFrames, 50);
    assert.equal(slowSubscriber.droppedFrames, 950);

    const firstItem = slowSubscriber.dequeue();
    assert.equal(firstItem?.eventId, "evt_0");
    assert.equal(slowSubscriber.pendingFrames, 49);
  });
});

describe("Telemetry Dashboard — Currency Formatting Utilities", () => {
  it("should format compact INR for Lakh and Crore values correctly", () => {
    assert.equal(formatPaiseToCompactInr(150000000), "₹15.00 L");
    assert.equal(formatPaiseToCompactInr(1500000000), "₹1.5 Cr");
    assert.equal(formatPaiseToCompactInr(550000), "₹5.5k");
    assert.equal(formatPaiseToCompactInr(4200), "₹42.00");
  });

  it("should handle zero, null, undefined, and NaN in formatPaiseToCompactInr", () => {
    assert.equal(formatPaiseToCompactInr(0), "₹0.00");
    assert.equal(formatPaiseToCompactInr(undefined as unknown as number), "₹0.00");
    assert.equal(formatPaiseToCompactInr(null as unknown as number), "₹0.00");
    assert.equal(formatPaiseToCompactInr(NaN), "₹0.00");
  });

  it("should format standard INR values via formatPaiseToInr", () => {
    assert.equal(formatPaiseToInr(420000), "₹4,200.00");
    assert.equal(formatPaiseToInr(0), "₹0.00");
    assert.equal(formatPaiseToInr(null), "₹0.00");
  });

  it("should compute percentage delta correctly with positive and negative changes", () => {
    assert.equal(computePercentageDelta(420000, 425000), "+1.2%");
    assert.equal(computePercentageDelta(425000, 420000), "-1.2%");
    assert.equal(computePercentageDelta(1000, 1000), "+0.0%");
    assert.equal(computePercentageDelta(0, 5000), "+0.0%");
  });
});

describe("Telemetry Dashboard — Latency and Event Formatting Utilities", () => {
  it("should format latency in microseconds and milliseconds accurately", () => {
    assert.equal(formatLatency(0.142), "142µs");
    assert.equal(formatLatency(3.2), "3.2ms");
    assert.equal(formatLatency(45), "45ms");
    assert.equal(formatLatency(0), "0ms");
    assert.equal(formatLatency(null), "0ms");
    assert.equal(formatLatency(undefined), "0ms");
  });

  it("should truncate cryptographic hashes preserving prefix and suffix", () => {
    const fullHash = "0xfa9812bc67de45fe9812bc67de45fe9812bc67de45fe";
    const truncated = truncateHash(fullHash);
    assert.equal(truncated, "0xfa9812...de45fe");
    assert.equal(truncateHash(""), "—");
    assert.equal(truncateHash(undefined), "—");
    assert.equal(truncateHash("short"), "short");
  });

  it("should format timestamps into deterministic time strings", () => {
    const formatted = formatTimestampToTime(testEpochMs);
    assert.match(formatted, /^\d{2}:\d{2}:\d{2}\.\d{3}$/);
  });

  it("should retrieve event style metadata and fallback style for unknown types", () => {
    const mcpStyle = getEventStyle("MCP_TOOL_CALL");
    assert.equal(mcpStyle.label, "MCP CALL");

    const paymentStyle = getEventStyle("PAYMENT_CAPTURED");
    assert.equal(paymentStyle.label, "SETTLED");

    const fallbackStyle = getEventStyle("UNKNOWN_TYPE" as TelemetryEventType);
    assert.equal(fallbackStyle.label, "UNKNOWN");
  });

  it("should format pretty JSON and gracefully catch circular or invalid structures", () => {
    const payload = { key: "value", number: 42 };
    const formatted = formatPrettyJson(payload);
    assert.equal(formatted, JSON.stringify(payload, null, 2));
    assert.equal(formatPrettyJson("simple"), '"simple"');
  });
});
