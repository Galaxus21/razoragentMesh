import { describe, it } from "node:test";
import assert from "node:assert/strict";
import { reserveInventoryLock } from "../src/inventoryLocker.js";
import { verifyLockSignature } from "../src/cryptoUtils.js";
import { CatalogStore } from "../src/catalogStore.js";
import { InsufficientStockException } from "../src/mcpTypes.js";

describe("InventoryLocker (Tool 2: reserve_inventory_lock)", () => {
  it("should successfully reserve an inventory lock and return signed token", async () => {
    const store = new CatalogStore();
    const lockResponse = await reserveInventoryLock(
      {
        sku_id: "SKU-CHAIR-001",
        quantity: 2,
        lock_ttl_seconds: 60,
        buyer_agent_id: "did:agent:procure-bot-01",
        quote_hash: "a".repeat(64)
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

    // Agent A and Agent B attempt to lock 1 unit in parallel
    const requestA = reserveInventoryLock(
      {
        sku_id: "SKU-LIMITED-001",
        quantity: 1,
        lock_ttl_seconds: 60,
        buyer_agent_id: "did:agent:buyer-a",
        quote_hash: "b".repeat(64)
      },
      { catalogStore: customStore }
    );

    const requestB = reserveInventoryLock(
      {
        sku_id: "SKU-LIMITED-001",
        quantity: 1,
        lock_ttl_seconds: 60,
        buyer_agent_id: "did:agent:buyer-b",
        quote_hash: "c".repeat(64)
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
