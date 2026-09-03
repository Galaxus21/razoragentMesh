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
      "nothing. Prices are list prices: call get_live_sku_quote for a binding number. Each item " +
      "also carries next_promotion when its merchant has a sale SCHEDULED, with the start time " +
      "and expected_savings_paise -- so you can find what is about to get cheaper without " +
      "quoting every SKU. Filter with has_upcoming_promotion to ask that question directly, and " +
      "advise your buyer to wait when the saving is worth the delay.",
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
        has_upcoming_promotion: {
          type: "boolean",
          description:
            "Omit to list everything. True lists only SKUs with a sale scheduled; false only " +
            "those without one, which is what to buy when waiting is not an option."
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
      "requested SKU and volume. A merchant sale that is RUNNING is already in " +
      "offered_unit_price_paise and is named in applied_discounts as SCHEDULED_PROMOTION. A sale " +
      "that has not started yet is in upcoming_promotions, with its start time and " +
      "expected_savings_paise. If upcoming_promotions is non-empty you MUST tell the buyer the " +
      "sale exists, what it would save and when it starts, even if you go on to recommend buying " +
      "now -- a buyer who later discovers you bought hours before a sale you saw and did not " +
      "mention has been badly served. Say it in your final answer, not only in your reasoning. " +
      "Which campaign, cashback and promo codes apply is set per SKU by its merchant, so a code " +
      "that discounts one SKU may do nothing on another -- applied_discounts names every one " +
      "that fired.",
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
      "exceed the saving (the response reports both, so you can tell). A converged price BINDS: " +
      "quote the same SKU with the same buyer_agent_id and quantity within 5 minutes and " +
      "get_live_sku_quote applies it as a NEGOTIATED line, so the cart and the settlement charge " +
      "it. Read savings_realised_paise, not savings_vs_list_paise, when you tell the buyer what " +
      "the bargaining saved: the first is measured against the discounts they would have got " +
      "anyway, and the second double-counts them.",
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
      "Atomically reserves stock against a LIVE QUOTE and returns the four values create_cart_mandate " +
      "needs: lock_token, fencing_token, expires_at_unix_ms, and signature. Call get_live_sku_quote " +
      "first and pass its quote_hash through unchanged -- a hash this mesh did not issue for this " +
      "exact SKU, quantity and buyer_agent_id is refused and NO stock is reserved, so a refusal " +
      "here costs you nothing and tells you what to fix. Note the two clocks: your lock lasts " +
      "lock_ttl_seconds, but the quote behind it dies 60 seconds after it was issued, and " +
      "create_cart_mandate needs both alive. Taking a lock longer than the quote does not extend " +
      "the quote -- go straight from quote to lock to cart, and re-quote if you detour.",
    inputSchema: {
      type: "object",
      required: ["sku_id", "quantity", "lock_ttl_seconds", "buyer_agent_id", "quote_hash"],
      properties: {
        sku_id: {
          type: "string",
          description: "Must match the SKU the quote_hash was issued for."
        },
        quantity: {
          type: "integer",
          minimum: 1,
          description:
            "Must match the quantity the quote_hash was issued for. Quote again to lock a different number."
        },
        lock_ttl_seconds: {
          type: "integer",
          minimum: 10,
          maximum: 120,
          default: 60,
          description:
            "How long the reservation is held. The 60s default already matches the quote's own " +
            "lifetime; a longer lock outlives the quote it was taken against and cannot be carted."
        },
        buyer_agent_id: {
          type: "string",
          description:
            "The same DID you quoted with. The quote is bound to it, so a lock for a different agent is refused."
        },
        quote_hash: {
          type: "string",
          description:
            "From get_live_sku_quote, unchanged. Verified against the quotes this mesh issued before any stock moves."
        }
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
