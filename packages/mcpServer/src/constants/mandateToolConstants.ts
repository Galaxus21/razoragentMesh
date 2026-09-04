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
/**
 * The Route account the mesh's OWN merchant identity is paid at -- the demo catalog's seller.
 *
 * No longer a default a caller can override: merchantPayoutRegistry.ts resolves the payout
 * destination from the merchant-signed cart, and this is the answer for every cart the mesh
 * signs itself.
 */
export const defaultMerchantAccount = "acc_demoMerchantChairs";
/**
 * Where a merchant registered through the Merchant API stores its profile. Must stay equal to
 * `redisMerchantProfileKeyPrefix` in merchantApi/src/constants/merchantConstants.py: this key is
 * the only way the mesh can learn the payout account of a merchant it did not sign for itself.
 */
export const redisMerchantProfileKeyPrefix = "mesh:merchant:profile:";
/** Razorpay Route linked account id. Mirrors razorpayAccountIdRegexPattern in merchantSchema.py. */
export const razorpayAccountIdRegex = /^acc_[a-zA-Z0-9_]+$/;
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

/**
 * A custodial delegation buys exactly once: execute_settlement discards the session buyer key so
 * its lifetime is the purchase rather than the delegation's full validity. Without this refusal a
 * second purchase reached the SDK's key guard and died on "Invalid secret key hex string", which
 * says nothing about the protocol rule being enforced.
 */
export const errorDelegationAlreadySettled =
  "this delegation has already been settled; call establish_agent_delegation again for another " +
  "purchase.";
/** Prefix for the cart-level refusal; verify_shipping_sla's own reason is appended to it. */
export const errorUnserviceableAddress =
  "this delivery address cannot be serviced, so no cart was signed.";

/**
 * Refuses a second settlement of an identical cart inside one MCP session.
 *
 * The cumulative budget cap is per delegation, and a new delegation is a new budget, so nothing
 * else stops an agent that re-pairs and buys the same thing again. The message names the earlier
 * payment so the agent can tell its user the purchase already happened, and names the flag that
 * lets a deliberate repeat through.
 */
/**
 * Raised before the bundle reaches the engine, so a refused purchase costs nothing.
 *
 * Names the session total rather than the delegation's, because the delegation's own budget will
 * look untouched -- that is the whole defect. Tells the agent the one thing that will actually
 * help: it cannot buy its way past this by opening another delegation.
 */
export const errorSessionBudgetExceeded = (
  ceilingPaise: number,
  spentPaise: number,
  attemptedPaise: number
): string =>
  `Cumulative budget exceeded for this shopping session: ${attemptedPaise} paise would take the ` +
  `total to ${spentPaise + attemptedPaise} paise against a ceiling of ${ceilingPaise} paise, ` +
  `already having spent ${spentPaise}. This ceiling is the FIRST max_budget_paise this session ` +
  "established and a further establish_agent_delegation cannot raise it -- a new delegation is " +
  "you re-pairing, not the buyer granting more money. Nothing was charged. Tell the buyer what " +
  "is left and ask before spending more.";

export const errorDuplicatePurchaseInSession = (paymentId: string): string =>
  `this exact cart was already settled in this session as ${paymentId}: ₹0 charged. The budget ` +
  "ceiling is per delegation, so a new delegation does not make this a new purchase. If the " +
  "buyer really wants a second one, call execute_settlement again with " +
  "allow_repeat_purchase: true.";

/**
 * Server-side warning, never an agent-facing refusal: by the time the reservation is consumed the
 * payment is captured, so a failure here costs one unit of stock, not the purchase.
 */
export const errorReservationConsumeFailed = (skuId: string, lockToken: string): string =>
  `settled reservation ${lockToken} on ${skuId} could not be consumed; the expiry sweeper may ` +
  "credit a sold unit back to stock.";

/**
 * Refuses a payout destination the caller chose rather than one the merchant signed for.
 *
 * Names the resolved account and the DID it came from, so this reads as "here is where this
 * merchant is paid" rather than "your argument was rejected" -- an agent that passed the field
 * out of habit can simply drop it and retry. Says nothing was charged, because the guard fires
 * before the bundle reaches the engine and an agent told only "refused" will assume otherwise.
 */
export const errorMerchantAccountNotBound = (
  requested: string,
  resolved: string,
  merchantDid: string
): string =>
  `merchant_account ${requested} is not the payout account registered to the merchant that ` +
  `signed this cart. The merchant leg pays ${resolved}, resolved from the signed cart's ` +
  `merchantDid ${merchantDid} -- a payout destination is never taken from the request, so this ` +
  "field cannot redirect funds. Omit it, or pass the registered account. Nothing was charged.";

/**
 * Fires when a cart names a merchant the mesh has no Route account for. Refusing is the whole
 * point: settling to an invented destination is the failure the resolution exists to prevent.
 */
export const errorMerchantPayoutUnregistered = (merchantDid: string): string =>
  `no Razorpay Route account is registered for merchantDid ${merchantDid}, so the merchant leg ` +
  "of this settlement has no destination. A merchant must be registered with the mesh " +
  "(POST /api/v1/merchant/register) before a cart it signed can settle. Nothing was charged.";

export const errorNoCartForDelegation = "No cart mandate has been created for this delegation";
export const errorNoExecutionPayload = "No execution payload has been issued for this delegation";
export const errorExecutionIdMismatch = "execution_id does not match the payload issued for this delegation";
