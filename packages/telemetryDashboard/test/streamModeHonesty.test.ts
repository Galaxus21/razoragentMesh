import { describe, it } from "node:test";
import assert from "node:assert/strict";
import { readFileSync } from "node:fs";
import path from "node:path";
import { fileURLToPath } from "node:url";

import {
  resolveEventProvenance,
  resolveStreamMode,
  summarizeStreamProvenance,
} from "../src/lib/streamModeResolver.js";
import { streamModePresentation } from "../src/constants/dashboardConstants.js";
import type {
  SseConnectionState,
  TelemetryEvent,
  TelemetryProvenance,
  TelemetryStreamMode,
} from "../src/types/telemetryEventTypes.js";

// These assertions exist because the header used to render "LIVE MESH SSE" whenever the SSE
// socket opened, which meant `scripts/seedTelemetryStream.py` -- a file of hardcoded fixtures --
// produced a screen indistinguishable from a real settlement. The rule under test is narrow:
// nothing but a run that actually happened may make the badge say LIVE.

const currentDirectory = path.dirname(fileURLToPath(import.meta.url));
const repositoryRoot = path.resolve(currentDirectory, "..", "..", "..");
const emitterSourcePath = path.join(
  repositoryRoot,
  "packages",
  "mandateEngine",
  "telemetryEmitter.py"
);
const seederSourcePath = path.join(repositoryRoot, "scripts", "seedTelemetryStream.py");

function buildEvent(provenance?: TelemetryProvenance): TelemetryEvent {
  return {
    eventId: `evt-${provenance ?? "absent"}`,
    eventType: "MANDATE_SIGNED",
    timestampMs: 1,
    sessionId: "session-test",
    ...(provenance ? { provenance } : {}),
    payload: {
      mandateType: "CART",
      mandateHash: "deadbeef",
      signerKeyDid: "did:agent:test",
      signatureHex: "00",
    },
  } as TelemetryEvent;
}

function buildHeartbeat(): TelemetryEvent {
  return {
    eventId: "evt-heartbeat",
    eventType: "HEARTBEAT",
    timestampMs: 1,
    sessionId: "session-test",
    payload: { serverTimestampMs: 1, activeSessionsCount: 0 },
  } as TelemetryEvent;
}

// Reads `name: type = "value"` / `name = "value"` style module constants without regex, so a
// stray backslash in the Python source can never silently break the parse.
function readQuotedPythonConstant(sourceText: string, constantName: string): string | null {
  for (const rawLine of sourceText.split("\n")) {
    const line = rawLine.trim();
    if (!line.startsWith(`${constantName}:`) && !line.startsWith(`${constantName} =`)) {
      continue;
    }
    const firstQuote = line.indexOf('"');
    const lastQuote = line.lastIndexOf('"');
    if (firstQuote === -1 || lastQuote <= firstQuote) {
      return null;
    }
    return line.slice(firstQuote + 1, lastQuote);
  }
  return null;
}

describe("Stream mode honesty: only a real run may be labelled LIVE", () => {
  it("treats an undeclared provenance as UNKNOWN rather than assuming it is live", () => {
    assert.equal(resolveEventProvenance(buildEvent()), "UNKNOWN");
    assert.equal(resolveEventProvenance(buildEvent("LIVE")), "LIVE");
    assert.equal(resolveEventProvenance(buildEvent("SYNTHETIC")), "SYNTHETIC");
  });

  it("reports IDLE when connected with nothing but heartbeats", () => {
    assert.equal(resolveStreamMode("CONNECTED", []), "IDLE");
    assert.equal(resolveStreamMode("CONNECTED", [buildHeartbeat(), buildHeartbeat()]), "IDLE");
  });

  it("reports REPLAY for seeded fixtures and never LIVE", () => {
    const mode = resolveStreamMode("CONNECTED", [
      buildEvent("SYNTHETIC"),
      buildEvent("SYNTHETIC"),
    ]);
    assert.equal(mode, "REPLAY");
    assert.notEqual(mode, "LIVE");
  });

  it("reports REPLAY for unstamped events, so a publisher cannot claim liveness by omission", () => {
    assert.equal(resolveStreamMode("CONNECTED", [buildEvent()]), "REPLAY");
  });

  it("reports LIVE only when every meaningful event came from a real run", () => {
    assert.equal(
      resolveStreamMode("CONNECTED", [buildEvent("LIVE"), buildHeartbeat(), buildEvent("LIVE")]),
      "LIVE"
    );
  });

  it("surfaces a fixture mixed into a live buffer instead of hiding it", () => {
    assert.equal(
      resolveStreamMode("CONNECTED", [buildEvent("LIVE"), buildEvent("SYNTHETIC")]),
      "MIXED"
    );
    assert.equal(
      resolveStreamMode("CONNECTED", [buildEvent("LIVE"), buildEvent()]),
      "MIXED"
    );
  });

  it("never claims LIVE while the transport is not connected, even holding live events", () => {
    const liveEvents = [buildEvent("LIVE"), buildEvent("LIVE")];
    const nonConnectedStates: ReadonlyArray<SseConnectionState> = [
      "CONNECTING",
      "DISCONNECTED",
      "ERROR",
    ];
    const expectedModes: ReadonlyArray<TelemetryStreamMode> = [
      "CONNECTING",
      "OFFLINE",
      "OFFLINE",
    ];

    nonConnectedStates.forEach((state, index) => {
      const mode = resolveStreamMode(state, liveEvents);
      assert.equal(mode, expectedModes[index]);
      assert.notEqual(mode, "LIVE");
    });
  });

  it("counts each provenance class separately so the badge tooltip can be audited", () => {
    const counts = summarizeStreamProvenance([
      buildEvent("LIVE"),
      buildEvent("SYNTHETIC"),
      buildEvent("SYNTHETIC"),
      buildEvent(),
      buildHeartbeat(),
    ]);
    assert.deepEqual(counts, { liveCount: 1, syntheticCount: 2, unknownCount: 1 });
  });
});

