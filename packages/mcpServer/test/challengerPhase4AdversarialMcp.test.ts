import { describe, it } from "node:test";
import assert from "node:assert/strict";
import { reserveInventoryLock } from "../src/tools/inventoryLocker.js";
import { executeSkuQuote } from "../src/tools/skuQuoter.js";
import { CatalogStore } from "../src/catalog/catalogStore.js";
import { verifyLockSignature } from "../src/crypto/lockSignatureGenerator.js";
import {
  InsufficientStockException,
  SkuNotFoundException
} from "../src/types/mcpToolTypes.js";

/** A lock is only granted against a quote this mesh issued, so these tests quote first. */
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

function buildLimitedStressCatalog(): CatalogStore {
  return new CatalogStore([
    {
      skuId: "SKU-CHALLENGE-001",
      name: "High Demand Limited SKU",
      category: "Hardware",
      description: "Stress test item with exactly 3 units",
      hsnCode: "84713010",
      gstRatePercent: 18,
      baseUnitPricePaise: 2500000,
      availableStock: 3,
      volumeTiers: []
    }
  ]);
}

function verifyLockResponseSignatures(fulfilled: PromiseFulfilledResult<any>[]): void {
  const lockTokens = new Set<string>();
  for (const f of fulfilled) {
    const resp = f.value;
    assert.ok(resp.lock_token.length > 0);
    assert.ok(!lockTokens.has(resp.lock_token), "Lock tokens must be distinct");
    lockTokens.add(resp.lock_token);

    const sigOk = verifyLockSignature(
      {
        lockToken: resp.lock_token,
        fencingToken: resp.fencing_token,
        skuId: resp.sku_id,
        quantityLocked: resp.quantity_locked,
        expiresAtUnixMs: resp.expires_at_unix_ms
      },
      resp.signature
    );
    assert.equal(sigOk, true, "Signature must be cryptographically valid");
  }
}

describe("Challenger 1 — Phase 4 Adversarial Inventory Locker (mcpServer)", () => {
  describe("Inventory Locker Semantics & Concurrency", () => {
    it("should handle high-concurrency race condition (10 concurrent requests for 3 units)", async () => {
      const limitedCatalog = buildLimitedStressCatalog();
      // Every bot quotes legitimately first: the contention under test is over the last units of
      // stock, not over whether a quote_hash is real.
      const promises = Array.from({ length: 10 }, (_, index) =>
        reserveInventoryLock(
          {
            sku_id: "SKU-CHALLENGE-001",
            quantity: 1,
            lock_ttl_seconds: 30,
            buyer_agent_id: `did:agent:bot-${index}`,
            quote_hash: quoteHashFor(limitedCatalog, "SKU-CHALLENGE-001", 1, `did:agent:bot-${index}`)
          },
          { catalogStore: limitedCatalog }
        )
      );

      const results = await Promise.allSettled(promises);
      const fulfilled = results.filter((r) => r.status === "fulfilled") as PromiseFulfilledResult<any>[];
      const rejected = results.filter((r) => r.status === "rejected") as PromiseRejectedResult[];

      assert.equal(fulfilled.length, 3, "Exactly 3 reservations must succeed");
      assert.equal(rejected.length, 7, "Exactly 7 reservations must fail with stock exhaustion");
      assert.equal(limitedCatalog.getStock("SKU-CHALLENGE-001"), 0, "Remaining stock must be 0");

      verifyLockResponseSignatures(fulfilled);

      for (const r of rejected) {
        assert.ok(r.reason instanceof InsufficientStockException);
        assert.ok(r.reason.message.includes("SKU-CHALLENGE-001"));
      }
    });

    it("should reject unknown SKU with SkuNotFoundException", async () => {
      const store = new CatalogStore();
      await assert.rejects(
        async () =>
          reserveInventoryLock(
            {
              sku_id: "SKU-NON-EXISTENT-999",
              quantity: 1,
              lock_ttl_seconds: 60,
              buyer_agent_id: "did:agent:bot-test",
              quote_hash: "0".repeat(64)
            },
            { catalogStore: store }
          ),
        (err: unknown) => err instanceof SkuNotFoundException && (err as Error).message.includes("SKU-NON-EXISTENT-999")
      );
    });

    it("should reject tampered signature payload in lock response verification", async () => {
      const store = new CatalogStore();
      const lockResponse = await reserveInventoryLock(
        {
          sku_id: "SKU-CHAIR-001", quantity: 1, lock_ttl_seconds: 60, buyer_agent_id: "did:agent:bot-tamper",
          quote_hash: quoteHashFor(store, "SKU-CHAIR-001", 1, "did:agent:bot-tamper")
        },
        { catalogStore: store }
      );

      const baseParams = {
        lockToken: lockResponse.lock_token,
        fencingToken: lockResponse.fencing_token,
        skuId: lockResponse.sku_id,
        quantityLocked: lockResponse.quantity_locked,
        expiresAtUnixMs: lockResponse.expires_at_unix_ms
      };

      assert.equal(verifyLockSignature(baseParams, lockResponse.signature), true);
      assert.equal(verifyLockSignature({ ...baseParams, quantityLocked: baseParams.quantityLocked + 10 }, lockResponse.signature), false);
      assert.equal(verifyLockSignature({ ...baseParams, expiresAtUnixMs: baseParams.expiresAtUnixMs + 1000 }, lockResponse.signature), false);
    });

    it("should correctly calculate lock TTL timestamp and default TTL fallback", async () => {
      const store = new CatalogStore();
      const beforeTime = Date.now();
      const customTtl = 45;
      const resp = await reserveInventoryLock(
        {
          sku_id: "SKU-CHAIR-001", quantity: 1, lock_ttl_seconds: customTtl, buyer_agent_id: "did:agent:bot-ttl",
          quote_hash: quoteHashFor(store, "SKU-CHAIR-001", 1, "did:agent:bot-ttl")
        },
        { catalogStore: store }
      );
      const afterTime = Date.now();

      assert.ok(resp.expires_at_unix_ms >= beforeTime + customTtl * 1000);
      assert.ok(resp.expires_at_unix_ms <= afterTime + customTtl * 1000);
    });
  });
});
