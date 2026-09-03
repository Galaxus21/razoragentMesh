// Pins the rest of F-04: a second delegation must not enlarge what the session may spend.
//
// `sessionPurchaseRegistry.test.ts` covers the duplicate-cart half -- the same cart, twice, in one
// session. This covers the general shape: `recordCumulativeSpend` keys on the Intent Mandate, so
// every `establish_agent_delegation` opens a fresh budget. B13_pro minted eight in a single run.
// Nothing in the protocol outlives a delegation, so the MCP session has to hold the ceiling.
//
// The invariant: the first budget a session declares is the most it can ever spend, and no later
// delegation raises it.

import assert from "node:assert/strict";
import { beforeEach, describe, it } from "node:test";
import {
  clearSessionPurchases,
  declareSessionCeiling,
  readSessionSpend,
  recordSessionSpend
} from "../src/session/sessionPurchaseRegistry.js";

const session = "mcp-session-budget-01";
const deskPaise = 2185462;
const declaredCeilingPaise = 2500000;

describe("the shopping session, not the delegation, holds the budget", () => {
  beforeEach(() => {
    clearSessionPurchases();
  });

  it("reports nothing for a session that never established a delegation", () => {
    assert.equal(readSessionSpend(session), undefined);
  });

  it("takes the first declared budget as the ceiling", () => {
    declareSessionCeiling(session, declaredCeilingPaise);

    const spend = readSessionSpend(session);
    assert.equal(spend?.ceilingPaise, declaredCeilingPaise);
    assert.equal(spend?.spentPaise, 0);
    assert.equal(spend?.remainingPaise, declaredCeilingPaise);
  });

  it("refuses to be raised by a later delegation", () => {
    declareSessionCeiling(session, declaredCeilingPaise);
    // The F-04 move: the agent wants more room, so it pairs again and asks for more.
    declareSessionCeiling(session, declaredCeilingPaise * 4);

    assert.equal(readSessionSpend(session)?.ceilingPaise, declaredCeilingPaise);
  });

  it("still lets a later delegation lower it", () => {
    declareSessionCeiling(session, declaredCeilingPaise);
    declareSessionCeiling(session, 900000);

    assert.equal(readSessionSpend(session)?.ceilingPaise, 900000);
  });

  it("accumulates spend across delegations rather than restarting it", () => {
    declareSessionCeiling(session, declaredCeilingPaise);
    recordSessionSpend(session, deskPaise);
    declareSessionCeiling(session, declaredCeilingPaise);

    const spend = readSessionSpend(session);
    assert.equal(spend?.spentPaise, deskPaise);
    assert.equal(spend?.remainingPaise, declaredCeilingPaise - deskPaise);
  });

  it("reports nothing remaining rather than a negative headroom", () => {
    declareSessionCeiling(session, deskPaise);
    recordSessionSpend(session, deskPaise);
    recordSessionSpend(session, deskPaise);

    assert.equal(readSessionSpend(session)?.remainingPaise, 0);
  });

  it("keeps sessions apart, so two shoppers racing are not one budget", () => {
    declareSessionCeiling(session, declaredCeilingPaise);
    declareSessionCeiling("mcp-session-budget-02", 500000);
    recordSessionSpend(session, deskPaise);

    assert.equal(readSessionSpend("mcp-session-budget-02")?.spentPaise, 0);
    assert.equal(readSessionSpend("mcp-session-budget-02")?.ceilingPaise, 500000);
  });
});