describe("Stream mode presentation", () => {
  it("gives every mode a label, colour and description", () => {
    const modes: ReadonlyArray<TelemetryStreamMode> = [
      "LIVE",
      "REPLAY",
      "MIXED",
      "IDLE",
      "CONNECTING",
      "OFFLINE",
    ];
    for (const mode of modes) {
      const presentation = streamModePresentation[mode];
      assert.ok(presentation, `Missing presentation for ${mode}`);
      assert.ok(presentation.label.length > 0);
      assert.ok(presentation.badgeClass.length > 0);
      assert.ok(presentation.dotClass.length > 0);
      assert.ok(presentation.description.length > 0);
    }
  });

  it("reserves the success colour for LIVE alone", () => {
    const successColouredModes = (
      ["LIVE", "REPLAY", "MIXED", "IDLE", "CONNECTING", "OFFLINE"] as const
    ).filter((mode) => streamModePresentation[mode].dotClass.includes("statusSuccess"));
    assert.deepEqual(successColouredModes, ["LIVE"]);
  });

  it("no longer lets the transport label claim liveness", () => {
    const modes = ["REPLAY", "MIXED", "IDLE", "CONNECTING", "OFFLINE"] as const;
    for (const mode of modes) {
      assert.ok(
        !streamModePresentation[mode].label.includes("LIVE"),
        `Mode ${mode} must not present itself as LIVE`
      );
    }
  });
});

describe("Publisher provenance stamps stay aligned across languages", () => {
  it("matches the provenance literals declared by the Python emitter", () => {
    const emitterSource = readFileSync(emitterSourcePath, "utf8");
    assert.equal(readQuotedPythonConstant(emitterSource, "provenanceLive"), "LIVE");
    assert.equal(readQuotedPythonConstant(emitterSource, "provenanceSynthetic"), "SYNTHETIC");
    assert.equal(readQuotedPythonConstant(emitterSource, "provenanceUnknown"), "UNKNOWN");
  });

  it("keeps the emitter defaulting to UNKNOWN, never to LIVE", () => {
    const emitterSource = readFileSync(emitterSourcePath, "utf8");
    const defaultingLine = emitterSource
      .split("\n")
      .find((line) => line.trim().startsWith("provenance: str = Field("));
    assert.ok(defaultingLine, "Emitter no longer declares a provenance field");
    assert.ok(
      defaultingLine.includes("default=provenanceUnknown"),
      "Emitter must default provenance to UNKNOWN so omission cannot imply liveness"
    );
  });

  it("keeps the telemetry seeder stamping SYNTHETIC on everything it emits", () => {
    const seederSource = readFileSync(seederSourcePath, "utf8");
    assert.equal(readQuotedPythonConstant(seederSource, "syntheticProvenanceValue"), "SYNTHETIC");
    assert.ok(
      seederSource.includes("event[provenanceFieldName] = syntheticProvenanceValue"),
      "Seeder must stamp every assembled event as SYNTHETIC"
    );
    assert.ok(
      !seederSource.includes("session_live_agent"),
      "Seeder must not label fixture sessions as live"
    );
  });
});
