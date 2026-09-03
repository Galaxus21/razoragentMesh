// Tests for the four mandate/settlement tools.
//
// The load-bearing cases here are the ones where a mistake would still LOOK like it worked: a
// cart signed over prices the agent supplied, an execution mandate signed for an amount the
// caller chose, a lock expiry in the wrong unit. Each of those produces a chain that verifies
// cleanly and is wrong, so they are asserted directly rather than through a happy path.

import { describe, it } from "node:test";
import assert from "node:assert/strict";
import { AgentKeyManager, canonicalizeJson, verifyMandateChain } from "@razorpay/agent-buyer-sdk";
import { establishAgentDelegation, buildPossessionProofPayload } from "../src/tools/delegationEstablisher.js";
import { createCartMandateForDelegation } from "../src/tools/cartMandateCreator.js";
import { signExecutionMandateForDelegation } from "../src/tools/executionMandateSigner.js";
import { executeSettlementForDelegation } from "../src/tools/settlementExecutor.js";
import { executeSkuQuote } from "../src/tools/skuQuoter.js";
import { defaultCatalogStore } from "../src/catalog/catalogStore.js";
import { signLockPayload } from "../src/crypto/lockSignatureGenerator.js";
import { millisPerSecond } from "../src/constants/protocolConstants.js";
import {
  custodyAgentHeld,
  custodyMeshDemoCustodial
} from "../src/constants/mandateToolConstants.js";

const testSkuId = "SKU-CHAIR-001";
const testQuantity = 2;
const testPincode = "560034";
const testStateCode = "29";
const budgetPaise = 10_000_000;

function nowSeconds(): number {
  return Math.floor(Date.now() / millisPerSecond);
}

/** A pairing request whose possession proof is genuinely signed by the DID it names. */
function buildProvenAgentRequest(signer: AgentKeyManager, timestampOverride?: number) {
  const request = {
    key_custody: custodyAgentHeld,
    buyer_agent_id: signer.getAgentDid(),
    proof_nonce: "nonce-under-test",
    proof_timestamp: timestampOverride ?? nowSeconds(),
    max_budget_paise: budgetPaise,
    single_transaction_limit_paise: budgetPaise,
    authorized_categories: [],
    validity_seconds: 86400
  };
  const proofSignature = signer.signPayload(
    buildPossessionProofPayload({ ...request, proof_signature: undefined } as never)
  );
  return { ...request, proof_signature: proofSignature };
}

async function establishCustodialDelegation(): Promise<Record<string, unknown>> {
  return establishAgentDelegation({
    key_custody: custodyMeshDemoCustodial,
    max_budget_paise: budgetPaise,
    single_transaction_limit_paise: budgetPaise
  });
}

