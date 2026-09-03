import readline from "node:readline";
import { randomUUID } from "node:crypto";
import {
  jsonRpcVersion,
  mcpServerName,
  mcpServerVersion,
  methodNotFoundErrorCode,
  invalidParamsErrorCode,
  internalErrorCode,
  parseErrorCode,
  supportedProtocolVersions,
  preferredProtocolVersion,
  merchantPrivateKeyIsDevelopmentFallback,
  merchantSecretKeyIsDevelopmentFallback
} from "./constants/protocolConstants.js";
import {
  hmacKeyFallbackWarning,
  merchantKeyFallbackWarning
} from "./constants/mandateToolConstants.js";
import { mcpToolsManifest } from "./constants/toolsManifest.js";
import { stdioSessionPrefix } from "./constants/telemetryConstants.js";
import {
  newCallId,
  publishToolCall,
  publishToolRefusal,
  publishToolResult
} from "./telemetry/telemetryPublisher.js";
import {
  resolveTransportMode,
  shouldStartStdio,
  shouldStartHttp
} from "./constants/transportConstants.js";
import type {
  JsonRpcRequest,
  JsonRpcResponse
} from "./types/mcpToolTypes.js";
import { executeTool } from "./tools/toolRegistry.js";
import { startMcpHttpServer } from "./http/httpAdapter.js";
import { initializeCatalogSubscriber } from "./catalog/catalogSubscriber.js";
import { indexCompiledFixtures } from "./catalog/fixtureIndexer.js";

export type { JsonRpcRequest, JsonRpcResponse };

/** Identifies which agent's activity a tool call belongs to, for grouping on the dashboard. */
export interface ToolCallContext {
  readonly sessionId: string;
}

// A stdio server serves exactly one client, so one id per process is the whole session.
// The Streamable HTTP transport supplies its own per-connection id instead.
const stdioSessionId = `${stdioSessionPrefix}-${randomUUID()}`;

// Re-exported so existing importers (and tests) keep loading the manifest from here after it
// moved into constants/toolsManifest.ts.
export { mcpToolsManifest };

// Re-exported: this module is the package entry point, and tests import the subscriber
// from here. It now lives in catalog/catalogSubscriber.ts.
export { initializeCatalogSubscriber };


/**
 * The single tool registry. stdio, /rpc and the Streamable HTTP transport all route through
 * here, so a quote fetched over any of them executes identical pricing code -- and, since the
 * telemetry publish happens here rather than per transport, every transport reports its work
 * the same way. Instrumenting the transports individually would let them drift.
 *
 * `context.sessionId` is what groups one agent's calls into one visible run on the dashboard.
 */
export async function dispatchToolCall(
  toolName: string,
  toolArguments: unknown,
  context?: ToolCallContext
): Promise<unknown> {
  const sessionId = context?.sessionId ?? stdioSessionId;
  const callId = newCallId();
  const startedAtMs = Date.now();

  publishToolCall(toolName, toolArguments, sessionId, callId);
  try {
    const output = await executeTool(toolName, toolArguments);
    publishToolResult(toolName, toolArguments, output, sessionId, callId, Date.now() - startedAtMs);
    return output;
  } catch (error: unknown) {
    publishToolRefusal(toolName, error, sessionId, callId, Date.now() - startedAtMs);
    throw error;
  }
}

function buildJsonRpcError(
  requestId: string | number | null,
  code: number,
  message: string,
  data?: unknown
): JsonRpcResponse {
  return {
    jsonrpc: jsonRpcVersion,
    id: requestId,
    error: {
      code,
      message,
      ...(data !== undefined ? { data } : {})
    }
  };
}

function handleInitializeRequest(
  requestId: string | number | null,
  params: unknown
): JsonRpcResponse {
  // Echo the client's requested revision when we implement it. Answering every client with
  // one hardcoded version makes a strict client abort a handshake it would otherwise accept.
  const requested = (params as { protocolVersion?: string } | undefined)?.protocolVersion;
  const negotiated =
    requested && supportedProtocolVersions.includes(requested) ? requested : preferredProtocolVersion;

  return {
    jsonrpc: jsonRpcVersion,
    id: requestId,
    result: {
      protocolVersion: negotiated,
      serverInfo: { name: mcpServerName, version: mcpServerVersion },
      capabilities: { tools: {} }
    }
  };
}

function handleToolsListRequest(requestId: string | number | null): JsonRpcResponse {
  return {
    jsonrpc: jsonRpcVersion,
    id: requestId,
    result: { tools: mcpToolsManifest }
  };
}

async function handleToolsCallRequest(
  requestId: string | number | null,
  params: unknown
): Promise<JsonRpcResponse> {
  const toolParams = params as { name?: string; arguments?: unknown } | undefined;
  const toolName = toolParams?.name;
  const toolArgs = toolParams?.arguments ?? {};

  if (!toolName) {
    return buildJsonRpcError(requestId, invalidParamsErrorCode, "Missing tool name in params");
  }

  // An unknown tool is a protocol-level "no such method", not an internal fault.
  if (!mcpToolsManifest.some((tool) => tool.name === toolName)) {
    return buildJsonRpcError(requestId, methodNotFoundErrorCode, `Tool ${toolName} not found`);
  }

  try {
    const output = await dispatchToolCall(toolName, toolArgs);
    return {
      jsonrpc: jsonRpcVersion,
      id: requestId,
      result: {
        content: [{ type: "text", text: JSON.stringify(output) }]
      }
    };
  } catch (error: unknown) {
    // A tool that refuses (out of stock, unserviceable pincode) is a TOOL result, not a
    // transport fault -- MCP carries it as isError inside result so the agent can read the
    // reason and adapt. Emitting it as a JSON-RPC error made the client treat a working
    // refusal as a broken server, and the code used (409) was outside the reserved band.
    const err = error as Error & { code?: string | number };
    return {
      jsonrpc: jsonRpcVersion,
      id: requestId,
      result: {
        content: [
          {
            type: "text",
            text: JSON.stringify({ error: err.message, exceptionCode: err.code ?? null })
          }
        ],
        isError: true
      }
    };
  }
}

