// Covers the Merchant SKU Studio's negotiation opt-in.
//
// Negotiation is off for every merchant until a policy with `negotiationEnabled` reaches
// `mesh:merchant:policy:{did}`, and nothing in the dashboard could write that key -- so in
// practice no merchant had a policy, and the x402 gateway took the seller's price from the
// BUYER's request body instead. This panel is the merchant's side of that bargain.
//
// What these tests defend is the wire contract: NegotiationPolicy is extra="forbid" and frozen,
// so a payload carrying one extra key, or missing one required key, is a 422 the merchant sees
// only as an opaque save failure.

import { describe, it } from "node:test";
import assert from "node:assert/strict";

import {
  buildNegotiationPolicyPayload,
  convertInrTextToPaise,
  defaultNegotiationPolicyForm,
  gatewayMaxNegotiationTurns,
  maxMarginFloorBps,
  NegotiationPolicyFormData,
  policyPayloadToFormData,
  previewFloorPricePaise,
  validateNegotiationPolicy,
} from "../src/lib/negotiationPolicyValidator.js";

const testMerchantDid = "did:agent:merchant_policy_01";

function buildPolicy(
  overrides: Partial<NegotiationPolicyFormData> = {}
): NegotiationPolicyFormData {
  return {
    ...defaultNegotiationPolicyForm,
    merchantDid: testMerchantDid,
    negotiationEnabled: true,
    marginFloorBps: 1000,
    minimumOrderQuantity: 1,
    autoAcceptSpreadInr: "0",
    maxNegotiationTurns: gatewayMaxNegotiationTurns,
    ...overrides,
  };
}

describe("Merchant SKU Studio — negotiation is opt-in", () => {
  it("starts switched off, so opening the panel does not consent to anything", () => {
    assert.equal(defaultNegotiationPolicyForm.negotiationEnabled, false);
  });

  it("carries the switch through to the payload in both positions", () => {
    assert.equal(buildNegotiationPolicyPayload(buildPolicy()).negotiationEnabled, true);
    assert.equal(
      buildNegotiationPolicyPayload(buildPolicy({ negotiationEnabled: false }))
        .negotiationEnabled,
      false
    );
  });

  it("sends exactly the field set NegotiationPolicy declares", () => {
    // extra="forbid" on the backend model: one unexpected key is a 422, and a missing required
    // key is a different 422. Both reach the merchant as "save failed".
    const payload = buildNegotiationPolicyPayload(buildPolicy());
    assert.deepEqual(Object.keys(payload).sort(), [
      "autoAcceptSpreadPaise",
      "createdAtTimestamp",
      "marginFloorBps",
      "maxNegotiationTurns",
      "merchantDid",
      "minimumOrderQuantity",
      "negotiationEnabled",
      "updatedAtTimestamp",
    ]);
  });

  it("preserves an existing createdAtTimestamp so an edit is not read as a new policy", () => {
    const payload = buildNegotiationPolicyPayload(buildPolicy(), 1_788_400_000);
    assert.equal(payload.createdAtTimestamp, 1_788_400_000);
    assert.ok(payload.updatedAtTimestamp >= payload.createdAtTimestamp);
  });

  it("sends zero for createdAtTimestamp when new, which the route stamps for us", () => {
    // The route treats a non-positive value as "this is new", so the panel can save without
    // having to fetch first.
    assert.equal(buildNegotiationPolicyPayload(buildPolicy()).createdAtTimestamp, 0);
  });

  it("trims the DID, so a pasted space does not create a second merchant's policy", () => {
    const payload = buildNegotiationPolicyPayload(
      buildPolicy({ merchantDid: `  ${testMerchantDid}  ` })
    );
    assert.equal(payload.merchantDid, testMerchantDid);
  });
});