/** Quote and lock exactly as an agent would, so the cart tool receives real mesh output. */
function buildCartRequest(delegationId: string, buyerAgentDid: string) {
  const quote = executeSkuQuote({
    sku_id: testSkuId,
    quantity: testQuantity,
    buyer_agent_id: buyerAgentDid,
    delivery_pincode: testPincode
  });
  const expiresAtUnixMs = Date.now() + 60 * millisPerSecond;
  const lockSignature = signLockPayload({
    lockToken: "lock-under-test",
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
    lock_token: "lock-under-test",
    fencing_token: 1001,
    lock_expires_at_unix_ms: expiresAtUnixMs,
    lock_signature: lockSignature
  };
}

describe("establish_agent_delegation", () => {
  it("returns the buyer private key in custodial mode, so the demo cannot pass as non-custodial", async () => {
    const result = await establishCustodialDelegation();
    assert.equal(result.key_custody, custodyMeshDemoCustodial);
    assert.equal(typeof result.buyer_private_key_hex, "string");
    assert.match(String(result.custody_disclosure), /CUSTODIAL/);
  });

  it("accepts a genuine possession proof and never returns a key for an agent-held delegation", async () => {
    const signer = AgentKeyManager.generate();
    const result = await establishAgentDelegation(buildProvenAgentRequest(signer));
    assert.equal(result.delegated_agent_did, signer.getAgentDid());
    assert.equal(result.buyer_private_key_hex, undefined);
    assert.match(String(result.custody_disclosure), /NON-CUSTODIAL/);
  });

  it("refuses a proof signed by a different key than the DID names", async () => {
    const claimed = AgentKeyManager.generate();
    const impostor = AgentKeyManager.generate();
    const request = buildProvenAgentRequest(claimed);
    const forged = impostor.signPayload(
      buildPossessionProofPayload({ ...request, proof_signature: undefined } as never)
    );
    await assert.rejects(
      () => establishAgentDelegation({ ...request, proof_signature: forged }),
      /does not verify/
    );
  });

  it("refuses a proof replayed from outside the drift window", async () => {
    const signer = AgentKeyManager.generate();
    const stale = buildProvenAgentRequest(signer, nowSeconds() - 600);
    await assert.rejects(() => establishAgentDelegation(stale), /drift window/);
  });

  it("clamps the per-transaction limit to the budget rather than deferring a 422 to settlement", async () => {
    const result = await establishAgentDelegation({
      key_custody: custodyMeshDemoCustodial,
      max_budget_paise: 500_000,
      single_transaction_limit_paise: 900_000
    });
    assert.equal(result.single_transaction_limit_paise, 500_000);
  });

  it("declares that authorized_categories is enforced at settlement", async () => {
    const result = await establishCustodialDelegation();
    assert.equal(result.category_enforcement, "enforced_at_settlement");
    // The note is what an agent reads to decide whether to trust the control, so it has to
    // name the mechanism rather than merely assert the outcome.
    assert.match(String(result.category_enforcement_note), /validateBudgetGate/);
  });
});

describe("create_cart_mandate", () => {
  it("emits inventoryLockExpiresAt in SECONDS so the settlement expiry guard can fire", async () => {
    const delegation = await establishCustodialDelegation();
    const request = buildCartRequest(
      String(delegation.delegation_id),
      String(delegation.delegated_agent_did)
    );
    const result = await createCartMandateForDelegation(request);

    const expectedSeconds = Math.floor(request.lock_expires_at_unix_ms / millisPerSecond);
    assert.equal(result.inventory_lock_expires_at, expectedSeconds);
    assert.equal(result.inventory_lock_expires_at_unit, "unix_seconds");
    // The guard compares against int(time.time()). A millisecond value here is ~1.79e12 and
    // would sit a thousand-fold in the future, making the comparison permanently false.
    assert.ok(Number(result.inventory_lock_expires_at) < Date.now());
  });

  it("signs the catalog's category onto every cart line", async () => {
    // establish_agent_delegation now discloses category_enforcement: "enforced_at_settlement",
    // and the enforcement only reaches validateBudgetGate if the category is actually inside
    // the merchant-signed cart. Without this the disclosure would be the second false claim
    // about authorized_categories in the same tool.
    const delegation = await establishCustodialDelegation();
    const request = buildCartRequest(
      String(delegation.delegation_id),
      String(delegation.delegated_agent_did)
    );
    const result = await createCartMandateForDelegation(request);

    const cart = result.cart_mandate as { items: ReadonlyArray<{ category?: string }> };
    const catalogSku = defaultCatalogStore.getSku(request.sku_id);
    assert.ok(catalogSku, `catalog fixture missing ${request.sku_id}`);
    for (const item of cart.items) {
      // The catalog's own value, not the sentinel and not anything the request supplied.
      assert.equal(item.category, catalogSku.category);
    }
  });

  it("refuses a quote hash the mesh did not produce for these parameters", async () => {
    const delegation = await establishCustodialDelegation();
    const request = buildCartRequest(
      String(delegation.delegation_id),
      String(delegation.delegated_agent_did)
    );
    await assert.rejects(
      () => createCartMandateForDelegation({ ...request, quote_hash: "a".repeat(64) }),
      /quote_hash does not match/
    );
  });

  it("refuses a lock signature this mesh did not mint", async () => {
    const delegation = await establishCustodialDelegation();
    const request = buildCartRequest(
      String(delegation.delegation_id),
      String(delegation.delegated_agent_did)
    );
    const foreign = signLockPayload(
      {
        lockToken: "lock-under-test",
        fencingToken: 1001,
        skuId: testSkuId,
        quantityLocked: testQuantity,
        expiresAtUnixMs: request.lock_expires_at_unix_ms
      },
      "00".repeat(32)
    );
    await assert.rejects(
      () => createCartMandateForDelegation({ ...request, lock_signature: foreign }),
      /not a signature this mesh produced/
    );
  });

  it("keeps discountPaise at zero, which the enclave's subtotal recomputation requires", async () => {
    const delegation = await establishCustodialDelegation();
    const result = await createCartMandateForDelegation(
      buildCartRequest(String(delegation.delegation_id), String(delegation.delegated_agent_did))
    );
    assert.equal(result.discount_paise, 0);
  });

  it("refuses an unknown delegation", async () => {
    await assert.rejects(
      () => createCartMandateForDelegation(buildCartRequest("dlg_missing", "did:agent:" + "0".repeat(64))),
      /Unknown or expired delegation_id/
    );
  });
});

describe("sign_execution_mandate", () => {
  it("returns exact bytes and no signature in agent-held mode", async () => {
    const signer = AgentKeyManager.generate();
    const delegation = await establishAgentDelegation(buildProvenAgentRequest(signer));
    const delegationId = String(delegation.delegation_id);
    await createCartMandateForDelegation(buildCartRequest(delegationId, signer.getAgentDid()));

    const result = await signExecutionMandateForDelegation({ delegation_id: delegationId });
    assert.equal(result.agent_signature, null);
    assert.equal(typeof result.signing_payload_canonical_json, "string");
    // The agent must be able to sign the returned string verbatim and have it verify.
    const signature = signer.signCanonicalBytes(
      new Uint8Array(Buffer.from(String(result.signing_payload_canonical_json), "utf-8"))
    );
    const verifier = AgentKeyManager.generate();
    assert.ok(
      verifier.verifySignature(
        canonicalizeJson(result.unsigned_payload),
        signature,
        signer.getPublicKeyHex()
      )
    );
  });

  it("produces a chain that verifies end to end in custodial mode", async () => {
    const delegation = await establishCustodialDelegation();
    const delegationId = String(delegation.delegation_id);
    const cart = await createCartMandateForDelegation(
      buildCartRequest(delegationId, String(delegation.delegated_agent_did))
    );
    const signed = await signExecutionMandateForDelegation({ delegation_id: delegationId });

    assert.equal(signed.signed_by, "mesh_session_key");
    assert.doesNotThrow(() =>
      verifyMandateChain(
        delegation.intent_mandate as never,
        cart.cart_mandate as never,
        signed.execution_mandate as never
      )
    );
  });

  it("takes the settlement amount from the stored cart, not from the caller", async () => {
    const delegation = await establishCustodialDelegation();
    const delegationId = String(delegation.delegation_id);
    const cart = await createCartMandateForDelegation(
      buildCartRequest(delegationId, String(delegation.delegated_agent_did))
    );
    const signed = await signExecutionMandateForDelegation({
      delegation_id: delegationId,
      settlement_amount_paise: 1
    } as never);
    assert.equal(signed.settlement_amount_paise, cart.total_paise);
  });

  it("refuses to sign before a cart exists", async () => {
    const delegation = await establishCustodialDelegation();
    await assert.rejects(
      () => signExecutionMandateForDelegation({ delegation_id: String(delegation.delegation_id) }),
      /No cart mandate/
    );
  });
});

describe("execute_settlement custody enforcement", () => {
  it("rejects a supplied signature in custodial mode, so the signer is never ambiguous", async () => {
    const delegation = await establishCustodialDelegation();
    const delegationId = String(delegation.delegation_id);
    await createCartMandateForDelegation(
      buildCartRequest(delegationId, String(delegation.delegated_agent_did))
    );
    const signed = await signExecutionMandateForDelegation({ delegation_id: delegationId });

    await assert.rejects(
      () =>
        executeSettlementForDelegation({
          delegation_id: delegationId,
          execution_id: signed.execution_id,
          agent_signature: "a".repeat(128)
        }),
      /only accepted when key_custody is agent_held/
    );
  });

  it("requires a signature in agent-held mode", async () => {
    const signer = AgentKeyManager.generate();
    const delegation = await establishAgentDelegation(buildProvenAgentRequest(signer));
    const delegationId = String(delegation.delegation_id);
    await createCartMandateForDelegation(buildCartRequest(delegationId, signer.getAgentDid()));
    const issued = await signExecutionMandateForDelegation({ delegation_id: delegationId });

    await assert.rejects(
      () =>
        executeSettlementForDelegation({
          delegation_id: delegationId,
          execution_id: issued.execution_id
        }),
      /agent_signature is required/
    );
  });

  it("replays the original signed bundle so the engine's nonce ledger is what refuses it", async () => {
    const delegation = await establishCustodialDelegation();
    const delegationId = String(delegation.delegation_id);
    await createCartMandateForDelegation(
      buildCartRequest(delegationId, String(delegation.delegated_agent_did))
    );
    const signed = await signExecutionMandateForDelegation({ delegation_id: delegationId });

    const sentNonces: string[] = [];
    const realFetch = globalThis.fetch;
    globalThis.fetch = (async (_url: string, init: { body: string }) => {
      const body = JSON.parse(init.body) as { executionMandate: { nonce: string } };
      sentNonces.push(body.executionMandate.nonce);
      return { ok: true, status: 200, text: async () => JSON.stringify({ status: "captured" }) };
    }) as unknown as typeof globalThis.fetch;

    try {
      const call = { delegation_id: delegationId, execution_id: signed.execution_id };
      await executeSettlementForDelegation(call);
      await executeSettlementForDelegation(call);
    } finally {
      globalThis.fetch = realFetch;
    }

    // Re-signing on the second call would mint a fresh nonce, and the same cart would settle
    // twice against a ledger that had no way to notice.
    assert.equal(sentNonces.length, 2);
    assert.equal(sentNonces[0], sentNonces[1]);
  });

  it("mints a distinct payment id per settlement, so Route transfers cannot collapse", async () => {
    const delegation = await establishCustodialDelegation();
    const delegationId = String(delegation.delegation_id);
    await createCartMandateForDelegation(
      buildCartRequest(delegationId, String(delegation.delegated_agent_did))
    );
    const signed = await signExecutionMandateForDelegation({ delegation_id: delegationId });

    const paymentIds: string[] = [];
    const realFetch = globalThis.fetch;
    globalThis.fetch = (async (_url: string, init: { body: string }) => {
      paymentIds.push((JSON.parse(init.body) as { paymentId: string }).paymentId);
      return { ok: true, status: 200, text: async () => JSON.stringify({ status: "captured" }) };
    }) as unknown as typeof globalThis.fetch;

    try {
      const call = { delegation_id: delegationId, execution_id: signed.execution_id };
      await executeSettlementForDelegation(call);
      await executeSettlementForDelegation(call);
    } finally {
      globalThis.fetch = realFetch;
    }

    assert.notEqual(paymentIds[0], paymentIds[1]);
    assert.ok(paymentIds.every((id) => id.startsWith("pay_mcp_")));
  });

  it("refuses an execution_id that does not match the payload it issued", async () => {
    const delegation = await establishCustodialDelegation();
    const delegationId = String(delegation.delegation_id);
    await createCartMandateForDelegation(
      buildCartRequest(delegationId, String(delegation.delegated_agent_did))
    );
    await signExecutionMandateForDelegation({ delegation_id: delegationId });

    await assert.rejects(
      () =>
        executeSettlementForDelegation({
          delegation_id: delegationId,
          execution_id: "mandate_exec_wrongwrongwrong"
        }),
      /does not match the payload/
    );
  });
});