/**
 * Returns null when the message is a JSON-RPC notification, meaning the caller must send
 * nothing at all. Every MCP client sends `notifications/initialized` immediately after the
 * handshake; answering it with an error -- as this did, because `id ?? null` erased the
 * difference between "no id" and "id: null" -- violates JSON-RPC 2.0 and can abort the
 * connection before the first tool call.
 */
export async function handleJsonRpcMessage(
  request: JsonRpcRequest
): Promise<JsonRpcResponse | null> {
  const isNotification = request.id === undefined;
  const requestId = request.id ?? null;

  if (isNotification) {
    return null;
  }

  if (request.method === "initialize") {
    return handleInitializeRequest(requestId, request.params);
  }
  if (request.method === "ping") {
    return { jsonrpc: jsonRpcVersion, id: requestId, result: {} };
  }
  if (request.method === "tools/list") {
    return handleToolsListRequest(requestId);
  }
  if (request.method === "tools/call") {
    return handleToolsCallRequest(requestId, request.params);
  }

  return buildJsonRpcError(
    requestId,
    methodNotFoundErrorCode,
    `Method ${request.method} not found`
  );
}

export function startMcpServer(): void {
  const lineReader = readline.createInterface({
    input: process.stdin,
    output: process.stdout,
    terminal: false
  });

  lineReader.on("line", async (line: string) => {
    const trimmed = line.trim();
    if (trimmed.length === 0) {
      return;
    }
    let parsed: JsonRpcRequest;
    try {
      parsed = JSON.parse(trimmed) as JsonRpcRequest;
    } catch (parseError: unknown) {
      // A malformed line previously produced no reply at all, leaving the client waiting on a
      // response that would never arrive. JSON-RPC requires -32700 with a null id.
      const err = parseError as Error;
      process.stderr.write(`[MCP Error] Failed to parse message: ${err.message}\n`);
      const parseFailure = buildJsonRpcError(null, parseErrorCode, "Parse error");
      process.stdout.write(`${JSON.stringify(parseFailure)}\n`);
      return;
    }

    try {
      const response = await handleJsonRpcMessage(parsed);
      // null means the message was a notification: write nothing.
      if (response !== null) {
        process.stdout.write(`${JSON.stringify(response)}\n`);
      }
    } catch (handlerError: unknown) {
      const err = handlerError as Error;
      process.stderr.write(`[MCP Error] Failed to process message: ${err.message}\n`);
      const failure = buildJsonRpcError(parsed.id ?? null, internalErrorCode, err.message);
      process.stdout.write(`${JSON.stringify(failure)}\n`);
    }
  });
}

// Both transports normally run together: stdio for MCP clients, HTTP for the buyer SDKs and
// the telemetry dashboard's protocol driver. They share `dispatchToolCall`, so a quote fetched
// over REST and one fetched over JSON-RPC execute identical pricing code.
//
// MCP_TRANSPORT=stdio exists for the side-by-side demo: the mesh is already serving HTTP on
// this port from Docker, so a client launching a second copy over stdio must not try to bind
// it again.
export function startAllTransports(): void {
  const transportMode = resolveTransportMode();
  warnOnDevelopmentSigningKeys();
  initializeCatalogSubscriber();
  // Deliberately not awaited, and it never rejects: the compiled fixtures are already quotable
  // from the in-process store, so indexing them is what makes them SEARCHABLE and nothing more.
  // Blocking boot on merchant-api being reachable would trade a working mesh for a nicer one.
  void indexCompiledFixtures();

  if (shouldStartStdio(transportMode)) {
    startMcpServer();
  }
  if (shouldStartHttp(transportMode)) {
    startMcpHttpServer({
      jsonRpcHandler: (message: unknown) => handleJsonRpcMessage(message as JsonRpcRequest),
      toolsManifest: mcpToolsManifest,
      toolDispatcher: dispatchToolCall
    });
  }
}

/**
 * Says out loud when this process is signing with keys committed to the repository.
 *
 * `merchantKeyFallbackWarning` has existed since the mandate tools landed, and its own text says
 * it is "emitted at startup" -- but nothing imported it, so the emission never happened. A
 * constant describing behaviour that does not occur is the same defect the rest of this audit is
 * about, one level down.
 */
export function warnOnDevelopmentSigningKeys(): void {
  if (merchantPrivateKeyIsDevelopmentFallback) {
    process.stderr.write(merchantKeyFallbackWarning);
  }
  if (merchantSecretKeyIsDevelopmentFallback) {
    process.stderr.write(hmacKeyFallbackWarning);
  }
}

if (process.argv[1] && (process.argv[1].endsWith("mcpServerMain.ts") || process.argv[1].endsWith("mcpServerMain.js"))) {
  startAllTransports();
}
