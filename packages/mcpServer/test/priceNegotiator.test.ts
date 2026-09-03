// Covers negotiate_price -- the buyer half of the x402-INR alternating-offer protocol.
//
// The gateway is stubbed rather than run: what these tests defend is the bidding strategy and the
// escrow lifecycle, both of which are this package's responsibility. The gateway's own rules
// (monotonicity, convergence, the micro-fee ledger) have their own suite under tests/.
//
// The property that matters most is the ceiling: max_unit_price_paise is the only promise this
// tool makes to a buyer, so a bid above it would be worse than a failed negotiation.

import assert from "node:assert/strict";
import test, { afterEach, beforeEach } from "node:test";
import { CatalogStore } from "../src/catalog/catalogStore.js";
import {
  concessionStepPaise,
  negotiatePrice,
  nextBuyerBidPaise,
  nextSellerAskPaise
} from "../src/tools/priceNegotiator.js";
import { minConcessionPaise } from "../src/constants/negotiationConstants.js";

const testSkuId = "SKU-NEGOTIATE-001";
const testBuyerDid = "did:agent:a1b2c3d4e5f60718293a4b5c6d7e8f90a1b2c3d4e5f60718293a4b5c6d7e8f90";
const listUnitPricePaise = 100_000;

function buildCatalogStore(): CatalogStore {
  return new CatalogStore([
    {
      skuId: testSkuId,
      name: "Negotiable Ergonomic Chair",
      category: "furniture",
      description: "Mesh-back task chair used to exercise the negotiation ladder.",
      hsnCode: "9401",
      gstRatePercent: 18,
      baseUnitPricePaise: listUnitPricePaise,
      availableStock: 25,
      volumeTiers: []
    }
  ]);
}

interface StubTurn {
  readonly buyerBidPaise: number;
  readonly sellerAskPaise: number;
  readonly turnNumber: number;
}

const originalFetch = globalThis.fetch;
let submittedTurns: StubTurn[] = [];
let releasedTokens: string[] = [];

/**
 * Stands in for the whole gateway. Convergence is evaluated with the gateway's own rule --
 * buyerBid >= sellerAsk (negotiation/convergenceChecker.py) -- so the ladder under test is
 * scored the same way the real service would score it.
 */
function installGatewayStub(
  options: { readonly failRelease?: boolean; readonly declineReason?: string } = {}
): void {
  submittedTurns = [];
  releasedTokens = [];
  let cumulativeFeesPaise = 0;

  globalThis.fetch = (async (url: string, init?: { body?: string; headers?: Record<string, string> }) => {
    const target = String(url);

    if (target.endsWith("/api/v1/mesh/challenge")) {
      // Difficulty 1, not the production 4: these tests exercise the loop, not the hash rate.
      return _jsonResponse(200, { challengeToken: `challenge-${submittedTurns.length}`, powDifficultyZeros: 1 });
    }
    if (target.endsWith("/api/v1/mesh/escrow/release")) {
      if (options.failRelease) {
        return _jsonResponse(404, { detail: "Escrow session not found" });
      }
      releasedTokens.push(init?.headers?.["X-Mesh-Escrow-Token"] ?? "");
      return _jsonResponse(200, { totalDebitedPaise: cumulativeFeesPaise, refundedBalancePaise: 5000 - cumulativeFeesPaise });
    }
    if (target.endsWith("/api/v1/mesh/escrow")) {
      // 201 Created, as the real route declares. A client that only accepts 200 breaks here.
      return _jsonResponse(201, { sessionToken: "esc_tok_test", remainingBalancePaise: 5000, initialHoldPaise: 5000 });
    }
    if (target.endsWith("/api/v1/mesh/negotiate")) {
      if (options.declineReason !== undefined) {
        // What the gateway answers for a merchant who has not opted in to negotiation.
        return _jsonResponse(403, { detail: options.declineReason });
      }
      const payload = JSON.parse(init?.body ?? "{}") as StubTurn;
      submittedTurns.push(payload);
      cumulativeFeesPaise += 50;
      const converged = payload.buyerBidPaise >= payload.sellerAskPaise;
      return _jsonResponse(200, {
        stepResult: {
          turnNumber: payload.turnNumber,
          buyerBidPaise: payload.buyerBidPaise,
          sellerAskPaise: payload.sellerAskPaise,
          spreadPaise: Math.max(0, payload.sellerAskPaise - payload.buyerBidPaise),
          isConverged: converged,
          cumulativeMicroFeesPaise: cumulativeFeesPaise
        },
        contractAstHash: converged ? "ast_hash_deadbeef" : null
      });
    }
    // Telemetry, which is fire-and-forget and irrelevant here.
    return _jsonResponse(202, {});
  }) as typeof globalThis.fetch;
}

function _jsonResponse(status: number, body: unknown): Response {
  return {
    ok: status >= 200 && status < 300,
    status,
    statusText: String(status),
    json: async () => body
  } as Response;
}

