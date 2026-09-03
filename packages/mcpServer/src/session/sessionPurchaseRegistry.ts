// Remembers what an agent has already bought inside one MCP session.
//
// The budget ceiling is enforced per delegation: `recordCumulativeSpend` keys on the Intent
// Mandate's id, and `establish_agent_delegation` mints a fresh buyer DID every time. Two
// delegations from the same agent, in the same run, for the same person, are therefore
// uncorrelated -- so an agent that wants more budget simply asks for another one.
//
// That is not hypothetical. On 2026-09-03 a buyer told to "set my spending limit to exactly what
// it will cost and not a rupee more" bought the desk under a Rs 25,000 delegation, noticed the cap
// should have been exact, opened a second delegation sized to the paise, and bought the same desk
// again: Rs 43,709.24 charged for one desk, and its final answer mentioned one payment.
//
// The MCP session is the one identifier that survives a new delegation, so it is what this
// registry keys on. Scope matters: two agents racing for the same last unit are two sessions and
// are unaffected, and so is a second, different purchase in the same session.

import type { CartMandate } from "@razorpay/agent-buyer-sdk";

// Bounded so a long-lived session cannot grow this map without limit. A session that has made
// this many distinct purchases is well outside the demo's shape; the oldest entry is evicted.
export const maxRememberedPurchasesPerSession = 64;
const cartKeyFieldSeparator = ":";
const cartKeyLineSeparator = "|";

const settledPurchasesBySession = new Map<string, Map<string, string>>();

/**
 * Identifies a purchase by what was bought, not by who bought it.
 *
 * The buyer DID, delegation id, cart id and nonce all change between two attempts at the same
 * purchase, so none of them can spot a repeat. The line items and the total do not.
 */
export function buildCartKey(cartMandate: CartMandate): string {
  const lines = cartMandate.items
    .map((item) =>
      [item.skuId, item.quantity, item.unitPricePaise].join(cartKeyFieldSeparator)
    )
    .join(cartKeyLineSeparator);

  return [lines, cartMandate.totalPaise].join(cartKeyFieldSeparator);
}

/** Returns the payment id of an identical purchase already settled in this session, if any. */
export function findPriorPurchase(sessionId: string, cartKey: string): string | undefined {
  return settledPurchasesBySession.get(sessionId)?.get(cartKey);
}

export function recordSettledPurchase(
  sessionId: string,
  cartKey: string,
  paymentId: string
): void {
  let sessionPurchases = settledPurchasesBySession.get(sessionId);
  if (!sessionPurchases) {
    sessionPurchases = new Map<string, string>();
    settledPurchasesBySession.set(sessionId, sessionPurchases);
  }

  if (sessionPurchases.size >= maxRememberedPurchasesPerSession) {
    const oldestKey = sessionPurchases.keys().next().value;
    if (oldestKey !== undefined) {
      sessionPurchases.delete(oldestKey);
    }
  }
  sessionPurchases.set(cartKey, paymentId);
}

/**
 * The spending ceiling this session is held to, and what it has spent so far.
 *
 * The duplicate-purchase guard above catches an agent buying the SAME cart twice. It does not
 * catch the general shape of the same defect: `recordCumulativeSpend` keys on the Intent Mandate,
 * so every new delegation starts a fresh budget, and an agent that mints eight of them in one run
 * -- B13_pro did -- has eight budgets and no ceiling at all. Nothing in the protocol outlives a
 * delegation, so the MCP session has to be the principal.
 *
 * FIRST declared wins, and later delegations can only lower it. Taking the minimum instead breaks
 * a legitimate flow the matrix covers: "buy the desk, then also buy the chair" re-pairs with a
 * second delegation sized to the chair, which is not the user revising their budget down. Taking
 * the latest would restore the hole outright.
 */
const sessionCeilingPaise = new Map<string, number>();
const sessionSpentPaise = new Map<string, number>();

export function declareSessionCeiling(sessionId: string, maxBudgetPaise: number): void {
  const existing = sessionCeilingPaise.get(sessionId);
  if (existing === undefined) {
    sessionCeilingPaise.set(sessionId, maxBudgetPaise);
    return;
  }
  sessionCeilingPaise.set(sessionId, Math.min(existing, maxBudgetPaise));
}

export interface SessionSpendState {
  readonly ceilingPaise: number;
  readonly spentPaise: number;
  readonly remainingPaise: number;
}

/** Undefined when this session never established a delegation through the MCP surface. */
export function readSessionSpend(sessionId: string): SessionSpendState | undefined {
  const ceilingPaise = sessionCeilingPaise.get(sessionId);
  if (ceilingPaise === undefined) {
    return undefined;
  }
  const spentPaise = sessionSpentPaise.get(sessionId) ?? 0;
  return { ceilingPaise, spentPaise, remainingPaise: Math.max(0, ceilingPaise - spentPaise) };
}

export function recordSessionSpend(sessionId: string, paise: number): void {
  sessionSpentPaise.set(sessionId, (sessionSpentPaise.get(sessionId) ?? 0) + paise);
}

/** Test seam: the registry is process-global, so a test that records must be able to reset it. */
export function clearSessionPurchases(): void {
  settledPurchasesBySession.clear();
  sessionCeilingPaise.clear();
  sessionSpentPaise.clear();
}
