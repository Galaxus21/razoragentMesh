// The MCP tools manifest -- the exact JSON Schema an external agent sees from tools/list.
//
// Extracted from mcpServerMain.ts, which had grown past the project's 300-line file rule.
// This is pure data with no behaviour, so it belongs beside the other protocol constants.

import {
  toolGetLiveSkuQuote,
  toolReserveInventoryLock,
  toolSearchCatalog,
  toolVerifyShippingSla
} from "./protocolConstants.js";
import { mandateToolsManifest } from "./mandateToolsManifest.js";

// Discovery and pricing first, then the purchase half. The order is what an agent reads top to
// bottom, and it is the order the tools are meant to be called in.
const discoveryToolsManifest = [
  {
    name: toolSearchCatalog,
    description:
      "Finds catalog products matching a natural-language description, ranked by semantic " +
      "similarity. Use this first when the buyer describes what they want rather than naming " +
      "a SKU id. The response reports embedding_mode: when it is 'hash' the ranking is NOT " +
      "semantic and the order is not meaningful.",
    inputSchema: {
      type: "object",
      properties: {
        query_text: {
          type: "string",
          minLength: 1,
          maxLength: 500,
          description: "Plain-language description of the desired product."
        },
        limit: {
          type: "integer",
          minimum: 1,
          maximum: 25,
          default: 5,
          description: "Maximum number of ranked results to return."
        }
      },
      required: ["query_text"]
    }
  },

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

export const mcpToolsManifest = [...discoveryToolsManifest, ...mandateToolsManifest];