beforeEach(() => installGatewayStub());
afterEach(() => {
  globalThis.fetch = originalFetch;
});

test("a buyer with room to move converges below the list price", async () => {
  const result = await negotiatePrice(
    {
      sku_id: testSkuId,
      quantity: 2,
      buyer_agent_id: testBuyerDid,
      opening_bid_paise: 85_000,
      max_unit_price_paise: 95_000
    },
    buildCatalogStore()
  );

  assert.equal(result.status, "CONVERGED");
  assert.ok(result.agreed_unit_price_paise !== null);
  assert.ok(
    (result.agreed_unit_price_paise as number) < listUnitPricePaise,
    "a negotiation that agrees the list price saved the buyer nothing"
  );
  assert.ok(result.savings_vs_list_paise > 0);
  assert.equal(result.contract_ast_hash, "ast_hash_deadbeef");
});

test("no turn ever bids above max_unit_price_paise", async () => {
  const ceilingPaise = 90_000;
  const result = await negotiatePrice(
    {
      sku_id: testSkuId,
      quantity: 1,
      buyer_agent_id: testBuyerDid,
      opening_bid_paise: 60_000,
      max_unit_price_paise: ceilingPaise
    },
    buildCatalogStore()
  );

  // The tool's single promise to its caller. Checked on the wire rather than on the result, so a
  // bid that was sent and then merely not reported would still fail this.
  for (const turn of submittedTurns) {
    assert.ok(
      turn.buyerBidPaise <= ceilingPaise,
      `turn ${turn.turnNumber} bid ${turn.buyerBidPaise}, above the ${ceilingPaise} ceiling`
    );
  }
  if (result.agreed_unit_price_paise !== null) {
    assert.ok(result.agreed_unit_price_paise <= ceilingPaise);
  }
});

test("bids never fall and asks never rise, which is what the gateway enforces", async () => {
  await negotiatePrice(
    {
      sku_id: testSkuId,
      quantity: 1,
      buyer_agent_id: testBuyerDid,
      opening_bid_paise: 50_000,
      max_unit_price_paise: 70_000
    },
    buildCatalogStore()
  );

  // NonMonotonicConcessionViolation is a 400 from the gateway, so breaking this does not merely
  // negotiate badly -- it aborts the call mid-way with the escrow already charged.
  for (let index = 1; index < submittedTurns.length; index += 1) {
    assert.ok(submittedTurns[index].buyerBidPaise >= submittedTurns[index - 1].buyerBidPaise);
    assert.ok(submittedTurns[index].sellerAskPaise <= submittedTurns[index - 1].sellerAskPaise);
  }
});

test("a ceiling below the seller's floor exhausts the turn budget instead of overpaying", async () => {
  const result = await negotiatePrice(
    {
      sku_id: testSkuId,
      quantity: 1,
      buyer_agent_id: testBuyerDid,
      opening_bid_paise: 10_000,
      max_unit_price_paise: 12_000
    },
    buildCatalogStore()
  );

  assert.equal(result.status, "EXHAUSTED");
  assert.equal(result.agreed_unit_price_paise, null);
  assert.equal(result.savings_vs_list_paise, 0);
  assert.equal(result.contract_ast_hash, null);
  assert.match(result.next_step, /No agreement/);
});

test("an opening bid at the list price converges on turn one without burning fees", async () => {
  const result = await negotiatePrice(
    {
      sku_id: testSkuId,
      quantity: 1,
      buyer_agent_id: testBuyerDid,
      opening_bid_paise: listUnitPricePaise,
      max_unit_price_paise: listUnitPricePaise + 5_000
    },
    buildCatalogStore()
  );

  assert.equal(result.status, "CONVERGED");
  assert.equal(result.turns_used, 1);
  assert.equal(result.agreed_unit_price_paise, listUnitPricePaise);
  // Converged at list, so there is nothing to celebrate -- and the tool says so rather than
  // reporting a "successful" negotiation that cost ₹0.50 and achieved nothing.
  assert.match(result.next_step, /did not cover/);
});

test("the escrow hold is always released, so a negotiation cannot park the buyer's money", async () => {
  await negotiatePrice(
    {
      sku_id: testSkuId,
      quantity: 1,
      buyer_agent_id: testBuyerDid,
      opening_bid_paise: 85_000,
      max_unit_price_paise: 95_000
    },
    buildCatalogStore()
  );

  assert.deepEqual(releasedTokens, ["esc_tok_test"]);
});

test("a failed release still returns the negotiation rather than throwing it away", async () => {
  installGatewayStub({ failRelease: true });

  const result = await negotiatePrice(
    {
      sku_id: testSkuId,
      quantity: 1,
      buyer_agent_id: testBuyerDid,
      opening_bid_paise: 85_000,
      max_unit_price_paise: 95_000
    },
    buildCatalogStore()
  );

  assert.equal(result.status, "CONVERGED");
  assert.equal(result.escrow_refunded_paise, 0);
});

