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
      "spending authority to your DID. The other three purchase tools take the delegation_id " +
      "it returns -- but PRICE THE PURCHASE BEFORE YOU CALL THIS. get_live_sku_quote and " +
      "verify_shipping_sla both answer without any delegation, and the cart charges exactly " +
      "the shipping_cost_paise the SLA returned, so offered_unit_price_paise x quantity + " +
      "total_tax_paise + shipping_cost_paise is the all-in total. Set max_budget_paise from " +
      "that figure, not from a guess you mean to correct afterwards -- see the ceiling rule " +
      "below for why a correction upward will not be accepted. " +
      "key_custody has NO default and you must state it. " +
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
      "reusing a settled delegation is refused, whatever budget it has left. " +
      "Know what that means for the ceiling you are given: the FIRST max_budget_paise this " +
      "session declares becomes the session ceiling and binds every later delegation too. A " +
      "further establish_agent_delegation may LOWER that ceiling but can never raise it, " +
      "because re-pairing is you reconnecting and not your buyer granting more money. So a " +
      "provisional cap you intended to widen once you knew the price will hold you to the " +
      "provisional figure and the purchase will be refused with nothing charged. Across MCP " +
      "sessions there is no ceiling at all and YOU are the one tracking the buyer's total. " +
      "Before you re-pair to retry, check whether the purchase you are redoing already " +
      "settled. Settling the same cart twice in one session is refused; settling it " +
      "twice across sessions is not.",
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
        proof_nonce: {
          type: "string",
          minLength: 1,
          description:
            "Random single-use string you signed over. Replaying a nonce is refused."
        },
        proof_timestamp: {
          type: "integer",
          minimum: 1,
          description: "Unix seconds. Accepted within -5s to +60s of mesh time."
        },
        max_budget_paise: {
          type: "integer",
          minimum: 1,
          description:
            "Total you may spend under this delegation, in paise (integer: 50000 is Rs 500). " +
            "The budget gate is deterministic -- a cart one paise over is refused."
        },
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
          description:
            "How long this delegation stays usable, in seconds. Every later call is " +
            "refused once it lapses, so allow for negotiation turns and retries.",
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
      "pass their outputs through unchanged. The cart also fixes WHERE the merchant is paid: " +
      "the Route payout account is resolved from the merchant identity signing this cart, so " +
      "merchant_account is not a destination you can choose. Omit it.",
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
        delegation_id: {
          type: "string",
          minLength: 1,
          description: "From establish_agent_delegation. Required on every later call."
        },
        sku_id: {
          type: "string",
          pattern: "^SKU-[A-Z0-9_-]{3,32}$",
          description: "The SKU you quoted and locked. It must match both."
        },
        quantity: {
          type: "integer",
          minimum: 1,
          maximum: 10000,
          description:
            "Units to buy. Must equal the quantity you quoted, or the quote hash will not " +
            "verify."
        },
        delivery_pincode: {
          type: "string",
          pattern: "^[1-9][0-9]{5}$",
          description:
            "Destination PIN code. An address no courier serves is refused here outright."
        },
        delivery_state_code: {
          type: "string",
          pattern: stateCodePattern,
          description: "Two-digit GST state code. Decides intra- vs inter-state GST."
        },
        promo_code: {
          type: "string",
          description: "Optional. Must be the same code you quoted with, if any."
        },
        package_weight_grams: {
          type: "integer",
          minimum: 1,
          default: defaultPackageWeightGrams,
          description: "Billable weight in grams, the same one you checked the SLA with."
        },
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
        merchant_account: {
          type: "string",
          minLength: 1,
          description:
            "Do not send this. The Razorpay Route recipient for the merchant leg is resolved " +
            "from the merchant identity that signs the cart, so it is not yours to choose. It " +
            "is accepted only so that naming a different account is REFUSED with a reason " +
            "rather than silently ignored; the refusal names the account this merchant is " +
            "actually paid at, and nothing is charged."
        }
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
        delegation_id: {
          type: "string",
          minLength: 1,
          description: "From establish_agent_delegation."
        },
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
      "lock, budget exceeded, bad signature, a merchant_account that is not where the signing " +
      "merchant is paid -- comes back as a tool result with isError set and a machine-readable " +
      "reason, NOT as a JSON-RPC error. A refusal means the protocol worked; read the reason " +
      "rather than retrying blindly. The merchant leg of the split always pays the account " +
      "registered to the merchantDid on the signed cart; no field on this call can move it.",
    inputSchema: {
      type: "object",
      required: ["delegation_id", "execution_id"],
      properties: {
        delegation_id: {
          type: "string",
          minLength: 1,
          description: "From establish_agent_delegation."
        },
        execution_id: {
          type: "string",
          minLength: 1,
          description:
            "From sign_execution_mandate. Settlement is refused if the mandate it names has " +
            "expired, so sign and settle without a long gap."
        },
        agent_signature: {
          type: "string",
          minLength: signatureHexLength,
          maxLength: signatureHexLength,
          description:
            `Required in ${custodyAgentHeld} mode; rejected in ${custodyMeshDemoCustodial} mode.`
        },
        merchant_account: {
          type: "string",
          minLength: 1,
          description:
            "Do not send this. The Route recipient for the merchant leg is resolved from the " +
            "merchantDid on the SIGNED cart mandate, never from this request, so it cannot " +
            "redirect a payout. Sending a value that differs from the resolved account is " +
            "refused before anything is charged."
        }
      }
    }
  }
];
