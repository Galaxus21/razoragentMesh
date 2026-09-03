// The MCP tools manifest -- the exact JSON Schema an external agent sees from tools/list.
//
// Extracted from mcpServerMain.ts, which had grown past the project's 300-line file rule.
// This is pure data with no behaviour, so it belongs beside the other protocol constants.

import {
  toolEstablishAgentDelegation,
  toolGetLiveSkuQuote,
  toolReserveInventoryLock,
  toolSearchCatalog,
  toolVerifyShippingSla
} from "./protocolConstants.js";
import { mandateToolsManifest } from "./mandateToolsManifest.js";

// Pairing first, then discovery and pricing, then the rest of the purchase half. The order is
// what an agent reads top to bottom, and every clean buyer in the dress rehearsal took it as the
// call order -- so the previous discovery-first order actively misled them: in
// mesh_demo_custodial the buyer DID is minted by establish_agent_delegation, and an agent that
// quotes first has no buyer_agent_id to quote with and must back up and correct itself.
// Nothing downstream depends on position; the manifest test asserts membership and count only.
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
          description:
            "Plain-language description of the desired product. 'queryText' and 'query' are " +
            "accepted as aliases for this field."
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
      "Calculates real-time unit pricing, volume discount tiers, and HSN-compliant GST for a " +
      "requested SKU and volume. When the merchant has a sale SCHEDULED, the response carries " +
      "upcoming_promotions with the start time and the expected_savings_paise -- check it before " +
      "committing, because waiting may be the better advice for your buyer. The field lists " +
      "FUTURE sales only: a promotion running right now appears neither there nor in " +
      "offered_unit_price_paise, which reflects volume tiers, campaigns and promo codes only.",
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

// Selected by name rather than by position, so this does not silently depend on the order
// mandateToolsManifest happens to declare its four entries in.
const pairingToolManifest = mandateToolsManifest.filter(
  (tool) => tool.name === toolEstablishAgentDelegation
);
const purchaseToolsManifest = mandateToolsManifest.filter(
  (tool) => tool.name !== toolEstablishAgentDelegation
);

export const mcpToolsManifest = [
  ...pairingToolManifest,
  ...discoveryToolsManifest,
  ...purchaseToolsManifest
];
