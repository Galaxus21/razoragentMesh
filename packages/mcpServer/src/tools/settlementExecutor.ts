// execute_settlement -- submits the three-mandate bundle to the settlement saga.
//
// Deliberately POSTs to the engine directly rather than going through
// RazorAgentClient.executeSettlement. The SDK client re-runs verifyMandateChain locally first,
// so a locally-detectable violation would never reach the engine and would emit no server-side
// BUDGET_BLOCKED telemetry -- the dashboard would stay blank for exactly the refusal a judge is
// most interested in, and a demo narrating "the mesh refused" would really be narrating "the
// SDK refused". Sending every bundle means the engine decides, and says so on the SSE bus.
//
// The signature is verified locally first all the same, because a bad signature should read as
// a clear tool refusal rather than an opaque HTTP 400.

import { randomBytes } from "node:crypto";
import { AgentKeyManager, extractPublicKeyFromDid } from "@razorpay/agent-buyer-sdk";
import {
  custodyAgentHeld,
  defaultMerchantAccount,
  errorCustodyMismatch,
  errorExecutionIdMismatch,
  errorNoExecutionPayload,
  errorSignatureRequired,
  errorUnknownDelegation,
  paymentIdPrefix,
  paymentIdRandomBytes
} from "../constants/mandateToolConstants.js";
import { hexEncoding, millisPerSecond, utf8Encoding } from "../constants/protocolConstants.js";
import { resolveMandateEngineUrl } from "../constants/telemetryConstants.js";
import {
  executeSettlementRequestSchema,
  type ExecuteSettlementRequest
} from "../schemas/executeSettlementSchema.js";
import {
  discardSessionBuyerKey,
  loadDelegationSession,
  type DelegationSession,
  type SessionStoreOptions
} from "../session/delegationSessionStore.js";

const settlementExecutePath = "/api/v1/settlement/execute";

/**
 * Route transfer idempotency keys are `trf_{paymentId}_{account}_{purpose}` with no nonce and
 * no cart hash, so two settlements sharing a payment id collapse into one transfer at the
 * provider -- money the merchant never receives, behind a 200. Never reuse the driver fixture.
 */
function newPaymentId(): string {
  return `${paymentIdPrefix}${randomBytes(paymentIdRandomBytes).toString(hexEncoding)}`;
}

/**
 * Resolves the signature that will go on M_E, enforcing that the two custody modes cannot be
 * mixed into a chain whose signer is ambiguous.
 */
function resolveAgentSignature(
  session: DelegationSession,
  request: ExecuteSettlementRequest
): string {
  if (session.keyCustody === custodyAgentHeld) {
    if (!request.agent_signature) {
      throw new Error(errorSignatureRequired);
    }
    const canonicalBytes = new Uint8Array(
      Buffer.from(session.executionCanonicalJson ?? "", utf8Encoding)
    );
    const publicKeyHex = extractPublicKeyFromDid(session.buyerAgentDid);
    const verifier = AgentKeyManager.generate();
    if (!verifier.verifySignature(canonicalBytes, request.agent_signature, publicKeyHex)) {
      throw new Error("agent_signature does not verify against the bytes issued for this execution");
    }
    return request.agent_signature;
  }

  if (request.agent_signature) {
    throw new Error(errorCustodyMismatch);
  }
  const sessionSigner = AgentKeyManager.fromSecretKey(session.buyerSecretKeyHex ?? "");
  return sessionSigner.signPayload(session.unsignedExecutionPayload);
}

export async function executeSettlementForDelegation(
  rawRequest: unknown,
  options: SessionStoreOptions = {}
): Promise<Record<string, unknown>> {
  const request = executeSettlementRequestSchema.parse(rawRequest);
  const session = await loadDelegationSession(request.delegation_id, options);
  if (!session) {
    throw new Error(errorUnknownDelegation);
  }
  if (!session.unsignedExecutionPayload || !session.cartMandate) {
    throw new Error(errorNoExecutionPayload);
  }
  if (session.unsignedExecutionPayload.executionId !== request.execution_id) {
    throw new Error(errorExecutionIdMismatch);
  }

  // A second call replays the ORIGINAL signed bundle rather than signing a new one. That is
  // what makes the engine's nonce ledger the thing that refuses it -- the refusal is the
  // protocol working, and a judge can trigger it by simply asking the agent to buy twice.
  // Re-signing here would mint a fresh nonce and quietly settle the same cart again.
  const executionMandate =
    session.signedExecutionMandate ?? {
      ...session.unsignedExecutionPayload,
      agentSignature: resolveAgentSignature(session, request)
    };

  const result = await _postSettlement(session, executionMandate, request);
  // The custodial key's lifetime is the purchase, not the delegation's full validity.
  await discardSessionBuyerKey(session, executionMandate, options);
  return result;
}

async function _postSettlement(
  session: DelegationSession,
  executionMandate: Record<string, unknown>,
  request: ExecuteSettlementRequest
): Promise<Record<string, unknown>> {
  const body = {
    intentMandate: session.intentMandate,
    cartMandate: session.cartMandate,
    executionMandate,
    merchantAccount: request.merchant_account ?? session.merchantAccount ?? defaultMerchantAccount,
    paymentId: newPaymentId(),
    // Set server-side and never exposed as a tool input. serverTime overrides the clock for
    // mandate expiry, inventory-lock expiry AND the NTP drift window, so an agent that could
    // set it could settle an expired delegation.
    serverTime: Math.floor(Date.now() / millisPerSecond)
  };

  const response = await fetch(`${resolveMandateEngineUrl()}${settlementExecutePath}`, {
    method: "POST",
    headers: { "Content-Type": "application/json", Accept: "application/json" },
    body: JSON.stringify(body)
  });

  const text = await response.text();
  if (!response.ok) {
    // Thrown so dispatchToolCall's publishToolRefusal fires and the JSON-RPC layer returns
    // result.isError = true. A refusal is a tool result, not a transport fault.
    const failure = new Error(`Settlement refused: [HTTP ${response.status}] ${text}`) as Error & {
      code?: number;
    };
    failure.code = response.status;
    throw failure;
  }
  return JSON.parse(text) as Record<string, unknown>;
}
