// MCP Streamable HTTP transport.
//
// Why this exists: a judge running the mesh in Docker should be able to point their own agent
// (Claude Desktop, Claude Code, Cursor) at a URL and have it connect -- no clone, no npm install,
// no build. The pre-existing POST /rpc passthrough carries JSON-RPC but is not the Streamable
// HTTP transport: it has no session lifecycle, no SSE upgrade and no Mcp-Session-Id, so a
// spec-compliant client will not drive it.
//
// This uses the official SDK for the transport only. Tool behaviour still comes from the shared
// dispatcher, so a quote fetched over stdio, over /rpc, and over /mcp all execute the same
// pricing code. The manifest and dispatcher arrive through options rather than an import,
// because mcpServerMain already imports the HTTP adapter and importing back would cycle.

import { randomUUID } from "node:crypto";
import type http from "node:http";
import { Server } from "@modelcontextprotocol/sdk/server/index.js";
import { StreamableHTTPServerTransport } from "@modelcontextprotocol/sdk/server/streamableHttp.js";
import {
  CallToolRequestSchema,
  ListToolsRequestSchema,
  isInitializeRequest
} from "@modelcontextprotocol/sdk/types.js";
import { mcpServerName, mcpServerVersion } from "../constants/protocolConstants.js";
import { sessionHeaderName } from "../constants/httpAdapterConstants.js";

export interface McpStreamableOptions {
  readonly toolsManifest: ReadonlyArray<Record<string, unknown>>;
  readonly toolDispatcher: (
    toolName: string,
    toolArguments: unknown,
    context?: { readonly sessionId: string }
  ) => Promise<unknown>;
}

/** Live sessions, keyed by the id the SDK generates during initialize. */
const activeTransports = new Map<string, StreamableHTTPServerTransport>();

/**
 * Builds one MCP server bound to the shared tool registry.
 *
 * A fresh Server is created per session rather than shared, because the SDK binds a server to
 * exactly one transport. The tools it exposes are the same objects in every case.
 */
function buildMcpServer(
  options: McpStreamableOptions,
  getSessionId: () => string | undefined
): Server {
  const server = new Server(
    { name: mcpServerName, version: mcpServerVersion },
    { capabilities: { tools: {} } }
  );

  server.setRequestHandler(ListToolsRequestSchema, async () => ({
    tools: options.toolsManifest as never
  }));

  server.setRequestHandler(CallToolRequestSchema, async (request) => {
    const toolName = request.params.name;
    const toolArguments = request.params.arguments ?? {};
    // Read at call time, not at construction: the session id is issued during initialize,
    // which happens after this server is built and connected.
    const sessionId = getSessionId();
    try {
      const output = await options.toolDispatcher(
        toolName,
        toolArguments,
        sessionId ? { sessionId } : undefined
      );
      return { content: [{ type: "text" as const, text: JSON.stringify(output) }] };
    } catch (error: unknown) {
      // Matches the stdio path deliberately: a tool that refuses (out of stock, unserviceable
      // pincode) is a tool result carrying isError, not a transport fault. An agent can read
      // the reason and adapt; a JSON-RPC error would read as a broken server.
      const err = error as Error & { code?: string | number };
      return {
        content: [
          {
            type: "text" as const,
            text: JSON.stringify({ error: err.message, exceptionCode: err.code ?? null })
          }
        ],
        isError: true
      };
    }
  });

  return server;
}

/** Opens a new session and registers it so later requests on the same id reuse it. */
async function openSession(options: McpStreamableOptions, customSessionId?: string): Promise<StreamableHTTPServerTransport> {
  const sessionId = customSessionId ?? randomUUID();
  const transport = new StreamableHTTPServerTransport({
    sessionIdGenerator: () => sessionId,
    onsessioninitialized: (id: string) => {
      activeTransports.set(id, transport);
    }
  });

  transport.onclose = () => {
    if (transport.sessionId) {
      activeTransports.delete(transport.sessionId);
    }
  };

  await buildMcpServer(options, () => transport.sessionId).connect(transport);
  return transport;
}

function readSessionId(request: http.IncomingMessage): string | undefined {
  const raw = request.headers[sessionHeaderName];
  return Array.isArray(raw) ? raw[0] : raw;
}

/**
 * Handles one request on /mcp. Returns false when the request is not a valid session
 * interaction, so the caller can answer with its own error shape.
 */
export async function handleStreamableRequest(
  request: http.IncomingMessage,
  response: http.ServerResponse,
  parsedBody: unknown,
  options: McpStreamableOptions
): Promise<boolean> {
  // Handle server/discover if client probes capabilities before initialize
  if (parsedBody && typeof parsedBody === "object" && (parsedBody as Record<string, unknown>).method === "server/discover") {
    const id = (parsedBody as Record<string, unknown>).id ?? null;
    response.setHeader("Content-Type", "application/json");
    response.statusCode = 200;
    response.end(JSON.stringify({
      jsonrpc: "2.0",
      id,
      result: {
        serverInfo: { name: mcpServerName, version: mcpServerVersion },
        capabilities: { tools: {} }
      }
    }));
    return true;
  }

  const sessionId = readSessionId(request);
  const existingForId = sessionId ? activeTransports.get(sessionId) : undefined;

  // A session id we do not hold is REFUSED, not adopted. Minting a fresh session under the
  // caller's id looks like it works and then behaves inexplicably: the delegation, cart and
  // execution payload the client believed it had are gone, so the next tool call fails with
  // "Unknown or expired delegation_id" and nothing anywhere connects that to a dropped session.
  // Returning false here lets httpAdapter answer 400 InvalidSession, which tells the client to
  // re-initialize -- the one thing that actually recovers the situation.
  // initialize is exempt: it is the request that ESTABLISHES a session, so a client re-initializing
  // after a server restart may still be carrying its old id, and refusing that would strand the
  // one call that recovers.
  if (sessionId && !existingForId && !isInitializeRequest(parsedBody)) {
    return false;
  }
  let existing = existingForId;

  if (!existing && request.method === "GET") {
    const newId = randomUUID();
    existing = await openSession(options, newId);
    (existing as unknown as { _webStandardTransport: { _initialized: boolean; sessionId: string } })._webStandardTransport._initialized = true;
    (existing as unknown as { _webStandardTransport: { _initialized: boolean; sessionId: string } })._webStandardTransport.sessionId = newId;
    activeTransports.set(newId, existing);
  }

  if (existing) {
    await existing.handleRequest(request, response, parsedBody);
    return true;
  }

  if (request.method === "POST" && isInitializeRequest(parsedBody)) {
    const transport = await openSession(options);
    await transport.handleRequest(request, response, parsedBody);
    return true;
  }

  return false;
}

/** Closes every open session. Used on shutdown so sockets do not outlive the process. */
export async function closeAllStreamableSessions(): Promise<void> {
  const transports = Array.from(activeTransports.values());
  activeTransports.clear();
  await Promise.all(transports.map((transport) => transport.close().catch(() => undefined)));
}

export function countActiveStreamableSessions(): number {
  return activeTransports.size;
}
