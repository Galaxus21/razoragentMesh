// establish_agent_delegation -- the pairing step, and the only place key custody is chosen.
//
// Identity in this mesh is entirely key-derived: a DID *is* `did:agent:` + an Ed25519 public
// key, and every verifier recovers the key straight out of the mandate. There is no registry
// and no API-key concept to reuse, so pairing is a proof of key possession rather than an
// invented credential: the agent signs the budget terms it is asking for, and the mesh
// verifies that signature with the key inside the DID it claims.
//
// Signing the terms (rather than a bare challenge) is what stops the proof being lifted onto a
// different delegation, and costs no extra round trip.

import { randomBytes } from "node:crypto";
import {
  AgentKeyManager,
  canonicalizeJson,
  createSignedIntentMandate,
  extractPublicKeyFromDid
} from "@razorpay/agent-buyer-sdk";
import {
  categoryEnforcementDisclosure,
  categoryEnforcementNote,
  custodyAgentHeld,
  custodyDisclosureAgentHeld,
  custodyDisclosureCustodial,
  custodyMeshDemoCustodial,
  delegationIdPrefix,
  delegationIdRandomBytes,
  demoUpiCircleDelegationToken,
  errorProofInvalid,
  errorProofRequired,
  errorProofStale,
  proofMaxAgeSeconds,
  proofMaxSkewSeconds
} from "../constants/mandateToolConstants.js";
import { hexEncoding, millisPerSecond } from "../constants/protocolConstants.js";
import {
  establishDelegationRequestSchema,
  type EstablishDelegationRequest
} from "../schemas/establishDelegationSchema.js";
import {
  resolveSessionStoreBackend,
  saveDelegationSession,
  type SessionStoreOptions
} from "../session/delegationSessionStore.js";
import { declareSessionCeiling } from "../session/sessionPurchaseRegistry.js";

export interface DelegationOptions extends SessionStoreOptions {
  /** The MCP connection this call arrived on -- the principal a budget ceiling is scoped to. */
  readonly mcpSessionId?: string;
}

function nowSeconds(): number {
  return Math.floor(Date.now() / millisPerSecond);
}

function newDelegationId(): string {
  return `${delegationIdPrefix}${randomBytes(delegationIdRandomBytes).toString(hexEncoding)}`;
}

/**
 * The bytes an agent_held caller must sign. Includes the budget terms so a captured proof
 * cannot be replayed against a delegation with a different ceiling.
 */
export function buildPossessionProofPayload(request: EstablishDelegationRequest): {
  readonly buyerAgentId: string;
  readonly maxBudgetPaise: number;
  readonly nonce: string;
  readonly singleTransactionLimitPaise: number;
  readonly timestamp: number;
} {
  return {
    buyerAgentId: request.buyer_agent_id ?? "",
    maxBudgetPaise: request.max_budget_paise,
    nonce: request.proof_nonce ?? "",
    singleTransactionLimitPaise: request.single_transaction_limit_paise,
    timestamp: request.proof_timestamp ?? 0
  };
}

function verifyPossessionProof(request: EstablishDelegationRequest): string {
  const { buyer_agent_id: did, proof_signature: signature, proof_timestamp: timestamp } = request;
  if (!did || !signature || !request.proof_nonce || timestamp === undefined) {
    throw new Error(errorProofRequired);
  }

  const drift = nowSeconds() - timestamp;
  if (drift > proofMaxAgeSeconds || drift < -proofMaxSkewSeconds) {
    throw new Error(errorProofStale);
  }

  const publicKeyHex = extractPublicKeyFromDid(did);
  const canonicalBytes = canonicalizeJson(buildPossessionProofPayload(request));
  const verifier = AgentKeyManager.generate();
  if (!verifier.verifySignature(canonicalBytes, signature, publicKeyHex)) {
    throw new Error(errorProofInvalid);
  }
  return did;
}

/**
 * Resolves who the buyer is, and who holds the key that speaks for them.
 *
 * In custodial mode the mesh mints the keypair and hands the private key straight back: a
 * custodial demo that gives you the key cannot be mistaken for a security boundary.
 */
