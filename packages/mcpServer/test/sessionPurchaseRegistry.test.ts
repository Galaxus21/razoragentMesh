// Pins the same-session duplicate-purchase guard against the three shapes it has to tell apart.
//
// The cumulative budget ceiling is keyed on the Intent Mandate id and a new delegation mints a
// new buyer DID, so nothing below the MCP session can see that an agent re-paired and bought the
// same thing again. On 2026-09-03 B04_flash did exactly that and charged Rs 43,709.24 for one
// desk while reporting one payment.
//
// The guard must catch that WITHOUT catching two agents racing for the same last unit (two
// sessions) or one agent buying two different things (one session, two carts).

import assert from "node:assert/strict";
import test from "node:test";
import type { CartMandate } from "@razorpay/agent-buyer-sdk";
import {
  buildCartKey,
  clearSessionPurchases,
  findPriorPurchase,
  maxRememberedPurchasesPerSession,
  recordSettledPurchase
} from "../src/session/sessionPurchaseRegistry.js";

const deskSkuId = "SKU-TEST-DESK-MID";
const chairSkuId = "SKU-TEST-CHAIR-PROMO";
const deskUnitPricePaise = 1847850;
const deskTotalPaise = 2185462;
const chairUnitPricePaise = 929800;
const chairTotalPaise = 1102164;

// buildCartKey reads four fields; the rest of a signed CartMandate is irrelevant to identity.
function buildCart(skuId: string, quantity: number, unitPricePaise: number, totalPaise: number): CartMandate {
  return {
    items: [{ skuId, quantity, unitPricePaise }],
    totalPaise
  } as unknown as CartMandate;
}

const deskCart = buildCart(deskSkuId, 1, deskUnitPricePaise, deskTotalPaise);
const chairCart = buildCart(chairSkuId, 1, chairUnitPricePaise, chairTotalPaise);

test("the same cart bought twice in one session is recognised", () => {
  clearSessionPurchases();
  const sessionId = "mcp-session-b04";

  recordSettledPurchase(sessionId, buildCartKey(deskCart), "pay_mcp_5d1cd87ef22d");

  // A second delegation changes the delegation id, the buyer DID, the cart id and the nonce.
  // None of those are in the key, so the repeat is still visible.
  assert.equal(
    findPriorPurchase(sessionId, buildCartKey(deskCart)),
    "pay_mcp_5d1cd87ef22d",
    "a re-paired agent buying the same cart must be caught"
  );
});

test("two agents racing for the same unit are not confused for one repeat buyer", () => {
  clearSessionPurchases();
  recordSettledPurchase("mcp-session-flash", buildCartKey(deskCart), "pay_mcp_27afb169f791");

  assert.equal(
    findPriorPurchase("mcp-session-pro", buildCartKey(deskCart)),
    undefined,
    "a different shopper buying the same SKU is a legitimate second sale"
  );
});

test("a second, different purchase in one session is allowed", () => {
  clearSessionPurchases();
  const sessionId = "mcp-session-b19";
  recordSettledPurchase(sessionId, buildCartKey(deskCart), "pay_mcp_87f7382654de");

  assert.equal(
    findPriorPurchase(sessionId, buildCartKey(chairCart)),
    undefined,
    "buy the desk, then also buy the chair must still work"
  );
});

test("quantity is part of a purchase's identity", () => {
  clearSessionPurchases();
  const sessionId = "mcp-session-qty";
  recordSettledPurchase(sessionId, buildCartKey(deskCart), "pay_mcp_one");

  const twelveDesks = buildCart(deskSkuId, 12, deskUnitPricePaise, 23550956);
  assert.equal(findPriorPurchase(sessionId, buildCartKey(twelveDesks)), undefined);
});

test("the per-session memory is bounded", () => {
  clearSessionPurchases();
  const sessionId = "mcp-session-bounded";
  const overflow = maxRememberedPurchasesPerSession + 5;

  for (let index = 0; index < overflow; index += 1) {
    const cart = buildCart(`${deskSkuId}-${index}`, 1, deskUnitPricePaise, deskTotalPaise);
    recordSettledPurchase(sessionId, buildCartKey(cart), `pay_mcp_${index}`);
  }

  // The newest is remembered; the oldest has been evicted rather than growing without limit.
  const newest = buildCart(`${deskSkuId}-${overflow - 1}`, 1, deskUnitPricePaise, deskTotalPaise);
  const oldest = buildCart(`${deskSkuId}-0`, 1, deskUnitPricePaise, deskTotalPaise);
  assert.equal(findPriorPurchase(sessionId, buildCartKey(newest)), `pay_mcp_${overflow - 1}`);
  assert.equal(findPriorPurchase(sessionId, buildCartKey(oldest)), undefined);
});
