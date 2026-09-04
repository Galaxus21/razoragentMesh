// The MCP surface never reclaimed lapsed reservations, so it disagreed with itself.
//
// `InMemoryAtomicLocker.reclaimExpired` was wired into exactly one call site -- the REST adapter's
// GET /api/v1/quote. The MCP tools went straight to the catalog store, so an agent that took a
// lock over MCP and abandoned the run kept those units reported as held for the life of the
// process, long past the lock's TTL. `executeLock` sweeps as it acquires, which is what made the
// two answers contradict each other: reserve_inventory_lock would grant stock that
// get_live_sku_quote had just called unavailable.
//
// These tests drive the MCP dispatcher only. Nothing here touches routeHandlers, so a reclaim
// that lives on the REST path alone cannot make them pass.

import assert from "node:assert/strict";
import test from "node:test";
import { executeTool } from "../src/tools/toolRegistry.js";
import { defaultCatalogStore } from "../src/catalog/catalogStore.js";
import { reclaimExpiredDefaultReservations } from "../src/inventory/redisLockManager.js";
import {
  toolBrowseCatalog,
  toolGetLiveSkuQuote,
  toolReserveInventoryLock
} from "../src/constants/protocolConstants.js";
import type { BrowseCatalogResponse } from "../src/schemas/catalogBrowseSchema.js";
import type { InventoryLockResponse } from "../src/schemas/inventoryLockSchema.js";
import type { SkuQuoteResponse } from "../src/schemas/skuQuoteSchema.js";

const testSkuId = "SKU-CHAIR-001";
const buyerAgentId = "did:agent:mcp-read-path-01";
const deliveryPincode = "560001";
// The floor reserve_inventory_lock's schema accepts -- the shortest lock an agent can actually
// take, so the lapse under test is one the tool really permits.
const shortestLockTtlSeconds = 10;
const ttlOverrunMs = 15_000;
const abandonedQuantity = 4;

async function quoteOverMcp(quantity: number): Promise<SkuQuoteResponse> {
  return (await executeTool(toolGetLiveSkuQuote, {
    sku_id: testSkuId,
    quantity,
    buyer_agent_id: buyerAgentId,
    delivery_pincode: deliveryPincode
  })) as SkuQuoteResponse;
}

/** Quotes first because a lock is only granted against a quote_hash this mesh issued. */
async function lockOverMcp(quantity: number): Promise<InventoryLockResponse> {
  const quote = await quoteOverMcp(quantity);
  return (await executeTool(toolReserveInventoryLock, {
    sku_id: testSkuId,
    quantity,
    buyer_agent_id: buyerAgentId,
    quote_hash: quote.quote_hash,
    lock_ttl_seconds: shortestLockTtlSeconds
  })) as InventoryLockResponse;
}

/** Runs `body` with the clock pushed past every reservation's TTL, exactly as walking away does. */
async function afterLocksLapse<T>(body: () => Promise<T>): Promise<T> {
  const originalDateNow = Date.now;
  Date.now = () => originalDateNow() + ttlOverrunMs;
  try {
    return await body();
  } finally {
    Date.now = originalDateNow;
  }
}

// executeTool reads the singleton store and the singleton locker, so each test has to hand both
// back. Draining the locker BEFORE reseeding matters: a reservation left behind would be swept
// during a later test and credit its units into the freshly seeded store, inflating stock.
function restoreMeshState(): void {
  const originalDateNow = Date.now;
  Date.now = () => originalDateNow() + ttlOverrunMs;
  try {
    reclaimExpiredDefaultReservations();
  } finally {
    Date.now = originalDateNow;
  }
  defaultCatalogStore.resetCatalog();
}

test("an abandoned MCP lock stops holding stock once its TTL lapses", async (t) => {
  t.after(restoreMeshState);
  const initialStock = defaultCatalogStore.getStock(testSkuId);

  await lockOverMcp(abandonedQuantity);

  // While the lock is live the hold is real, and the quote is right to report it.
  const heldQuote = await quoteOverMcp(1);
  assert.equal(heldQuote.available_stock, initialStock - abandonedQuantity);

  // The agent walks away. Nothing else calls the mesh -- no REST quote, no second lock attempt.
  const lapsedQuote = await afterLocksLapse(() => quoteOverMcp(1));

  assert.equal(
    lapsedQuote.available_stock,
    initialStock,
    "a quote taken over MCP must report stock an expired lock no longer holds"
  );
});

test("the stock the MCP quote advertises is the stock a lock can take", async (t) => {
  t.after(restoreMeshState);
  const initialStock = defaultCatalogStore.getStock(testSkuId);

  await lockOverMcp(abandonedQuantity);

  await afterLocksLapse(async () => {
    const lapsedQuote = await quoteOverMcp(initialStock);
    assert.equal(lapsedQuote.available_stock, initialStock);

    // The property the whole fix is for: the read and the write agree. This lock asks for every
    // unit the quote just advertised, so it can only succeed if both surfaces swept.
    const lock = await lockOverMcp(initialStock);
    assert.equal(lock.quantity_locked, initialStock);
  });
});

test("browse_catalog lists a SKU that only an expired lock was hiding", async (t) => {
  t.after(restoreMeshState);
  const initialStock = defaultCatalogStore.getStock(testSkuId);

  // Hold every unit, so the SKU falls below browse's default min_stock of 1 and drops out of the
  // listing entirely -- a stronger failure than an understated count, and indistinguishable to
  // the agent from the mesh not selling the thing at all.
  await lockOverMcp(initialStock);
  const heldListing = (await executeTool(toolBrowseCatalog, {})) as BrowseCatalogResponse;
  assert.equal(
    heldListing.items.some((item) => item.sku_id === testSkuId),
    false,
    "a fully held SKU is correctly hidden while the lock is live"
  );

  const lapsedListing = await afterLocksLapse(
    async () => (await executeTool(toolBrowseCatalog, {})) as BrowseCatalogResponse
  );
  const listed = lapsedListing.items.find((item) => item.sku_id === testSkuId);

  assert.ok(listed, "an expired lock must not keep a SKU out of the catalog listing");
  assert.equal(listed.available_stock, initialStock);
});
