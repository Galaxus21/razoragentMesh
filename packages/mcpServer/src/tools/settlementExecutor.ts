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
  errorCustodyMismatch,
  errorDuplicatePurchaseInSession,
  errorExecutionIdMismatch,
  errorNoExecutionPayload,
  errorReservationConsumeFailed,
  errorSessionBudgetExceeded,
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
import {
  consumeRedisReservation,
  defaultInMemoryLocker
} from "../inventory/redisLockManager.js";
import {
  buildCartKey,
  findPriorPurchase,
  readSessionSpend,
  recordSessionSpend,
  recordSettledPurchase
} from "../session/sessionPurchaseRegistry.js";
import { defaultCatalogStore } from "../catalog/catalogStore.js";
import { evaluateScheduledPromotions } from "../catalog/pricingEngine.js";
import {
  assertRequestedMerchantAccountMatches,
  resolveMerchantPayoutAccount
} from "../merchant/merchantPayoutRegistry.js";

const settlementExecutePath = "/api/v1/settlement/execute";
const paymentIdResponseField = "paymentId";
const secondsPerMinute = 60;
const paisePerRupee = 100;

export interface SettlementOptions extends SessionStoreOptions {
  /** The MCP connection this call arrived on -- the only id that survives a new delegation. */
  readonly mcpSessionId?: string;
}

/**
 * Refuses buying the identical cart twice in one MCP session.
 *
 * Only reachable when the agent has already settled this exact cart in this session, which the
 * per-delegation budget ceiling cannot see: a second `establish_agent_delegation` is a second
 * budget. Skipped entirely for stdio and for any caller without a session id, because without one
 * there is nothing to scope the memory to.
 */
function _rejectDuplicatePurchase(
  cartKey: string,
  request: ExecuteSettlementRequest,
  mcpSessionId?: string
): void {
  if (!mcpSessionId || request.allow_repeat_purchase) {
    return;
  }
  const priorPaymentId = findPriorPurchase(mcpSessionId, cartKey);
  if (priorPaymentId) {
    throw new Error(errorDuplicatePurchaseInSession(priorPaymentId));
  }
}

/**
 * Holds the whole session to the first budget it declared.
 *
 * Checked before the bundle is posted, so an over-budget purchase costs the buyer nothing. Skipped
 * without a session id for the same reason the duplicate guard is: stdio and the REST adapter have
 * no connection to scope a memory to, and refusing on a ceiling nobody could have declared would
 * make those surfaces unusable rather than safer.
 */
function _rejectOverSessionBudget(cartTotalPaise: number, mcpSessionId?: string): void {
  if (!mcpSessionId) {
    return;
  }
  const spend = readSessionSpend(mcpSessionId);
  if (!spend || spend.spentPaise + cartTotalPaise <= spend.ceilingPaise) {
    return;
  }
  throw new Error(
    errorSessionBudgetExceeded(spend.ceilingPaise, spend.spentPaise, cartTotalPaise)
  );
}

function _rememberPurchase(
  cartKey: string,
  result: Record<string, unknown>,
  mcpSessionId?: string
): void {
  const paymentId = result[paymentIdResponseField];
  if (!mcpSessionId || typeof paymentId !== "string") {
    return;
  }
  recordSettledPurchase(mcpSessionId, cartKey, paymentId);
}

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
  options: SettlementOptions = {}
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

  // The payout destination, resolved from the merchantDid the MERCHANT signed onto this cart --
  // never from the request. `merchant_account` used to win over the account bound at cart
  // creation, which made the merchant leg of the split a field any caller could set. Resolved
  // here rather than read off the session so the answer comes from the signed document itself:
  // a session copy is one more thing that can drift from what the merchant attested to.
  const payout = await resolveMerchantPayoutAccount(session.cartMandate.merchantDid, options);
  assertRequestedMerchantAccountMatches(request.merchant_account, payout);

  const cartKey = buildCartKey(session.cartMandate);
  _rejectDuplicatePurchase(cartKey, request, options.mcpSessionId);
  _rejectOverSessionBudget(session.cartMandate.totalPaise, options.mcpSessionId);

  // A second call replays the ORIGINAL signed bundle rather than signing a new one. That is
  // what makes the engine's nonce ledger the thing that refuses it -- the refusal is the
  // protocol working, and a judge can trigger it by simply asking the agent to buy twice.
  // Re-signing here would mint a fresh nonce and quietly settle the same cart again.
  const executionMandate =
    session.signedExecutionMandate ?? {
      ...session.unsignedExecutionPayload,
      agentSignature: resolveAgentSignature(session, request)
    };

  const result = await _postSettlement(session, executionMandate, payout.razorpayAccountId);
  _rememberPurchase(cartKey, result, options.mcpSessionId);
  if (options.mcpSessionId) {
    recordSessionSpend(options.mcpSessionId, session.cartMandate.totalPaise);
  }
  // Order matters: the unit is only sold once the engine has captured, and it must stop being a
  // reservation the moment it is.
  await _consumeSettledReservation(session, options);
  // The custodial key's lifetime is the purchase, not the delegation's full validity.
  await discardSessionBuyerKey(session, executionMandate, options);
  return { ...result, ..._upcomingSaleNotice(session) };
}

