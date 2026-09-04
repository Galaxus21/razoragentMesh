// Where the merchant leg of a settlement is paid, and who gets to decide it.
//
// The payout account used to be a request field on two tools. execute_settlement's
// `merchant_account` beat the one bound at cart creation, and nothing compared either against
// anything the merchant had signed -- the Cart Mandate carries merchantDid but no account -- so
// any `acc_...` string a buyer agent invented became the Route destination for the merchant's
// share. It landed on the mock ledger only because RAZORPAY_ROUTE_LIVE is unset.
//
// These tests pin the replacement: the account is resolved from the merchant-signed merchantDid,
// a caller may only agree with that resolution, and a merchant the mesh cannot resolve does not
// settle at all. The last case tampers with the stored cart's merchantDid, because a guard that
// merely returned the demo constant would pass every other test here.

import { describe, it } from "node:test";
import assert from "node:assert/strict";
import type { Redis } from "ioredis";
import { establishAgentDelegation } from "../src/tools/delegationEstablisher.js";
import { createCartMandateForDelegation } from "../src/tools/cartMandateCreator.js";
import { signExecutionMandateForDelegation } from "../src/tools/executionMandateSigner.js";
import { executeSettlementForDelegation } from "../src/tools/settlementExecutor.js";
import { executeSkuQuote } from "../src/tools/skuQuoter.js";
import { signLockPayload } from "../src/crypto/lockSignatureGenerator.js";
import {
  loadDelegationSession,
  saveDelegationSession
} from "../src/session/delegationSessionStore.js";
import {
  meshMerchantDid,
  payoutSourceMeshMerchantKey,
  payoutSourceRegisteredProfile,
  resolveMerchantPayoutAccount
} from "../src/merchant/merchantPayoutRegistry.js";
import {
  custodyMeshDemoCustodial,
  defaultMerchantAccount,
  redisMerchantProfileKeyPrefix
} from "../src/constants/mandateToolConstants.js";
import { millisPerSecond } from "../src/constants/protocolConstants.js";

const testSkuId = "SKU-CHAIR-001";
const testQuantity = 2;
const testPincode = "560034";
const testStateCode = "29";
const budgetPaise = 10_000_000;
const attackerAccount = "acc_attackerControlled";
const secondMerchantDid = "did:razoragent:merchant:0123456789abcdef";
const secondMerchantAccount = "acc_secondMerchantLamps";

/** Only `get` is exercised, so the seam stays a map rather than a Redis double. */
function fakeRedis(entries: Record<string, string>): Redis {
  return {
    get: async (key: string): Promise<string | null> => entries[key] ?? null
  } as unknown as Redis;
}

async function establishCustodialDelegation(): Promise<string> {
  const delegation = await establishAgentDelegation({
    key_custody: custodyMeshDemoCustodial,
    max_budget_paise: budgetPaise,
    single_transaction_limit_paise: budgetPaise
  });
  return String(delegation.delegation_id);
}

/** Quote and lock exactly as an agent would, so the cart tool receives real mesh output. */
function buildCartRequest(delegationId: string, buyerAgentDid: string) {
  const quote = executeSkuQuote({
    sku_id: testSkuId,
    quantity: testQuantity,
    buyer_agent_id: buyerAgentDid,
    delivery_pincode: testPincode
  });
  const lockToken = `lock-payout-${Math.random().toString(36).slice(2)}`;
  const expiresAtUnixMs = Date.now() + 60 * millisPerSecond;
  const lockSignature = signLockPayload({
    lockToken,
    fencingToken: 1001,
    skuId: testSkuId,
    quantityLocked: testQuantity,
    expiresAtUnixMs
  });

  return {
    delegation_id: delegationId,
    sku_id: testSkuId,
    quantity: testQuantity,
    delivery_pincode: testPincode,
    delivery_state_code: testStateCode,
    quote_hash: quote.quote_hash,
    lock_token: lockToken,
    fencing_token: 1001,
    lock_expires_at_unix_ms: expiresAtUnixMs,
    lock_signature: lockSignature
  };
}

/** A delegation carried all the way to a signed execution mandate, ready to settle. */
async function buildSettleableDelegation(): Promise<{ delegationId: string; executionId: string }> {
  const delegationId = await establishCustodialDelegation();
  const session = await loadDelegationSession(delegationId);
  await createCartMandateForDelegation(
    buildCartRequest(delegationId, String(session?.buyerAgentDid))
  );
  const signed = await signExecutionMandateForDelegation({ delegation_id: delegationId });
  return { delegationId, executionId: String(signed.execution_id) };
}

/** Captures what reached the engine, and proves whether it was reached at all. */
async function withStubbedEngine<T>(
  body: () => Promise<T>
): Promise<{ result?: T; error?: Error; bodies: Record<string, unknown>[] }> {
  const bodies: Record<string, unknown>[] = [];
  const realFetch = globalThis.fetch;
  globalThis.fetch = (async (_url: string, init: { body: string }) => {
    bodies.push(JSON.parse(init.body) as Record<string, unknown>);
    return { ok: true, status: 200, text: async () => JSON.stringify({ status: "captured" }) };
  }) as unknown as typeof globalThis.fetch;

  try {
    return { result: await body(), bodies };
  } catch (error: unknown) {
    return { error: error as Error, bodies };
  } finally {
    globalThis.fetch = realFetch;
  }
}

