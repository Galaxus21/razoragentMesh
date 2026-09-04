// Runs before any test module loads, via --import in the test script.
//
// The tool handlers publish telemetry as a side effect, and the publisher posts to
// MANDATE_ENGINE_URL, which defaults to the local mandate engine. So running the suite against a
// live `docker compose up` injected real events into the demo stream: a monitored buyer-agent run
// picked up three phantom get_live_sku_quote calls and a "1 refused -- protocol worked" session
// that no agent had made, mid-analysis. Tests must not write to the running mesh.
//
// Pointed at a closed port rather than stubbed: publishEvent already swallows transport failures
// by design, so the handlers take exactly the path they take in production, minus the delivery.
const telemetrySinkEnvVar = "MANDATE_ENGINE_URL";
const closedLoopbackPort = "http://127.0.0.1:9";

if (!process.env[telemetrySinkEnvVar]) {
  process.env[telemetrySinkEnvVar] = closedLoopbackPort;
}
