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
} from "./mcpConstants.js";
import { executeSkuQuote } from "./skuQuoter.js";
import { reserveInventoryLock } from "./inventoryLocker.js";
import { verifyShippingSla } from "./slaVerifier.js";
import { defaultCatalogStore } from "./catalogStore.js";

export interface JsonRpcRequest {
  readonly jsonrpc: string;
  readonly id?: string | number | null;
  readonly method: string;
  readonly params?: Record<string, unknown>;
}

export interface JsonRpcResponse {
  readonly jsonrpc: string;
  readonly id: string | number | null;
  readonly result?: unknown;
  readonly error?: {
    readonly code: number;
    readonly message: string;
    readonly data?: unknown;
  };
}

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
        delivery_pincode: { type: "string", pattern: "^[1-9][0-9]{5}$" }
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

export async function handleJsonRpcMessage(
  request: JsonRpcRequest
): Promise<JsonRpcResponse> {
  const requestId = request.id ?? null;

  if (request.method === "initialize") {
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

  if (request.method === "tools/list") {
    return {
      jsonrpc: jsonRpcVersion,
      id: requestId,
      result: { tools: mcpToolsManifest }
    };
  }

  if (request.method === "tools/call") {
    const params = request.params as { name?: string; arguments?: unknown } | undefined;
    const name = params?.name;
    const args = params?.arguments ?? {};

    if (!name) {
      return {
        jsonrpc: jsonRpcVersion,
        id: requestId,
        error: { code: invalidParamsErrorCode, message: "Missing tool name in params" }
      };
    }

    try {
      const output = await dispatchToolCall(name, args);
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
      return {
        jsonrpc: jsonRpcVersion,
        id: requestId,
        error: {
          code: typeof errorCode === "number" ? errorCode : internalErrorCode,
          message: err.message,
          data: { exceptionCode: err.code }
        }
      };
    }
  }

  return {
    jsonrpc: jsonRpcVersion,
    id: requestId,
    error: {
      code: methodNotFoundErrorCode,
      message: `Method ${request.method} not found`
    }
  };
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

if (process.argv[1] && process.argv[1].endsWith("mcpServerMain.ts")) {
  startMcpServer();
}
