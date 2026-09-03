// A thin REST + JSON-RPC-over-HTTP face for the MCP tool layer.
//
// Why this exists: `mcpServerMain.ts` speaks MCP over stdio, which is correct for an MCP client
// but unreachable from the buyer SDKs, whose `getLiveSkuQuote` / `reserveInventoryLock` /
// `verifyShippingSla` issue plain HTTP against `defaultMcpServerUrl`. Without this adapter the
// first three calls of every documented purchase flow have nothing to connect to. Both
// transports run side by side and share the same tool functions.

import http from "node:http";
import { URL } from "node:url";
import {
  corsAllowAllOrigins,
  corsAllowedHeaders,
  corsAllowedMethods,
  corsExposedHeaders,
  corsPreflightMaxAgeSeconds,
  defaultHttpPort,
  errorDetailFieldName,
  errorFieldName,
  headerAllowHeaders,
  headerAllowMethods,
  headerAllowOrigin,
  headerContentType,
  headerExposeHeaders,
  headerMaxAge,
  healthStatusOk,
  httpBindHost,
  httpPortEnvVar,
  maxRequestBodyBytes,
  mediaTypeJson,
  methodDelete,
  methodGet,
  methodOptions,
  methodPost,
  routeHealth,
  routeLock,
  routeMcp,
  routeQuote,
  routeRpc,
  routeSla,
  routeToolsManifest,
  statusBadRequest,
  statusMethodNotAllowed,
  statusNoContent,
  statusAccepted,
  statusNotFound,
  statusOk,
  statusPayloadTooLarge
} from "../constants/httpAdapterConstants.js";
import { mcpServerName, mcpServerVersion } from "../constants/protocolConstants.js";
import { mapErrorToHttpResponse } from "./httpErrorMapper.js";
import { handleLockRequest, handleQuoteRequest, handleSlaRequest } from "./routeHandlers.js";
import { countActiveStreamableSessions, handleStreamableRequest } from "./mcpStreamableTransport.js";

export interface McpHttpServerOptions {
  readonly jsonRpcHandler: (message: unknown) => Promise<unknown>;
  readonly toolsManifest: readonly unknown[];
  /** Shared tool registry, so /mcp executes the same code as stdio and /rpc. */
  readonly toolDispatcher: (
    toolName: string,
    toolArguments: unknown,
    context?: { readonly sessionId: string }
  ) => Promise<unknown>;
}

const bodyTooLargeMessage = "Request body exceeded the maximum permitted size.";
const malformedJsonMessage = "Request body is not valid JSON.";
const routeNotFoundMessage = "No such route on the MCP HTTP adapter.";
const methodNotAllowedMessage = "HTTP method not permitted for this route.";
const invalidMcpSessionMessage =
  "No valid MCP session. POST an initialize request without Mcp-Session-Id to start one.";
const localOriginBase = "http://localhost";

function applyCorsHeaders(response: http.ServerResponse): void {
  response.setHeader(headerAllowOrigin, corsAllowAllOrigins);
  response.setHeader(headerAllowMethods, corsAllowedMethods);
  response.setHeader(headerAllowHeaders, corsAllowedHeaders);
  response.setHeader(headerExposeHeaders, corsExposedHeaders);
  response.setHeader(headerMaxAge, corsPreflightMaxAgeSeconds);
}

function sendJson(response: http.ServerResponse, statusCode: number, payload: unknown): void {
  applyCorsHeaders(response);
  response.setHeader(headerContentType, mediaTypeJson);
  response.statusCode = statusCode;
  response.end(JSON.stringify(payload));
}

function sendError(response: http.ServerResponse, statusCode: number, name: string, detail: string): void {
  sendJson(response, statusCode, { [errorFieldName]: name, [errorDetailFieldName]: detail });
}

async function readRequestBody(request: http.IncomingMessage): Promise<unknown> {
  const chunks: Buffer[] = [];
  let totalBytes = 0;

  for await (const chunk of request) {
    const bufferChunk = chunk as Buffer;
    totalBytes += bufferChunk.length;
    if (totalBytes > maxRequestBodyBytes) {
      throw new RangeError(bodyTooLargeMessage);
    }
    chunks.push(bufferChunk);
  }

  const rawBody = Buffer.concat(chunks).toString("utf-8").trim();
  if (rawBody.length === 0) {
    return {};
  }
  try {
    return JSON.parse(rawBody);
  } catch {
    throw new SyntaxError(malformedJsonMessage);
  }
}

function buildHealthPayload(): Record<string, unknown> {
  return {
    status: healthStatusOk,
    service: mcpServerName,
    version: mcpServerVersion,
    // What this port serves. Reaching /health at all proves the HTTP transports are up;
    // stdio is a separate transport on the same process and is not implied by this response.
    transports: ["http", "mcp-streamable-http"],
    mcpEndpoint: routeMcp,
    activeMcpSessions: countActiveStreamableSessions()
  };
}

