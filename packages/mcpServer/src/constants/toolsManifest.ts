// The MCP tools manifest -- the exact JSON Schema an external agent sees from tools/list.
//
// Extracted from mcpServerMain.ts, which had grown past the project's 300-line file rule.
// This is pure data with no behaviour, so it belongs beside the other protocol constants.

import {
  toolBrowseCatalog,
  toolEstablishAgentDelegation,
  toolGetLiveSkuQuote,
  toolNegotiatePrice,
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
    name: toolBrowseCatalog,
    description:
      "Lists what the mesh actually sells, with optional category, brand, HSN and stock filters. " +
      "Use this when search_catalog returns nothing useful, or when you want to see the range " +
      "before choosing -- it enumerates the live catalog directly rather than ranking it, so a " +
      "product missing from the semantic index still appears here. Returns total_matching so you " +
      "can page with offset, and categories_available so you can widen a filter that matched " +
      "nothing. Prices are list prices: call get_live_sku_quote for a binding number.",
    inputSchema: {
      type: "object",
      properties: {
        category: { type: "string", minLength: 1, description: "Exact category, case-insensitive." },
        brand: { type: "string", minLength: 1, description: "Exact brand, case-insensitive." },
        hsn_code: { type: "string", minLength: 1 },
        min_stock: {
          type: "integer",
          minimum: 0,
          default: 1,
          description: "Defaults to 1, so only orderable stock is listed. Pass 0 to include out-of-stock."
        },
        limit: { type: "integer", minimum: 1, maximum: 100, default: 25 },
        offset: { type: "integer", minimum: 0, default: 0 }
      }
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
    name: toolNegotiatePrice,
    description:
      "Bargains for a lower unit price by running a full x402-INR alternating-offer negotiation " +
      "against the merchant gateway -- up to 5 turns, each gated by a proof-of-work solve and " +
      "charged ₹0.50 from a micro-escrow this tool opens and releases for you. Negotiation is " +
      "opt-in per merchant: many sell at a firm listed price and answer status DECLINED, which " +
      "costs nothing and means buy at list rather than retry. The merchant also sets the floor, " +
      "so a converged price is theirs to allow, not yours to name. Give it what you " +
      "want to open at and, in max_unit_price_paise, the most you will pay: the bid ladder never " +
      "crosses that ceiling, so a CONVERGED result is always affordable. Worth a call before " +
      "get_live_sku_quote on anything expensive; skip it on cheap items, where the turn fees can " +
      "exceed the saving (the response reports both, so you can tell). The agreed price is " +
      "recorded in the gateway's contract AST -- it is NOT applied to your quote automatically, " +
      "so get_live_sku_quote remains the only source of a bindable quote_hash.",
    inputSchema: {
      type: "object",
      required: ["sku_id", "quantity", "buyer_agent_id", "opening_bid_paise", "max_unit_price_paise"],
      properties: {
        sku_id: { type: "string", pattern: "^SKU-[A-Z0-9_-]{3,32}$" },
        quantity: { type: "integer", minimum: 1, maximum: 10000 },
        buyer_agent_id: { type: "string", pattern: "^did:agent:[a-z0-9_\\-\\.:]+$" },
        opening_bid_paise: {
          type: "integer",
          minimum: 1,
          description: "Your opening offer per unit. Below the list price, or there is nothing to negotiate."
        },
        max_unit_price_paise: {
          type: "integer",
          minimum: 1,
          description:
            "Your walk-away price per unit. A hard ceiling, not a target: no turn will bid above it."
        },
        merchant_did: { type: "string", minLength: 1 },
        max_turns: { type: "integer", minimum: 1, maximum: 5, default: 5 }
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
      "Deterministically calculates courier routing zone, delivery SLA hours, and shipping cost. " +
      "CHECK serviceable before building a cart: it is false when no courier serves the delivery " +
      "pincode, and when the tier you asked for is not offered to that zone. Both cases return " +
      "unserviceable_reason to relay to your buyer, and available_delivery_tiers so you can " +
      "re-request usefully. create_cart_mandate refuses an unserviceable address outright.",
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
