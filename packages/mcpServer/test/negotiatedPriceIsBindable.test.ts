// Pins F-05: a converged negotiation must reach the bill, and must never overstate what it won.
//
// `priceNegotiator.test.ts` asserts the ladder -- concession steps, the clamp at the buyer's bid,
// convergence, escrow release. None of it asserted a PRICE, and none could: before this, a
// converged bargain changed nothing. Nine negotiations converged in the 2026-09-03 matrix, all
// nine paid the ordinary list-based quote, and one agent reported a 661.50 saving on a purchase
// that saved nothing.
//
// Two invariants here. A bargain the buyer struck is the price the buyer is charged. And the
// saving reported is measured against what the buyer would have paid anyway, so a merchant sale
// is never re-counted as something the bargaining achieved.

import assert from "node:assert/strict";
import { describe, it } from "node:test";
import { executeSkuQuote } from "../src/tools/skuQuoter.js";
import { defaultCatalogStore } from "../src/catalog/catalogStore.js";
import { defaultIssuedQuoteRegistry } from "../src/inventory/issuedQuoteRegistry.js";
import { AgreedPriceRegistry } from "../src/negotiation/agreedPriceRegistry.js";
import { buildNegotiationResponse } from "../src/negotiation/negotiationResponse.js";
import type { NegotiatePriceRequest } from "../src/schemas/negotiatePriceSchema.js";

const chairSku = "SKU-CHAIR-001";
const chairBasePaise = 420000;
// What the automatic stack offers this SKU at: the mesh's own Rs 20 festive campaign and
// Rs 1.50 cashback, the same figure skuQuoter.test.ts pins.
const chairAutomaticPaise = 417850;
const agreedPaise = 390000;
const buyerDid = "did:agent:bargain-hunter-01";

function quoteWith(registry: AgreedPriceRegistry, overrides: Record<string, unknown> = {}) {
  return executeSkuQuote(
    {
      sku_id: chairSku,
      quantity: 1,
      buyer_agent_id: buyerDid,
      delivery_pincode: "560001",
      ...overrides
    },
    defaultCatalogStore,
    undefined,
    defaultIssuedQuoteRegistry,
    registry
  );
}

function registryHolding(agreedUnitPricePaise: number, quantity = 1): AgreedPriceRegistry {
  const registry = new AgreedPriceRegistry();
  registry.record({
    skuId: chairSku,
    quantity,
    buyerAgentId: buyerDid,
    agreedUnitPricePaise,
    contractAstHash: "ast_test_hash"
  });
  return registry;
}

describe("a converged negotiation binds the price it agreed", () => {
  it("charges the agreed price and names it in applied_discounts", () => {
    const quote = quoteWith(registryHolding(agreedPaise));

    assert.equal(quote.offered_unit_price_paise, agreedPaise);
    assert.equal(quote.total_savings_paise, chairBasePaise - agreedPaise);
    const negotiated = quote.applied_discounts?.find((item) => item.type === "NEGOTIATED");
    assert.ok(negotiated, "the buyer must be able to see that bargaining set the price");
    assert.equal(negotiated.discountPaise, chairAutomaticPaise - agreedPaise);
  });

  it("is scoped to the agent that struck it", () => {
    const quote = quoteWith(registryHolding(agreedPaise), {
      buyer_agent_id: "did:agent:someone-else-02"
    });

    assert.equal(quote.offered_unit_price_paise, chairAutomaticPaise);
  });

  it("is scoped to the quantity it was struck for", () => {
    // Agreed for one; asking for three is a different purchase and gets the ordinary price.
    const quote = quoteWith(registryHolding(agreedPaise, 1), { quantity: 3 });

    assert.equal(quote.offered_unit_price_paise, chairAutomaticPaise);
  });

  it("never raises a price: an agreement worse than the automatic stack is ignored", () => {
    const quote = quoteWith(registryHolding(chairAutomaticPaise + 5000));

    assert.equal(quote.offered_unit_price_paise, chairAutomaticPaise);
    assert.equal(
      quote.applied_discounts?.some((item) => item.type === "NEGOTIATED"),
      false
    );
  });

  it("does not issue a quote that outlives the agreement pricing it", () => {
    const registry = new AgreedPriceRegistry();
    const agreement = registry.record({
      skuId: chairSku,
      quantity: 1,
      buyerAgentId: buyerDid,
      agreedUnitPricePaise: agreedPaise,
      contractAstHash: null
    });

    const quote = quoteWith(registry);

    // Otherwise the cart's re-quote returns to list, the hashes differ, and the agent is told
    // "quote mismatch" when its bargain has merely run out.
    assert.ok(quote.quote_expiry_timestamp <= agreement.agreementExpiresAt);
  });

  it("forgets an agreement once it has lapsed", () => {
    const registry = new AgreedPriceRegistry();
    const struckAt = 1788450000;
    registry.record(
      {
        skuId: chairSku,
        quantity: 1,
        buyerAgentId: buyerDid,
        agreedUnitPricePaise: agreedPaise,
        contractAstHash: null
      },
      struckAt
    );

    assert.ok(registry.lookup({ skuId: chairSku, quantity: 1, buyerAgentId: buyerDid }, struckAt));
    assert.equal(
      registry.lookup({ skuId: chairSku, quantity: 1, buyerAgentId: buyerDid }, struckAt + 301),
      undefined
    );
  });
});