function resolveBuyerIdentity(request: EstablishDelegationRequest): {
  readonly buyerAgentDid: string;
  readonly buyerSecretKeyHex?: string;
} {
  if (request.key_custody === custodyAgentHeld) {
    return { buyerAgentDid: verifyPossessionProof(request) };
  }
  const sessionSigner = AgentKeyManager.generate();
  return {
    buyerAgentDid: sessionSigner.getAgentDid(),
    buyerSecretKeyHex: sessionSigner.getSecretKeyHex()
  };
}

export async function establishAgentDelegation(
  rawRequest: unknown,
  options: DelegationOptions = {}
): Promise<Record<string, unknown>> {
  const request = establishDelegationRequestSchema.parse(rawRequest);
  // The session, not the delegation, is the principal that holds a budget. Recorded here because
  // this is the only place a buyer's stated limit enters the mesh.
  if (options.mcpSessionId) {
    declareSessionCeiling(options.mcpSessionId, request.max_budget_paise);
  }
  const { buyerAgentDid, buyerSecretKeyHex } = resolveBuyerIdentity(request);

  // Clamped rather than rejected, matching buildIntentStep in the dashboard driver. Left
  // unclamped, a limit above the budget passes here and raises
  // SingleTransactionLimitExceededException at settlement, on a chain that looked valid.
  const singleTransactionLimitPaise = Math.min(
    request.single_transaction_limit_paise,
    request.max_budget_paise
  );
  const validUntilTimestamp = nowSeconds() + request.validity_seconds;

  // The demo principal. Held by the mesh, which is exactly what the custody disclosure says.
  const userSigner = AgentKeyManager.generate();
  const intentMandate = createSignedIntentMandate(
    {
      delegatedAgentDid: buyerAgentDid,
      maxBudgetPaise: request.max_budget_paise,
      singleTransactionLimitPaise,
      upiCircleDelegationToken: demoUpiCircleDelegationToken,
      authorizedCategories: request.authorized_categories,
      validUntilTimestamp
    },
    userSigner
  );

  const delegationId = newDelegationId();
  await saveDelegationSession(
    {
      delegationId,
      userDid: intentMandate.userDid,
      buyerAgentDid,
      keyCustody: request.key_custody,
      intentMandate,
      expiresAtUnixSeconds: validUntilTimestamp,
      ...(buyerSecretKeyHex ? { buyerSecretKeyHex } : {})
    },
    options
  );

  return _buildDelegationResponse({
    delegationId,
    request,
    intentMandate,
    buyerAgentDid,
    buyerSecretKeyHex,
    singleTransactionLimitPaise,
    validUntilTimestamp,
    sessionStore: await resolveSessionStoreBackend(options)
  });
}

interface DelegationResponseParams {
  readonly delegationId: string;
  readonly request: EstablishDelegationRequest;
  readonly intentMandate: ReturnType<typeof createSignedIntentMandate>;
  readonly buyerAgentDid: string;
  readonly buyerSecretKeyHex?: string;
  readonly singleTransactionLimitPaise: number;
  readonly validUntilTimestamp: number;
  readonly sessionStore: string;
}

function _buildDelegationResponse(params: DelegationResponseParams): Record<string, unknown> {
  const isCustodial = params.request.key_custody === custodyMeshDemoCustodial;
  return {
    delegation_id: params.delegationId,
    intent_mandate: params.intentMandate,
    user_did: params.intentMandate.userDid,
    delegated_agent_did: params.buyerAgentDid,
    valid_until_timestamp: params.validUntilTimestamp,
    max_budget_paise: params.request.max_budget_paise,
    single_transaction_limit_paise: params.singleTransactionLimitPaise,
    key_custody: params.request.key_custody,
    custody_disclosure: isCustodial ? custodyDisclosureCustodial : custodyDisclosureAgentHeld,
    // Returned on purpose in custodial mode: it is the plainest possible statement that the
    // mesh, not the agent, holds buyer authority here.
    ...(params.buyerSecretKeyHex ? { buyer_private_key_hex: params.buyerSecretKeyHex } : {}),
    category_enforcement: categoryEnforcementDisclosure,
    category_enforcement_note: categoryEnforcementNote,
    session_store: params.sessionStore
  };
}
