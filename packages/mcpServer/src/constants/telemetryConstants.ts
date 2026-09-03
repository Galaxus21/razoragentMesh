// Telemetry publishing config for the MCP tool layer.
//
// Why this exists: until now nothing in packages/mcpServer emitted telemetry -- the package
// held no HTTP client at all. A third-party agent calling get_live_sku_quote produced no
// events, so the dashboard stayed dark while an external agent worked. The MCP_TOOL_CALL and
// MCP_TOOL_RESULT events the panels render came only from the seeder (stamped SYNTHETIC) or
// from the dashboard's own driver mirroring steps it had executed itself.
//
// Publishing is best-effort by design: a tool call must never fail, or slow down, because the
// telemetry bus is unreachable.

export const mandateEngineUrlEnvVar = "MANDATE_ENGINE_URL";
export const fallbackMandateEngineUrl = "http://localhost:8000";
export const telemetryEventsPath = "/api/v1/telemetry/events";

// Matches the mandate engine's `^(LIVE|SYNTHETIC|UNKNOWN)$` provenance constraint. Every event
// this module sends describes a tool the mesh genuinely just executed, so LIVE is honest here.
// The dashboard's stream badge requires liveCount > 0 and zero unproven events to show LIVE.
export const liveProvenanceValue = "LIVE";

// Same budget the dashboard's own mirror uses. Long enough to survive a slow local hop, short
// enough that a dead bus cannot hold a tool response open.
export const telemetryTimeoutMs = 1500;

// Session id used when the server runs over stdio, where there is no transport-issued id.
// One per process: a stdio server serves exactly one client.
export const stdioSessionPrefix = "stdio";

export function resolveMandateEngineUrl(): string {
  const configured = process.env[mandateEngineUrlEnvVar]?.trim();
  return configured && configured.length > 0 ? configured : fallbackMandateEngineUrl;
}

export const millisecondsPerSecond = 1000;