describe("what a negotiation reports having saved", () => {
  const request = {
    sku_id: chairSku,
    quantity: 1,
    buyer_agent_id: buyerDid,
    opening_bid_paise: 350000,
    max_unit_price_paise: 400000,
    max_turns: 5
  } as NegotiatePriceRequest;

  const outcome = {
    turns: [],
    agreedUnitPricePaise: agreedPaise,
    contractAstHash: "ast_test_hash",
    cumulativeFeesPaise: 150,
    declinedReason: null
  };

  it("measures the saving against the automatic price, not the list price", () => {
    const response = buildNegotiationResponse({
      request,
      listUnitPricePaise: chairBasePaise,
      automaticUnitPricePaise: chairAutomaticPaise,
      outcome,
      refundedPaise: 4850,
      agreement: {
        skuId: chairSku,
        quantity: 1,
        buyerAgentId: buyerDid,
        agreedUnitPricePaise: agreedPaise,
        contractAstHash: "ast_test_hash",
        agreementExpiresAt: 1788450300
      }
    });

    assert.equal(response.agreed_price_is_bindable, true);
    // Against list it looks like 30000. The 2150 of automatic discount was never the bargain's
    // to claim, and reporting it as such is exactly what B20_flash did to its user.
    assert.equal(response.savings_vs_list_paise, chairBasePaise - agreedPaise);
    assert.equal(response.savings_realised_paise, chairAutomaticPaise - agreedPaise);
    assert.match(response.next_step, /BINDABLE/);
  });

  it("reports zero and says so when the automatic discounts already win", () => {
    const losingPaise = chairAutomaticPaise + 1000;
    const response = buildNegotiationResponse({
      request,
      listUnitPricePaise: chairBasePaise,
      automaticUnitPricePaise: chairAutomaticPaise,
      outcome: { ...outcome, agreedUnitPricePaise: losingPaise },
      refundedPaise: 4850,
      agreement: {
        skuId: chairSku,
        quantity: 1,
        buyerAgentId: buyerDid,
        agreedUnitPricePaise: losingPaise,
        contractAstHash: null,
        agreementExpiresAt: 1788450300
      }
    });

    assert.equal(response.agreed_price_is_bindable, false);
    assert.equal(response.savings_realised_paise, 0);
    assert.match(response.next_step, /it changes nothing/);
  });

  it("says so when a binding saving did not cover the turn fees", () => {
    const thinPaise = chairAutomaticPaise - 100;
    const response = buildNegotiationResponse({
      request,
      listUnitPricePaise: chairBasePaise,
      automaticUnitPricePaise: chairAutomaticPaise,
      outcome: { ...outcome, agreedUnitPricePaise: thinPaise, cumulativeFeesPaise: 250 },
      refundedPaise: 4750,
      agreement: {
        skuId: chairSku,
        quantity: 1,
        buyerAgentId: buyerDid,
        agreedUnitPricePaise: thinPaise,
        contractAstHash: null,
        agreementExpiresAt: 1788450300
      }
    });

    assert.equal(response.agreed_price_is_bindable, true);
    assert.equal(response.savings_realised_paise, 100);
    assert.match(response.next_step, /did not cover/);
  });

  it("binds nothing when the negotiation never converged", () => {
    const response = buildNegotiationResponse({
      request,
      listUnitPricePaise: chairBasePaise,
      automaticUnitPricePaise: chairAutomaticPaise,
      outcome: { ...outcome, agreedUnitPricePaise: null, contractAstHash: null },
      refundedPaise: 4850,
      agreement: undefined
    });

    assert.equal(response.status, "EXHAUSTED");
    assert.equal(response.agreed_price_is_bindable, false);
    assert.equal(response.savings_realised_paise, 0);
    assert.equal(response.savings_vs_list_paise, 0);
  });
});
