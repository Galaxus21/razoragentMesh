// sign_execution_mandate -- produces the Execution Mandate (M_E) that hash-binds M_I and M_C.
//
// This is where the custody decision made at pairing becomes visible and unavoidable:
//   agent_held          -> returns the exact bytes to sign, and NO signature.
//   mesh_demo_custodial -> signs with the mesh-held session key and returns a complete M_E.
//
// Nothing the caller sends influences what is signed. settlementAmountPaise is taken from the
// stored cart, upiCircleToken from the stored intent, and buyerAgentDid from the identity
// proven at pairing -- because createSignedExecutionMandate signs whatever integer it is
// handed and does not derive it from the cart. A caller-supplied amount would produce a
// perfectly valid, correctly hash-chained mandate that only validateBudgetGate would catch.

import {
  AgentKeyManager,
  buildUnsignedExecutionPayload,
  canonicalizeJsonString,
  computeSha256Digest,
  canonicalizeJson
} from "@razorpay/agent-buyer-sdk";
import {
  custodyAgentHeld,
  custodyDisclosureCustodial,
  errorNoCartForDelegation,
  errorUnknownDelegation,
  executionSigningWindowSeconds
} from "../constants/mandateToolConstants.js";
import {
  signExecutionMandateRequestSchema
} from "../schemas/signExecutionMandateSchema.js";
import {
  loadDelegationSession,
  saveDelegationSession,
  type SessionStoreOptions
} from "../session/delegationSessionStore.js";

const signingInstructions =
  "Compute a detached Ed25519 signature over the UTF-8 bytes of signing_payload_canonical_json " +
  "using the private key behind your DID, and pass the result as 128 lowercase hex characters " +
  "to execute_settlement as agent_signature. Do not re-canonicalise the payload yourself -- " +
  "sign the exact string returned here.";

export async function signExecutionMandateForDelegation(
  rawRequest: unknown,
  options: SessionStoreOptions = {}
): Promise<Record<string, unknown>> {
  const request = signExecutionMandateRequestSchema.parse(rawRequest);
  const session = await loadDelegationSession(request.delegation_id, options);
  if (!session) {
    throw new Error(errorUnknownDelegation);
  }
  if (!session.cartMandate) {
    throw new Error(errorNoCartForDelegation);
  }

  const unsignedPayload = buildUnsignedExecutionPayload(
    {
      intentMandate: session.intentMandate,
      cartMandate: session.cartMandate,
      settlementAmountPaise: session.cartMandate.totalPaise,
      upiCircleToken: session.intentMandate.upiCircleDelegationToken
    },
    session.buyerAgentDid
  );

  const canonicalJson = canonicalizeJsonString(unsignedPayload);
  await saveDelegationSession(
    { ...session, unsignedExecutionPayload: unsignedPayload, executionCanonicalJson: canonicalJson },
    options
  );

  const common = {
    execution_id: unsignedPayload.executionId,
    buyer_agent_did: unsignedPayload.buyerAgentDid,
    intent_mandate_hash: unsignedPayload.intentMandateHash,
    cart_mandate_hash: unsignedPayload.cartMandateHash,
    settlement_amount_paise: unsignedPayload.settlementAmountPaise,
    currency: unsignedPayload.currency,
    upi_circle_token: unsignedPayload.upiCircleToken,
    nonce: unsignedPayload.nonce,
    timestamp: unsignedPayload.timestamp,
    // The engine's NonceLedger accepts serverTime in [timestamp - 60, timestamp + 5]. A signing
    // round trip slower than that raises TimestampExpiredException at settlement, which reads as
    // an unrelated failure unless the agent was told to expect it.
    signing_window_seconds: executionSigningWindowSeconds,
    settle_before_timestamp: unsignedPayload.timestamp + executionSigningWindowSeconds
  };

  if (session.keyCustody === custodyAgentHeld) {
    return {
      ...common,
      unsigned_payload: unsignedPayload,
      signing_payload_canonical_json: canonicalJson,
      signing_digest_sha256: computeSha256Digest(canonicalizeJson(unsignedPayload)),
      agent_signature: null,
      signing_instructions: signingInstructions
    };
  }

  const sessionSigner = AgentKeyManager.fromSecretKey(session.buyerSecretKeyHex ?? "");
  const agentSignature = sessionSigner.signPayload(unsignedPayload);
  return {
    ...common,
    unsigned_payload: unsignedPayload,
    execution_mandate: { ...unsignedPayload, agentSignature },
    agent_signature: agentSignature,
    signed_by: "mesh_session_key",
    custody_disclosure: custodyDisclosureCustodial
  };
}