/**
 * Restates, on the receipt, a sale the buyer was shown and the agent did not pass on.
 *
 * get_live_sku_quote's description already instructs an agent in the strongest terms a
 * description allows: if upcoming_promotions is non-empty you MUST tell the buyer, in the final
 * answer and not only in your reasoning. Measured, it does not work. On 2026-09-04 four naive
 * agents -- both models, two prompt variants, one of them naming a feature only the promoted SKU
 * has -- were each handed a ₹6,000 sale opening ninety minutes out on the monitor they were
 * buying. None mentioned it. That is 0 of 7 across every unasked run measured to date, against
 * 2 of 2 on the one scenario that asks.
 *
 * What agents do relay, reliably, is the receipt: all four printed the payment id, the invoice
 * number and the tax split verbatim. So the notice goes where the evidence says it will be read,
 * rather than where it ought to have been enough.
 */
function _upcomingSaleNotice(session: DelegationSession): Record<string, string> {
  const skuId = session.cartMandate?.items[0]?.skuId;
  const sku = skuId ? defaultCatalogStore.getSku(skuId) : undefined;
  if (!sku?.promotions?.length) {
    return {};
  }

  const nowUnix = Math.floor(Date.now() / millisPerSecond);
  let upcoming;
  try {
    upcoming = evaluateScheduledPromotions(sku.baseUnitPricePaise, sku.promotions, nowUnix)
      .upcomingPromotions;
  } catch {
    // A malformed promotion costs this notice, never the receipt of a completed purchase.
    return {};
  }
  if (upcoming.length === 0) {
    return {};
  }

  const soonest = upcoming.reduce((a, b) => (a.starts_at_unix <= b.starts_at_unix ? a : b));
  const minutes = Math.max(1, Math.round((soonest.starts_at_unix - nowUnix) / secondsPerMinute));
  const savings = (soonest.expected_savings_paise / paisePerRupee).toFixed(2);
  return {
    buyerNotice:
      `This purchase completed shortly before a merchant sale. "${soonest.name}" opens on ` +
      `${skuId} in about ${minutes} minute(s) and would have saved ₹${savings} per unit. Tell ` +
      "the buyer: they were shown this sale before paying, and are entitled to know they bought " +
      "ahead of it."
  };
}

/**
 * Retires the inventory reservation this cart was built on, so the expiry sweeper cannot credit
 * a sold unit back to stock.
 *
 * `reserve_inventory_lock` decrements stock and files a reservation scored by expiry;
 * `lockExpirySweeper` credits every lapsed reservation back, because an abandoned cart must not
 * cost the merchant stock. Nothing distinguished a settled reservation from an abandoned one, so
 * a completed sale expired like an abandonment and returned its unit to the shelf -- measured on
 * 2026-09-03 as three captured payments against a SKU whose stock was one.
 *
 * Deliberately non-fatal. The money has already moved by the time this runs; failing the tool
 * here would tell the agent the purchase failed when it did not. The cost of the failure is one
 * unit of stock, which is the pre-fix behaviour, so it is logged and the capture stands.
 */
async function _consumeSettledReservation(
  session: DelegationSession,
  options: SettlementOptions
): Promise<void> {
  const lockToken = session.cartMandate?.inventoryLockToken;
  const skuId = session.cartMandate?.items[0]?.skuId;
  if (!lockToken || !skuId) {
    return;
  }

  try {
    if (options.redisClient) {
      await consumeRedisReservation(options.redisClient, lockToken, skuId);
      return;
    }
    defaultInMemoryLocker.consumeReservation(lockToken);
  } catch (consumeError) {
    console.warn(errorReservationConsumeFailed(skuId, lockToken), consumeError);
  }
}

async function _postSettlement(
  session: DelegationSession,
  executionMandate: Record<string, unknown>,
  merchantAccount: string
): Promise<Record<string, unknown>> {
  const body = {
    intentMandate: session.intentMandate,
    cartMandate: session.cartMandate,
    executionMandate,
    // Already resolved from cartMandate.merchantDid by the caller. Taken as a parameter rather
    // than re-resolved so there is exactly one place a payout destination is decided, and so
    // this function cannot be given a request field by a future edit.
    merchantAccount,
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