describe("merchant payout resolution", () => {
  it("pays the mesh's own merchant identity at the demo account, derived from its signing key", async () => {
    const payout = await resolveMerchantPayoutAccount(meshMerchantDid());

    assert.equal(payout.razorpayAccountId, defaultMerchantAccount);
    assert.equal(payout.source, payoutSourceMeshMerchantKey);
    assert.equal(payout.merchantDid, meshMerchantDid());
  });

  it("reads a second merchant's account out of the profile the Merchant API registered", async () => {
    const client = fakeRedis({
      [`${redisMerchantProfileKeyPrefix}${secondMerchantDid}`]: JSON.stringify({
        merchantDid: secondMerchantDid,
        razorpayAccountId: secondMerchantAccount
      })
    });

    const payout = await resolveMerchantPayoutAccount(secondMerchantDid, { redisClient: client });

    assert.equal(payout.razorpayAccountId, secondMerchantAccount);
    assert.equal(payout.source, payoutSourceRegisteredProfile);
  });

  it("refuses a merchant it has no registered account for rather than inventing a destination", async () => {
    await assert.rejects(
      () => resolveMerchantPayoutAccount(secondMerchantDid, { redisClient: fakeRedis({}) }),
      /no Razorpay Route account is registered/
    );
  });

  it("refuses a profile whose account id is not a Route account id, rather than passing it on", async () => {
    const client = fakeRedis({
      [`${redisMerchantProfileKeyPrefix}${secondMerchantDid}`]: JSON.stringify({
        razorpayAccountId: "not-an-account"
      })
    });

    await assert.rejects(
      () => resolveMerchantPayoutAccount(secondMerchantDid, { redisClient: client }),
      /no Razorpay Route account is registered/
    );
  });
});

describe("create_cart_mandate payout binding", () => {
  it("refuses a merchant_account that is not where the signing merchant is paid", async () => {
    const delegationId = await establishCustodialDelegation();
    const session = await loadDelegationSession(delegationId);
    const request = {
      ...buildCartRequest(delegationId, String(session?.buyerAgentDid)),
      merchant_account: attackerAccount
    };

    await assert.rejects(
      () => createCartMandateForDelegation(request),
      /is not the payout account registered to the merchant that signed this cart/
    );

    // The refusal has to come before the merchant key signs: a cart naming a payout the mesh has
    // already decided to refuse must never exist, signed, anywhere.
    const after = await loadDelegationSession(delegationId);
    assert.equal(after?.cartMandate, undefined, "no cart may be signed for a redirected payout");
  });

  it("accepts the resolved account when a caller passes it back, so agreement is not a refusal", async () => {
    const delegationId = await establishCustodialDelegation();
    const session = await loadDelegationSession(delegationId);

    const cart = await createCartMandateForDelegation({
      ...buildCartRequest(delegationId, String(session?.buyerAgentDid)),
      merchant_account: defaultMerchantAccount
    });

    assert.equal(cart.price_reconciled, true);
    assert.equal(cart.merchant_did, meshMerchantDid());
  });
});

describe("execute_settlement payout binding", () => {
  it("refuses a redirected merchant_account without reaching the engine, so nothing is charged", async () => {
    const { delegationId, executionId } = await buildSettleableDelegation();

    const { error, bodies } = await withStubbedEngine(() =>
      executeSettlementForDelegation({
        delegation_id: delegationId,
        execution_id: executionId,
        merchant_account: attackerAccount
      })
    );

    assert.match(String(error?.message), /is not the payout account registered to the merchant/);
    assert.match(String(error?.message), /Nothing was charged/);
    assert.equal(bodies.length, 0, "a refused payout must never reach the settlement saga");
  });

  it("posts the account resolved from the signed cart when the caller omits the field", async () => {
    const { delegationId, executionId } = await buildSettleableDelegation();

    const { bodies } = await withStubbedEngine(() =>
      executeSettlementForDelegation({ delegation_id: delegationId, execution_id: executionId })
    );

    assert.equal(bodies.length, 1);
    assert.equal(bodies[0]?.merchantAccount, defaultMerchantAccount);
  });

  it("resolves from the cart's merchantDid, so an unresolvable merchant cannot settle", async () => {
    const { delegationId, executionId } = await buildSettleableDelegation();

    // Rewrite the merchantDid the settlement will resolve from. If the payout were still a
    // constant, or read from a session field, this would settle to the demo account regardless.
    const session = await loadDelegationSession(delegationId);
    assert.ok(session?.cartMandate);
    await saveDelegationSession({
      ...session,
      cartMandate: { ...session.cartMandate, merchantDid: secondMerchantDid }
    });

    const { error, bodies } = await withStubbedEngine(() =>
      executeSettlementForDelegation({ delegation_id: delegationId, execution_id: executionId })
    );

    assert.match(String(error?.message), /no Razorpay Route account is registered/);
    assert.match(String(error?.message), new RegExp(secondMerchantDid));
    assert.equal(bodies.length, 0);
  });
});
