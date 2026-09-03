import { describe, it } from "node:test";
import assert from "node:assert/strict";
import { reserveInventoryLock } from "../src/tools/inventoryLocker.js";
import { executeSkuQuote } from "../src/tools/skuQuoter.js";
import { verifyLockSignature } from "../src/crypto/lockSignatureGenerator.js";
import { CatalogStore } from "../src/catalog/catalogStore.js";
import { IssuedQuoteRegistry } from "../src/inventory/issuedQuoteRegistry.js";
import { InsufficientStockException } from "../src/types/mcpToolTypes.js";

/**
 * A lock is only granted against a quote this mesh issued, so every lock test has to quote first
 * -- which is also the sequence a buyer agent must follow.
 */
function quoteHashFor(
  store: CatalogStore,
  skuId: string,
  quantity: number,
  buyerAgentId: string
): string {
  return executeSkuQuote(
    { sku_id: skuId, quantity, buyer_agent_id: buyerAgentId, delivery_pincode: "560001" },
    store
  ).quote_hash;
}

describe("InventoryLocker (Tool 2: reserve_inventory_lock)", () => {
  it("should successfully reserve an inventory lock and return signed token", async () => {
    const store = new CatalogStore();
    const lockResponse = await reserveInventoryLock(
      {
        sku_id: "SKU-CHAIR-001",
        quantity: 2,
        lock_ttl_seconds: 60,
        buyer_agent_id: "did:agent:procure-bot-01",
        quote_hash: quoteHashFor(store, "SKU-CHAIR-001", 2, "did:agent:procure-bot-01")
      },
      { catalogStore: store }
    );

    assert.ok(lockResponse.lock_token.length > 0);
    assert.ok(lockResponse.fencing_token > 0);
    assert.equal(lockResponse.sku_id, "SKU-CHAIR-001");
    assert.equal(lockResponse.quantity_locked, 2);
    assert.ok(lockResponse.expires_at_unix_ms > Date.now());

    const isSigValid = verifyLockSignature({
      lockToken: lockResponse.lock_token,
      fencingToken: lockResponse.fencing_token,
      skuId: lockResponse.sku_id,
      quantityLocked: lockResponse.quantity_locked,
      expiresAtUnixMs: lockResponse.expires_at_unix_ms
    }, lockResponse.signature);

    assert.equal(isSigValid, true);
  });

  it("should handle concurrency double-spend lock race on last remaining unit (TC-09)", async () => {
    const customStore = new CatalogStore([
      {
        skuId: "SKU-LIMITED-001",
        name: "Limited Edition Collector Item",
        category: "Collectibles",
        description: "Only 1 unit in stock",
        hsnCode: "94013000",
        gstRatePercent: 18,
        baseUnitPricePaise: 500000,
        availableStock: 1, // Exactly 1 unit
        volumeTiers: []
      }
    ]);

    // Both agents quote the last unit legitimately -- the race is over stock, not over the quote.
    const hashA = quoteHashFor(customStore, "SKU-LIMITED-001", 1, "did:agent:buyer-a");
    const hashB = quoteHashFor(customStore, "SKU-LIMITED-001", 1, "did:agent:buyer-b");

    // Agent A and Agent B attempt to lock 1 unit in parallel
    const requestA = reserveInventoryLock(
      {
        sku_id: "SKU-LIMITED-001",
        quantity: 1,
        lock_ttl_seconds: 60,
        buyer_agent_id: "did:agent:buyer-a",
        quote_hash: hashA
      },
      { catalogStore: customStore }
    );

    const requestB = reserveInventoryLock(
      {
        sku_id: "SKU-LIMITED-001",
        quantity: 1,
        lock_ttl_seconds: 60,
        buyer_agent_id: "did:agent:buyer-b",
        quote_hash: hashB
      },
      { catalogStore: customStore }
    );

    const results = await Promise.allSettled([requestA, requestB]);
    const fulfilled = results.filter((r) => r.status === "fulfilled");
    const rejected = results.filter((r) => r.status === "rejected");

    assert.equal(fulfilled.length, 1);
    assert.equal(rejected.length, 1);
    assert.equal(customStore.getStock("SKU-LIMITED-001"), 0);

    const rejectionReason = (rejected[0] as PromiseRejectedResult).reason;
    assert.ok(rejectionReason instanceof InsufficientStockException);
  });
});

