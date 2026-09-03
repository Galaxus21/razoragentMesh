// Constants for the four mandate/settlement tools.
//
// Kept apart from protocolConstants.ts, which is about pricing, zones and JSON-RPC framing.
// Everything here concerns the AP2 mandate chain: who signs, for how long, and what the agent
// is told about key custody.

/** Custody has no default anywhere. An agent must state which model it is using. */
export const custodyAgentHeld = "agent_held" as const;
export const custodyMeshDemoCustodial = "mesh_demo_custodial" as const;
export const custodyModes = [custodyAgentHeld, custodyMeshDemoCustodial] as const;
export type KeyCustodyMode = (typeof custodyModes)[number];

// The mandate schemas pin DIDs to exactly `did:agent:` + 64 lowercase hex. The MCP manifest's
// quoting tools use a looser pattern; validating a delegation against that looser one lets an
// agent pair, quote, and burn an inventory lock before a Pydantic 422 at settlement.
export const strictAgentDidPattern = "^did:agent:[0-9a-f]{64}$";
export const strictAgentDidRegex = /^did:agent:[0-9a-f]{64}$/;
export const stateCodePattern = "^[0-9]{2}$";
export const stateCodeRegex = /^[0-9]{2}$/;
export const signatureHexLength = 128;
export const mandateHashHexLength = 64;

export const delegationIdPrefix = "dlg_";
export const delegationIdRandomBytes = 12;
export const paymentIdPrefix = "pay_mcp_";
export const paymentIdRandomBytes = 6;

// Matches the SDK's own ceiling (defaultIntentValiditySeconds). A session in custodial mode
// holds a live signing key for exactly this long, so it is also the session TTL.
export const maxDelegationValiditySeconds = 86400;
export const minDelegationValiditySeconds = 60;
export const defaultDelegationValiditySeconds = 86400;

// NonceLedger accepts serverTime in [timestamp - 60, timestamp + 5]. The possession proof
// reuses that shape so a captured proof cannot be replayed into a second delegation, and
// sign_execution_mandate reports the remaining window to the agent.
export const proofMaxAgeSeconds = 60;
export const proofMaxSkewSeconds = 5;
export const executionSigningWindowSeconds = 65;

export const defaultPackageWeightGrams = 750;
export const defaultMerchantAccount = "acc_demoMerchantChairs";
// Checksum-valid (Luhn Mod-36); the engine rejects a made-up GSTIN with HTTP 422.
// 29 = Karnataka, matching defaultOriginPincode.
export const demoMerchantGstin = "29AAACR5055K1Z3";
export const demoMerchantStateCode = "29";
export const demoUpiCircleDelegationToken = "upi_circle_del_tok_demo_0001";

// discountPaise is always zero and that is deliberate -- see the note carried on every cart.
export const cartDiscountPaise = 0;
export const cartDiscountRationale =
  "Always 0. The settlement enclave recomputes the subtotal from unitPricePaise x quantity and " +
  "then subtracts discountPaise. The line item already carries the post-discount unit price -- " +
  "which is also the price GST was levied on -- so reporting savings here would deduct them " +
  "twice and the enclave would reject the cart. Savings are reported on the quote instead.";

/**
 * Said in the tool output, not in a footnote. In custodial mode the mesh holds the buyer key
 * AND the demo principal key, so it can mint itself a delegation with any budget and settle
 * against it: every signature still verifies, and the budget ceiling bounds the agent rather
 * than the mesh. A demo that returns the private key cannot be mistaken for a security
 * boundary, which is why the pairing response does exactly that.
 */
export const custodyDisclosureAgentHeld =
  "NON-CUSTODIAL. The mesh holds no buyer key. You sign the Execution Mandate yourself with " +
  "the key behind your DID; sign_execution_mandate returns the exact bytes and no signature. " +
  "The mesh still holds the demo principal key that signed the Intent Mandate.";

export const custodyDisclosureCustodial =
  "CUSTODIAL -- DEMO ONLY. The mesh minted and holds the buyer private key returned in this " +
  "response, and can sign Execution Mandates for this delegation with no human approval. The " +
  "mesh also holds the principal key that signed the Intent Mandate, so the budget ceiling is " +
  "self-asserted by the mesh and is not a bound on the mesh. The signature chain is real; the " +
  "claim that a human authorised this spend is not.";

/**
 * authorized_categories is now a real control, so the disclosure says what it actually binds.
 * It was "advertised_only" for as long as `twoPhaseCommitSaga` called `validateBudgetGate`
 * without `skuCategories`, which left `_verifyCategoryAuthorization` unreachable.
 */
export const categoryEnforcementDisclosure = "enforced_at_settlement";
export const categoryEnforcementNote =
  "authorized_categories is enforced at settlement. The Merchant signs a category onto every " +
  "cart line, and verifyAndCapturePhase passes those categories to validateBudgetGate: a line " +
  "outside this list aborts the settlement with CategoryNotAuthorizedException and ₹0 charged. " +
  "Spellings come from the merchant catalog (for example 'IT Hardware'), compared " +
  "case-insensitively. An empty list places no category restriction on the delegation.";

/** Emitted at startup when the merchant key falls back to the literal committed in the repo. */
export const merchantKeyFallbackWarning =
  "[MCP Warning] MERCHANT_PRIVATE_KEY_HEX is unset; signing Cart Mandates with the development " +
  "key committed in protocolConstants.ts. Anyone with this repository can forge a Cart Mandate " +
  "against this deployment. Set MERCHANT_PRIVATE_KEY_HEX for anything beyond a local demo.\n";

/** Emitted at startup when the quote-signing HMAC key falls back to the committed literal. */
export const hmacKeyFallbackWarning =
  "[MCP Warning] HMAC_SECRET_KEY is unset; signing quotes with the development key committed " +
  "in protocolConstants.ts. Every peer that verifies a quote must share this value, so a mesh " +
  "where one service is configured and another is not will fail every verification.\n";

export const sessionStoreRedis = "redis" as const;
export const sessionStoreMemory = "memory" as const;

export const errorUnknownDelegation = "Unknown or expired delegation_id";
export const errorCustodyMismatch = "agent_signature is only accepted when key_custody is agent_held";
export const errorSignatureRequired = "agent_signature is required when key_custody is agent_held";
export const errorProofRequired =
  "buyer_agent_id and proof_signature are required when key_custody is agent_held";
export const errorProofInvalid =
  "proof_signature does not verify against the public key in buyer_agent_id";
export const errorProofStale = "proof_timestamp is outside the accepted drift window";
export const errorQuoteMismatch =
  "quote_hash does not match the quote this mesh recomputed for these parameters";

/**
 * Builds the expiry refusal. Distinct from errorQuoteMismatch on purpose: the parameters
 * reconciled exactly and only the clock moved, so telling the agent "hash mismatch" sends it
 * hunting for a hashing bug it does not have. Says how long ago the quote lapsed and what to
 * do next, because only err.message reaches the agent.
 */
export const errorQuoteExpired = (lapsedSecondsAgo: number, validitySeconds: number): string =>
  `quote expired ${lapsedSecondsAgo}s ago; quotes are valid for ${validitySeconds}s. ` +
  "The parameters reconciled exactly -- only the clock moved. Call get_live_sku_quote again " +
  "and retry create_cart_mandate with the fresh quote_hash.";
export const errorLockSignatureInvalid = "lock_signature is not a signature this mesh produced";
export const errorNoCartForDelegation = "No cart mandate has been created for this delegation";
export const errorNoExecutionPayload = "No execution payload has been issued for this delegation";
export const errorExecutionIdMismatch = "execution_id does not match the payload issued for this delegation";
