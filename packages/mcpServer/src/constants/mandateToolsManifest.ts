// Manifest entries for the four mandate/settlement tools.
//
// Split from toolsManifest.ts to keep both files inside the project's 300-line limit. The
// descriptions are load-bearing, not decoration: an external agent chooses key custody and
// reads the custodial disclosure from this text, and V-04 requires that documented behaviour
// be the behaviour. Anything claimed here must be true of the implementation.

import {
  toolCreateCartMandate,
  toolEstablishAgentDelegation,
  toolExecuteSettlement,
  toolSignExecutionMandate
} from "./protocolConstants.js";
import {
  custodyAgentHeld,
  custodyMeshDemoCustodial,
  defaultDelegationValiditySeconds,
  defaultMerchantAccount,
  defaultPackageWeightGrams,
  executionSigningWindowSeconds,
  mandateHashHexLength,
  maxDelegationValiditySeconds,
  minDelegationValiditySeconds,
  signatureHexLength,
  stateCodePattern,
  strictAgentDidPattern
} from "./mandateToolConstants.js";

export const mandateToolsManifest = [
  {
    name: toolEstablishAgentDelegation,
    description:
      "Pairs your agent with the mesh and issues a signed Intent Mandate delegating a bounded " +
      "spending authority to your DID. Call this first; the other three purchase tools take " +
      "the delegation_id it returns. key_custody has NO default and you must state it. " +
      `'${custodyAgentHeld}': you keep your Ed25519 private key, prove possession by signing ` +
      "the budget terms, and later sign the Execution Mandate yourself -- the mesh never holds " +
      `buyer authority. '${custodyMeshDemoCustodial}': the mesh mints and holds the buyer key ` +
      "and returns the private key to you, because a custodial demo that hands you the key " +
      "cannot be mistaken for a security boundary; in that mode the mesh can sign purchases " +
      "with no human approval and the budget ceiling does not bind the mesh. " +
      "authorized_categories IS enforced at settlement against the merchant-signed cart. " +
      `In ${custodyMeshDemoCustodial} a delegation authorises a SINGLE purchase: the mesh ` +
      "discards the session buyer key once that purchase settles, so its lifetime is the " +
      "purchase and not validity_seconds. Call this tool again for each further purchase -- " +
      "reusing a settled delegation is refused, whatever budget it has left.",
    inputSchema: {
      type: "object",
      required: ["key_custody", "max_budget_paise", "single_transaction_limit_paise"],
      properties: {
        key_custody: {
          type: "string",
          enum: [custodyAgentHeld, custodyMeshDemoCustodial],
          description: "No default. State which party holds the buyer signing key."
        },
        buyer_agent_id: {
          type: "string",
          pattern: strictAgentDidPattern,
          description: `Required for ${custodyAgentHeld}; omitted otherwise. did:agent: plus 64 lowercase hex.`
        },
        proof_signature: {
          type: "string",
          minLength: signatureHexLength,
          maxLength: signatureHexLength,
          description:
            `Required for ${custodyAgentHeld}. Detached Ed25519, 128 lowercase hex, over the ` +
            "RFC 8785 canonical JSON of {buyerAgentId, maxBudgetPaise, nonce, " +
            "singleTransactionLimitPaise, timestamp}."
        },
        proof_nonce: { type: "string", minLength: 1 },
        proof_timestamp: {
          type: "integer",
          minimum: 1,
          description: "Unix seconds. Accepted within -5s to +60s of mesh time."
        },
        max_budget_paise: { type: "integer", minimum: 1 },
        single_transaction_limit_paise: {
          type: "integer",
          minimum: 1,
          description: "Clamped to max_budget_paise if larger."
        },
        authorized_categories: {
          type: "array",
          items: { type: "string" },
          default: [],
          description:
            "Enforced at settlement against the category the merchant signed onto each cart " +
            "line; a line outside this list aborts with ₹0 charged. Use the merchant " +
            "catalog's spellings (matched case-insensitively). Empty means no restriction."
        },
        validity_seconds: {
          type: "integer",
          minimum: minDelegationValiditySeconds,
          maximum: maxDelegationValiditySeconds,
          default: defaultDelegationValiditySeconds
        }
      }
    }
  },
  {
    name: toolCreateCartMandate,
    description:
      "Produces a merchant-signed Cart Mandate from a live quote and a live inventory lock. " +
      "The mesh re-derives every price from its own pricing and shipping engines and compares " +
      "the result against your quote_hash, so the merchant signature attests only to numbers " +
      "the merchant produced. Call get_live_sku_quote and reserve_inventory_lock first and " +
      "pass their outputs through unchanged.",
    inputSchema: {
      type: "object",
      required: [
        "delegation_id",
        "sku_id",
        "quantity",
        "delivery_pincode",
        "delivery_state_code",
        "quote_hash",
        "lock_token",
        "fencing_token",
        "lock_expires_at_unix_ms",
        "lock_signature"
      ],
      properties: {
        delegation_id: { type: "string", minLength: 1 },
        sku_id: { type: "string", pattern: "^SKU-[A-Z0-9_-]{3,32}$" },
        quantity: { type: "integer", minimum: 1, maximum: 10000 },
        delivery_pincode: { type: "string", pattern: "^[1-9][0-9]{5}$" },
        delivery_state_code: {
          type: "string",
          pattern: stateCodePattern,
          description: "Two-digit GST state code. Decides intra- vs inter-state GST."
        },
        promo_code: { type: "string" },
        package_weight_grams: { type: "integer", minimum: 1, default: defaultPackageWeightGrams },
        quote_hash: { type: "string", minLength: 1, description: "From get_live_sku_quote." },
        quote_expiry_timestamp: {
          type: "integer",
          minimum: 1,
          description:
            "Optional but recommended: pass quote_expiry_timestamp back exactly as " +
            "get_live_sku_quote returned it. Supplying it lets the mesh tell an expired quote " +
            "apart from a genuine parameter mismatch and refuse with a timeout you can act on."
        },
        lock_token: { type: "string", minLength: 1, description: "From reserve_inventory_lock." },
        fencing_token: { type: "integer", minimum: 1, description: "From reserve_inventory_lock." },
        lock_expires_at_unix_ms: {
          type: "integer",
          minimum: 1,
          description: "Milliseconds, exactly as reserve_inventory_lock returned it."
        },
        lock_signature: {
          type: "string",
          minLength: 1,
          description:
            "From reserve_inventory_lock, where this value is returned under the key " +
            "'signature' -- not 'lock_signature'. Pass it through unchanged."
        },
        merchant_account: { type: "string", minLength: 1, default: defaultMerchantAccount }
      }
    }
  },
  {
    name: toolSignExecutionMandate,
    description:
      `Issues the Execution Mandate binding your Intent and Cart mandates together. In ` +
      `${custodyAgentHeld} mode it returns the exact RFC 8785 canonical JSON to sign and NO ` +
      `signature: sign those bytes with your key and pass 128 lowercase hex to ` +
      `execute_settlement. In ${custodyMeshDemoCustodial} mode the mesh signs with the session ` +
      `key it holds and returns a complete mandate. Settle within ` +
      `${executionSigningWindowSeconds} seconds -- the nonce ledger rejects a mandate signed ` +
      "outside that window. The settlement amount is taken from the stored cart and cannot be " +
      "supplied by the caller.",
    inputSchema: {
      type: "object",
      required: ["delegation_id"],
      properties: {
        delegation_id: { type: "string", minLength: 1 },
        cart_mandate_hash: {
          type: "string",
          minLength: mandateHashHexLength,
          maxLength: mandateHashHexLength,
          description: "Optional. Selects a cart when the delegation holds more than one."
        }
      }
    }
  },
  {
    name: toolExecuteSettlement,
    description:
      "Submits the three-mandate bundle to the settlement saga and returns the capture, the " +
      "Route split and the GSTR-1 invoice. A refusal -- replayed nonce, expired inventory " +
      "lock, budget exceeded, bad signature -- comes back as a tool result with isError set " +
      "and a machine-readable reason, NOT as a JSON-RPC error. A refusal means the protocol " +
      "worked; read the reason rather than retrying blindly.",
    inputSchema: {
      type: "object",
      required: ["delegation_id", "execution_id"],
      properties: {
        delegation_id: { type: "string", minLength: 1 },
        execution_id: { type: "string", minLength: 1 },
        agent_signature: {
          type: "string",
          minLength: signatureHexLength,
          maxLength: signatureHexLength,
          description:
            `Required in ${custodyAgentHeld} mode; rejected in ${custodyMeshDemoCustodial} mode.`
        },
        merchant_account: { type: "string", minLength: 1, default: defaultMerchantAccount }
      }
    }
  }
];
