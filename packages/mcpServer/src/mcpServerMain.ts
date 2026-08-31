import readline from "node:readline";
import {
  toolGetLiveSkuQuote,
  toolReserveInventoryLock,
  toolVerifyShippingSla,
  jsonRpcVersion,
  mcpServerName,
  mcpServerVersion,
  methodNotFoundErrorCode,
  invalidParamsErrorCode,
  internalErrorCode
} from "./constants/protocolConstants.js";
import type {
  JsonRpcRequest,
  JsonRpcResponse
} from "./types/mcpToolTypes.js";
import { executeSkuQuote } from "./tools/skuQuoter.js";
import { reserveInventoryLock } from "./tools/inventoryLocker.js";
import { verifyShippingSla } from "./tools/slaVerifier.js";
import { defaultCatalogStore } from "./catalog/catalogStore.js";
import { startMcpHttpServer } from "./http/httpAdapter.js";

export type { JsonRpcRequest, JsonRpcResponse };

export const mcpToolsManifest = [
  {
    name: toolGetLiveSkuQuote,
    description:
      "Calculates real-time unit pricing, volume discount tiers, and HSN-compliant GST for a requested SKU and volume.",
    inputSchema: {
      type: "object",
      required: ["sku_id", "quantity", "buyer_agent_id", "delivery_pincode"],
      properties: {
        sku_id: { type: "string", pattern: "^SKU-[A-Z0-9_-]{3,32}$" },
        quantity: { type: "integer", minimum: 1, maximum: 10000 },
        buyer_agent_id: { type: "string", pattern: "^did:agent:[a-z0-9_\\-\\.:]+$" },
        delivery_pincode: { type: "string", pattern: "^[1-9][0-9]{5}$" },
        promo_code: { type: "string" }
      }
    }
  },
  {
    name: toolReserveInventoryLock,
    description:
      "Atomically locks requested inventory stock in Redis with a 60-second TTL and returns a cryptographically signed lock token.",
    inputSchema: {
      type: "object",
      required: ["sku_id", "quantity", "lock_ttl_seconds", "buyer_agent_id", "quote_hash"],
      properties: {
        sku_id: { type: "string" },
        quantity: { type: "integer", minimum: 1 },
        lock_ttl_seconds: { type: "integer", minimum: 10, maximum: 120, default: 60 },
        buyer_agent_id: { type: "string" },
        quote_hash: { type: "string" }
      }
    }
  },
  {
    name: toolVerifyShippingSla,
    description:
      "Deterministically calculates courier routing zone, delivery SLA hours, and shipping cost.",
    inputSchema: {
      type: "object",
      required: ["origin_pincode", "delivery_pincode", "package_weight_grams", "required_delivery_tier"],
      properties: {
        origin_pincode: { type: "string", pattern: "^[1-9][0-9]{5}$" },
        delivery_pincode: { type: "string", pattern: "^[1-9][0-9]{5}$" },
        package_weight_grams: { type: "integer", minimum: 1 },
        required_delivery_tier: {
          type: "string",
          enum: ["standard", "express", "sameDay"]
        }
      }
    }
  }
];

export async function dispatchToolCall(
  toolName: string,
  toolArguments: unknown
): Promise<unknown> {
  if (toolName === toolGetLiveSkuQuote) {
    return executeSkuQuote(toolArguments, defaultCatalogStore);
  }
  if (toolName === toolReserveInventoryLock) {
    return await reserveInventoryLock(toolArguments, { catalogStore: defaultCatalogStore });
  }
  if (toolName === toolVerifyShippingSla) {
    return verifyShippingSla(toolArguments);
  }
  throw new Error(`Tool ${toolName} not recognized`);
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

function handleInitializeRequest(requestId: string | number | null): JsonRpcResponse {
  return {
    jsonrpc: jsonRpcVersion,
    id: requestId,
    result: {
      protocolVersion: "2024-11-05",
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
    const err = error as Error & { code?: string | number };
    const errorCode = err.code === "INSUFFICIENT_STOCK" ? 409 : internalErrorCode;
    return buildJsonRpcError(
      requestId,
      typeof errorCode === "number" ? errorCode : internalErrorCode,
      err.message,
      { exceptionCode: err.code }
    );
  }
}

export async function handleJsonRpcMessage(
  request: JsonRpcRequest
): Promise<JsonRpcResponse> {
  const requestId = request.id ?? null;

  if (request.method === "initialize") {
    return handleInitializeRequest(requestId);
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

export function initializeCatalogSubscriber(redisUrl?: string): void {
  const targetUrl = redisUrl ?? process.env.REDIS_URL;
  if (!targetUrl) {
    return;
  }
  import("ioredis")
    .then((ioredisModule) => {
      const RedisClass = ioredisModule.Redis ?? ioredisModule.default;
      const subscriber = new RedisClass(targetUrl, {
        retryStrategy: (times: number) => Math.min(times * 100, 2000),
        maxRetriesPerRequest: null,
        enableOfflineQueue: true,
        lazyConnect: false
      });
      subscriber.on("error", (error: unknown) => {
        const msg = String(error);
        if (!msg.includes("Connection in subscriber mode")) {
          process.stderr.write("Redis pub/sub subscriber error: " + msg + "\n");
        }
      });
      defaultCatalogStore.subscribeToCatalogChannel(subscriber);
    })
    .catch((error: unknown) => {
      process.stderr.write("Redis pub/sub subscriber error: " + String(error) + "\n");
    });
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
    try {
      const parsed = JSON.parse(trimmed) as JsonRpcRequest;
      const response = await handleJsonRpcMessage(parsed);
      process.stdout.write(`${JSON.stringify(response)}\n`);
    } catch (parseError: unknown) {
      const err = parseError as Error;
      process.stderr.write(`[MCP Error] Failed to process message: ${err.message}\n`);
    }
  });
}

// Both transports run together: stdio for MCP clients, HTTP for the buyer SDKs and the
// telemetry dashboard's protocol driver. They share `dispatchToolCall`, so a quote fetched
// over REST and one fetched over JSON-RPC execute identical pricing code.
export function startAllTransports(): void {
  initializeCatalogSubscriber();
  startMcpServer();
  startMcpHttpServer({
    jsonRpcHandler: (message: unknown) => handleJsonRpcMessage(message as JsonRpcRequest),
    toolsManifest: mcpToolsManifest
  });
}

if (process.argv[1] && (process.argv[1].endsWith("mcpServerMain.ts") || process.argv[1].endsWith("mcpServerMain.js"))) {
  startAllTransports();
}
