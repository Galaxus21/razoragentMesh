// Transport selection. The server can run stdio, HTTP, or both.
//
// Why this exists: startAllTransports used to bind 0.0.0.0:PORT unconditionally, so launching
// the server over stdio from an MCP client while the Docker mesh was already up produced
// EADDRINUSE -- and with no error handler on the HTTP server, that killed the MCP session.
// A judge running the dashboard in one window cannot connect an agent in the other without
// this. Default stays "both" so the container's behaviour is unchanged.

export const transportModeStdio = "stdio";
export const transportModeHttp = "http";
export const transportModeBoth = "both";

export type TransportMode =
  | typeof transportModeStdio
  | typeof transportModeHttp
  | typeof transportModeBoth;

export const transportModeEnvVar = "MCP_TRANSPORT";
export const defaultTransportMode: TransportMode = transportModeBoth;

const validTransportModes: ReadonlyArray<TransportMode> = [
  transportModeStdio,
  transportModeHttp,
  transportModeBoth
];

/**
 * Reads MCP_TRANSPORT and falls back to "both" for an unset or unrecognised value.
 * An unrecognised value is reported on stderr rather than thrown: a typo in a client's
 * config should not stop the server from starting in its default configuration.
 */
export function resolveTransportMode(rawValue?: string): TransportMode {
  const candidate = (rawValue ?? process.env[transportModeEnvVar] ?? "").trim().toLowerCase();
  if (candidate.length === 0) {
    return defaultTransportMode;
  }
  if (validTransportModes.includes(candidate as TransportMode)) {
    return candidate as TransportMode;
  }
  process.stderr.write(
    `[MCP] Unrecognised ${transportModeEnvVar}="${candidate}". ` +
      `Expected one of ${validTransportModes.join(", ")}. Falling back to "${defaultTransportMode}".\n`
  );
  return defaultTransportMode;
}

export function shouldStartStdio(mode: TransportMode): boolean {
  return mode === transportModeStdio || mode === transportModeBoth;
}

export function shouldStartHttp(mode: TransportMode): boolean {
  return mode === transportModeHttp || mode === transportModeBoth;
}