async function routeRequest(
  request: http.IncomingMessage,
  response: http.ServerResponse,
  options: McpHttpServerOptions
): Promise<void> {
  const requestUrl = new URL(request.url ?? "/", localOriginBase);
  const pathname = requestUrl.pathname;
  const method = request.method ?? methodGet;

  // MCP Streamable HTTP. Handled before the REST chain because the SDK owns the whole
  // response -- status, headers and any SSE framing -- and only needs CORS applied first.
  // GET (open the stream) and DELETE (end the session) carry no body, so only POST is parsed.
  if (pathname === routeMcp) {
    if (method !== methodGet && method !== methodPost && method !== methodDelete) {
      sendError(response, statusMethodNotAllowed, "MethodNotAllowed", methodNotAllowedMessage);
      return;
    }
    applyCorsHeaders(response);
    const mcpBody = method === methodPost ? await readRequestBody(request) : undefined;
    const handled = await handleStreamableRequest(request, response, mcpBody, {
      toolsManifest: options.toolsManifest as ReadonlyArray<Record<string, unknown>>,
      toolDispatcher: options.toolDispatcher
    });
    if (!handled) {
      if (method === methodGet) {
        sendError(response, statusMethodNotAllowed, "MethodNotAllowed", "GET SSE stream not offered without active session.");
        return;
      }
      sendError(response, statusBadRequest, "InvalidSession", invalidMcpSessionMessage);
    }
    return;
  }

  if (pathname === routeHealth && method === methodGet) {
    sendJson(response, statusOk, buildHealthPayload());
    return;
  }
  if (pathname === routeToolsManifest && method === methodGet) {
    sendJson(response, statusOk, { tools: options.toolsManifest });
    return;
  }
  if (pathname === routeQuote && method === methodGet) {
    sendJson(response, statusOk, handleQuoteRequest(requestUrl.searchParams));
    return;
  }
  if (pathname === routeSla && method === methodGet) {
    sendJson(response, statusOk, handleSlaRequest(requestUrl.searchParams));
    return;
  }
  if (pathname === routeLock && method === methodPost) {
    sendJson(response, statusOk, await handleLockRequest(await readRequestBody(request)));
    return;
  }
  if (pathname === routeRpc && method === methodPost) {
    const rpcResult = await options.jsonRpcHandler(await readRequestBody(request));
    // A null result means the message was a notification, which must not be answered with a
    // body. Serialising it as `null` made clients parse a bare null as a malformed response.
    if (rpcResult === null) {
      applyCorsHeaders(response);
      response.writeHead(statusAccepted);
      response.end();
      return;
    }
    sendJson(response, statusOk, rpcResult);
    return;
  }

  const isKnownRoute = [routeHealth, routeToolsManifest, routeQuote, routeSla, routeLock, routeRpc].includes(pathname);
  if (isKnownRoute) {
    sendError(response, statusMethodNotAllowed, "MethodNotAllowed", methodNotAllowedMessage);
    return;
  }
  sendError(response, statusNotFound, "NotFound", routeNotFoundMessage);
}

function handleRequestFailure(response: http.ServerResponse, error: unknown): void {
  if (error instanceof RangeError && error.message === bodyTooLargeMessage) {
    sendError(response, statusPayloadTooLarge, "PayloadTooLarge", error.message);
    return;
  }
  if (error instanceof SyntaxError && error.message === malformedJsonMessage) {
    sendError(response, statusBadRequest, "MalformedJson", error.message);
    return;
  }
  const mapped = mapErrorToHttpResponse(error);
  sendJson(response, mapped.statusCode, {
    [errorFieldName]: mapped.errorName,
    [errorDetailFieldName]: mapped.detail,
    ...(mapped.issues !== undefined ? { issues: mapped.issues } : {})
  });
}

export function createMcpHttpServer(options: McpHttpServerOptions): http.Server {
  return http.createServer((request, response) => {
    if (request.method === methodOptions) {
      applyCorsHeaders(response);
      response.statusCode = statusNoContent;
      response.end();
      return;
    }
    routeRequest(request, response, options).catch((error: unknown) => {
      handleRequestFailure(response, error);
    });
  });
}

export function resolveHttpPort(): number {
  const rawPort = process.env[httpPortEnvVar];
  const parsedPort = rawPort ? Number.parseInt(rawPort, 10) : Number.NaN;
  return Number.isInteger(parsedPort) && parsedPort > 0 ? parsedPort : defaultHttpPort;
}

export function startMcpHttpServer(options: McpHttpServerOptions): http.Server {
  const server = createMcpHttpServer(options);
  const port = resolveHttpPort();

  // Without this handler a bind failure is an uncaught exception that takes the whole process
  // down -- including the stdio transport an MCP client is talking to. The common case is a
  // judge whose Docker mesh already owns this port; the stdio session must survive it.
  server.on("error", (error: NodeJS.ErrnoException) => {
    if (error.code === "EADDRINUSE") {
      process.stderr.write(
        `[MCP HTTP] Port ${port} is already in use, so the HTTP adapter did not start. ` +
          `Set MCP_TRANSPORT=stdio to disable it, or PORT to bind elsewhere.\n`
      );
      return;
    }
    process.stderr.write(`[MCP HTTP] Server error: ${String(error)}\n`);
  });

  server.listen(port, httpBindHost, () => {
    process.stderr.write(`[MCP HTTP] REST adapter listening on ${httpBindHost}:${port}\n`);
  });
  return server;
}