// quote_hash was required and unchecked: it went straight into the lock signature as supplied, so
// any string bought a real lock and real stock, and the agent only discovered the problem two
// tools later at create_cart_mandate. The invariant these pin down is that a refusal costs the
// merchant nothing.
describe("a lock is only granted against a quote this mesh issued", () => {
  const buyer = "did:agent:quote-guard-buyer";

  it("refuses a fabricated quote_hash without taking any stock", async () => {
    const store = new CatalogStore();
    const stockBefore = store.getStock("SKU-CHAIR-001");

    await assert.rejects(
      () =>
        reserveInventoryLock(
          {
            sku_id: "SKU-CHAIR-001",
            quantity: 1,
            lock_ttl_seconds: 60,
            buyer_agent_id: buyer,
            quote_hash: "deadbeef".repeat(8)
          },
          { catalogStore: store }
        ),
      (err: unknown) => /not a quote this mesh issued/.test((err as Error).message)
    );

    // The half that matters. Before this guard the fabricated hash reserved a unit for 60s.
    assert.equal(store.getStock("SKU-CHAIR-001"), stockBefore, "a refused lock must take no stock");
  });

  it("refuses a real quote_hash presented for a different purchase", async () => {
    const store = new CatalogStore();
    const chairHash = quoteHashFor(store, "SKU-CHAIR-001", 1, buyer);
    const stockBefore = store.getStock("SKU-CHAIR-001");

    // Same hash, larger quantity: the quote priced one chair and cannot vouch for three.
    await assert.rejects(
      () =>
        reserveInventoryLock(
          {
            sku_id: "SKU-CHAIR-001",
            quantity: 3,
            lock_ttl_seconds: 60,
            buyer_agent_id: buyer,
            quote_hash: chairHash
          },
          { catalogStore: store }
        ),
      (err: unknown) => /issued for 1 x SKU-CHAIR-001/.test((err as Error).message)
    );

    // And it cannot be handed to another agent, which is what binds a quote to its buyer.
    await assert.rejects(
      () =>
        reserveInventoryLock(
          {
            sku_id: "SKU-CHAIR-001",
            quantity: 1,
            lock_ttl_seconds: 60,
            buyer_agent_id: "did:agent:someone-else",
            quote_hash: chairHash
          },
          { catalogStore: store }
        ),
      (err: unknown) => /bound to the exact purchase it priced/.test((err as Error).message)
    );

    assert.equal(store.getStock("SKU-CHAIR-001"), stockBefore);
  });

  it("says the quote expired rather than that the hash is unknown", async () => {
    // Distinct refusals for distinct mistakes: "quote again" is a different instruction from
    // "quote first", and an agent told the wrong one debugs the wrong thing.
    const store = new CatalogStore();
    const registry = new IssuedQuoteRegistry();
    const nowUnix = Math.floor(Date.now() / 1000);
    registry.record(
      {
        quoteHash: "f".repeat(64),
        skuId: "SKU-CHAIR-001",
        quantity: 1,
        buyerAgentId: buyer,
        quoteExpiryTimestamp: nowUnix - 30
      },
      nowUnix - 90
    );

    await assert.rejects(
      () =>
        reserveInventoryLock(
          {
            sku_id: "SKU-CHAIR-001",
            quantity: 1,
            lock_ttl_seconds: 60,
            buyer_agent_id: buyer,
            quote_hash: "f".repeat(64)
          },
          { catalogStore: store, quoteRegistry: registry }
        ),
      (err: unknown) => /quote expired 30s ago/.test((err as Error).message)
    );
  });

  it("forgets quotes that can no longer be used, so the registry cannot grow without bound", () => {
    const registry = new IssuedQuoteRegistry();
    const nowUnix = Math.floor(Date.now() / 1000);
    const lapsed = {
      quoteHash: "a".repeat(64), skuId: "SKU-CHAIR-001", quantity: 1,
      buyerAgentId: buyer, quoteExpiryTimestamp: nowUnix - 600
    };
    const live = {
      quoteHash: "b".repeat(64), skuId: "SKU-CHAIR-001", quantity: 1,
      buyerAgentId: buyer, quoteExpiryTimestamp: nowUnix + 60
    };

    registry.record(lapsed, nowUnix - 660);
    assert.equal(registry.size, 1);
    registry.record(live, nowUnix);
    assert.equal(registry.size, 1, "the lapsed quote is dropped on the next write");
    assert.equal(registry.verify({ ...live, quoteHash: live.quoteHash }, nowUnix).outcome, "issued");
    assert.equal(registry.verify({ ...lapsed, quoteHash: lapsed.quoteHash }, nowUnix).outcome, "unknown");
  });
});