describe("Merchant SKU Studio — negotiation policy validation mirrors the backend", () => {
  it("accepts a well-formed policy", () => {
    const result = validateNegotiationPolicy(buildPolicy());
    assert.equal(result.isValid, true, JSON.stringify(result.errors));
  });

  it("requires a DID, because the policy is stored under it", () => {
    assert.ok(validateNegotiationPolicy(buildPolicy({ merchantDid: "   " })).errors.merchantDid);
    assert.ok(validateNegotiationPolicy(buildPolicy({ merchantDid: "merchant_1" })).errors.merchantDid);
  });

  it("holds the margin floor inside the model's basis-point bounds", () => {
    assert.ok(validateNegotiationPolicy(buildPolicy({ marginFloorBps: -1 })).errors.marginFloorBps);
    assert.ok(
      validateNegotiationPolicy(buildPolicy({ marginFloorBps: maxMarginFloorBps + 1 })).errors
        .marginFloorBps
    );
    assert.equal(
      validateNegotiationPolicy(buildPolicy({ marginFloorBps: maxMarginFloorBps })).isValid,
      true
    );
  });

  it("refuses a turn budget outside 1..10", () => {
    assert.ok(
      validateNegotiationPolicy(buildPolicy({ maxNegotiationTurns: 0 })).errors.maxNegotiationTurns
    );
    assert.ok(
      validateNegotiationPolicy(buildPolicy({ maxNegotiationTurns: 11 })).errors.maxNegotiationTurns
    );
    // 10 is legal for the model even though the gateway will only honour 5. Refusing it here
    // would contradict the backend; the panel says so in prose instead.
    assert.equal(validateNegotiationPolicy(buildPolicy({ maxNegotiationTurns: 10 })).isValid, true);
  });

  it("refuses a rupee amount that is blank, negative or unparseable", () => {
    for (const amount of ["", "-5", "abc", "1.234"]) {
      const result = validateNegotiationPolicy(buildPolicy({ autoAcceptSpreadInr: amount }));
      assert.equal(result.isValid, false, `"${amount}" should be refused`);
      assert.ok(result.errors.autoAcceptSpreadInr);
    }
  });

  it("requires a minimum order quantity of at least one", () => {
    assert.ok(
      validateNegotiationPolicy(buildPolicy({ minimumOrderQuantity: 0 })).errors
        .minimumOrderQuantity
    );
  });
});

describe("Merchant SKU Studio — the floor the merchant is shown is the one the gateway uses", () => {
  it("matches computeFloorPricePaise's integer arithmetic", () => {
    // x402Gateway/src/negotiation/merchantTerms.py: listPrice * (10000 - bps) // 10000. If the
    // panel rounded the other way it would promise a floor the gateway would undercut.
    assert.equal(previewFloorPricePaise(420_000, 1000), 378_000);
    assert.equal(previewFloorPricePaise(99_999, 1), 99_989);
    assert.equal(previewFloorPricePaise(420_000, 0), 420_000);
    assert.equal(previewFloorPricePaise(420_000, maxMarginFloorBps), 0);
  });

  it("reports zero rather than a negative floor for an unpriced SKU", () => {
    assert.equal(previewFloorPricePaise(0, 1000), 0);
  });

  it("clamps an out-of-range margin the same way the gateway does", () => {
    assert.equal(previewFloorPricePaise(420_000, 99_999), 0);
    assert.equal(previewFloorPricePaise(420_000, -5), 420_000);
  });
});

describe("Merchant SKU Studio — rupee/paise conversion", () => {
  it("converts to integer paise without floating drift", () => {
    assert.equal(convertInrTextToPaise("25.50"), 2550);
    assert.equal(convertInrTextToPaise("0"), 0);
    assert.equal(convertInrTextToPaise(" 1200 "), 120_000);
  });

  it("returns null for anything that is not a rupee amount", () => {
    for (const amount of ["", "abc", "-1", "1.999", "1,200"]) {
      assert.equal(convertInrTextToPaise(amount), null, `"${amount}" should not convert`);
    }
  });

  it("round-trips a saved policy back into the form", () => {
    const payload = buildNegotiationPolicyPayload(buildPolicy({ autoAcceptSpreadInr: "25.50" }));
    const restored = policyPayloadToFormData(payload);
    assert.equal(restored.autoAcceptSpreadInr, "25.50");
    assert.equal(restored.negotiationEnabled, true);
    assert.equal(restored.merchantDid, testMerchantDid);
  });
});