test("an unknown sku is refused before any escrow is opened", async () => {
  await assert.rejects(
    () =>
      negotiatePrice(
        {
          sku_id: "SKU-DOES-NOT-EXIST",
          quantity: 1,
          buyer_agent_id: testBuyerDid,
          opening_bid_paise: 1_000,
          max_unit_price_paise: 2_000
        },
        buildCatalogStore()
      ),
    /could not find that sku_id/
  );
  assert.equal(submittedTurns.length, 0, "a doomed request must not cost a micro-fee");
});

test("a ceiling below the opening bid is refused by the schema, before any fee", async () => {
  await assert.rejects(
    () =>
      negotiatePrice(
        {
          sku_id: testSkuId,
          quantity: 1,
          buyer_agent_id: testBuyerDid,
          opening_bid_paise: 90_000,
          max_unit_price_paise: 80_000
        },
        buildCatalogStore()
      ),
    /max_unit_price_paise/
  );
  assert.equal(submittedTurns.length, 0);
});

test("a concession is at least the gateway's documented minimum step", () => {
  // A proportional share of a nearly-closed spread rounds to nothing, which would stall the
  // ladder one paise short of agreement. The floor is what stops that.
  assert.equal(concessionStepPaise(10, 3000), minConcessionPaise);
  assert.equal(concessionStepPaise(0, 3000), 0);
  assert.ok(concessionStepPaise(100_000, 3000) > minConcessionPaise);
});

test("the seller never asks below the buyer's standing bid", () => {
  // Mirrors computeSellerCounterAsk in the gateway. Without the clamp a wide spread would let the
  // seller undercut an offer the buyer had already made.
  assert.equal(nextSellerAskPaise(50_000, 49_900), 49_900);
  assert.ok(nextSellerAskPaise(100_000, 50_000) < 100_000);
});

test("the buyer's bid stops exactly at the ceiling", () => {
  assert.equal(nextBuyerBidPaise(9_999, 10_000), 10_000);
  assert.equal(nextBuyerBidPaise(10_000, 10_000), 10_000);
});


test("a merchant who has not opted in is reported as DECLINED, not as a tool failure", async () => {
  // Negotiation is opt-in per merchant. Letting the gateway's 403 out as an exception would tell
  // an agent the mesh is broken, when the correct reading is "this seller's price is firm".
  const reason = "This merchant has not enabled negotiation. Their listed price is firm.";
  installGatewayStub({ declineReason: reason });

  const result = await negotiatePrice(
    {
      sku_id: testSkuId,
      quantity: 1,
      buyer_agent_id: testBuyerDid,
      opening_bid_paise: 85_000,
      max_unit_price_paise: 95_000
    },
    buildCatalogStore()
  );

  assert.equal(result.status, "DECLINED");
  assert.equal(result.declined_reason, reason);
  assert.equal(result.agreed_unit_price_paise, null);
  assert.equal(result.contract_ast_hash, null);
  assert.equal(result.turns_used, 0);
  // The refusal lands before any turn is held, so asking cost nothing.
  assert.equal(result.micro_fees_paid_paise, 0);
  assert.match(result.next_step, /get_live_sku_quote/);
  // The escrow this tool opened is still released -- a declined negotiation must not park money.
  assert.equal(releasedTokens.length, 1);
});

test("a declined negotiation says which merchant behaviour caused it", async () => {
  // "switched off" and "could not check" are different answers: one is final, the other is worth
  // retrying. Flattening them into a generic refusal is what makes an agent retry forever.
  const reason =
    "Negotiation is unavailable: this gateway cannot reach its policy store, so it cannot " +
    "confirm the merchant opted in.";
  installGatewayStub({ declineReason: reason });

  const result = await negotiatePrice(
    {
      sku_id: testSkuId,
      quantity: 1,
      buyer_agent_id: testBuyerDid,
      opening_bid_paise: 85_000,
      max_unit_price_paise: 95_000
    },
    buildCatalogStore()
  );

  assert.equal(result.status, "DECLINED");
  assert.match(result.declined_reason ?? "", /cannot reach its policy store/);
});

test("a gateway fault is still an error, so a real outage is not read as a firm price", async () => {
  installGatewayStub();
  const stubbedFetch = globalThis.fetch;
  globalThis.fetch = (async (url: string, init?: { body?: string; headers?: Record<string, string> }) => {
    if (String(url).endsWith("/api/v1/mesh/negotiate")) {
      return _jsonResponse(500, { detail: "internal error" });
    }
    return stubbedFetch(url as never, init as never);
  }) as typeof globalThis.fetch;

  await assert.rejects(
    negotiatePrice(
      {
        sku_id: testSkuId,
        quantity: 1,
        buyer_agent_id: testBuyerDid,
        opening_bid_paise: 85_000,
        max_unit_price_paise: 95_000
      },
      buildCatalogStore()
    ),
    /HTTP 500/
  );
});
