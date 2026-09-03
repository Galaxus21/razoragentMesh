// The other half of the reservation contract, pinned after the 2026-09-03 rehearsal.
//
// `lockExpiryRestoresStock.test.ts` proves an ABANDONED reservation gives its stock back. Nothing
// proved that a SETTLED one does not. Both end as a reservation whose expiry passes, and the
// sweeper could not tell them apart, so a completed sale expired like an abandonment and returned
// its unit to the shelf: SKU-TEST-DESK-LASTONE, authored with stock 1, took three captured
// payments in five minutes and read back as 1 available.
//
// `execute_settlement` now consumes the reservation on capture. These tests hold that line.

import assert from "node:assert/strict";
import test from "node:test";
import { CatalogStore } from "../src/catalog/catalogStore.js";
import { InMemoryAtomicLocker } from "../src/inventory/redisLockManager.js";

const testSkuId = "SKU-CHAIR-001";
const shortTtlSeconds = 10;
const ttlOverrunMs = 11_000;
const singleUnit = 1;

function buildSeededStore(): { store: CatalogStore; initialStock: number } {
  const store = new CatalogStore();
  return { store, initialStock: store.getStock(testSkuId) };
}

// Runs `body` with the clock pushed past every reservation's TTL, so the next acquire sweeps.
function afterLocksLapse<T>(body: () => T): T {
  const originalDateNow = Date.now;
  Date.now = () => originalDateNow() + ttlOverrunMs;
  try {
    return body();
  } finally {
    Date.now = originalDateNow;
  }
}

test("a settled reservation is not credited back when it lapses", () => {
  const { store, initialStock } = buildSeededStore();
  const locker = new InMemoryAtomicLocker();

  assert.equal(locker.executeLock(store, testSkuId, 2, shortTtlSeconds, "lock-sold").success, true);
  assert.equal(store.getStock(testSkuId), initialStock - 2);

  assert.equal(locker.consumeReservation("lock-sold"), true, "the sale must claim its reservation");

  // The acquire below sweeps first; a sold unit must not be among what it reclaims.
  afterLocksLapse(() => locker.reclaimExpired(store));
  assert.equal(store.getStock(testSkuId), initialStock - 2, "a sold unit must stay sold");
});

test("a settled reservation and an abandoned one are told apart", () => {
  const { store, initialStock } = buildSeededStore();
  const locker = new InMemoryAtomicLocker();

  locker.executeLock(store, testSkuId, 2, shortTtlSeconds, "lock-sold");
  locker.executeLock(store, testSkuId, 3, shortTtlSeconds, "lock-abandoned");
  locker.consumeReservation("lock-sold");

  const sweep = afterLocksLapse(() => locker.reclaimExpired(store));

  assert.equal(sweep.restoredUnits, 3, "only the abandoned cart returns its units");
  assert.equal(store.getStock(testSkuId), initialStock - 2);
});

test("consuming the same reservation twice is a no-op", () => {
  const { store, initialStock } = buildSeededStore();
  const locker = new InMemoryAtomicLocker();

  locker.executeLock(store, testSkuId, 2, shortTtlSeconds, "lock-sold");
  assert.equal(locker.consumeReservation("lock-sold"), true);
  assert.equal(locker.consumeReservation("lock-sold"), false, "a second consume claims nothing");

  afterLocksLapse(() => locker.reclaimExpired(store));
  assert.equal(store.getStock(testSkuId), initialStock - 2);
});

test("the last unit cannot be sold twice", () => {
  const { store, initialStock } = buildSeededStore();
  const locker = new InMemoryAtomicLocker();

  // Drive the SKU down to a single unit -- the scarcity case the rehearsal oversold.
  store.updateStock(testSkuId, -(initialStock - singleUnit));
  assert.equal(store.getStock(testSkuId), singleUnit);

  const firstBuyer = locker.executeLock(store, testSkuId, singleUnit, shortTtlSeconds, "lock-winner");
  assert.equal(firstBuyer.success, true);
  locker.consumeReservation("lock-winner");
  assert.equal(store.getStock(testSkuId), 0);

  const secondBuyer = afterLocksLapse(() =>
    locker.executeLock(store, testSkuId, singleUnit, shortTtlSeconds, "lock-latecomer")
  );

  assert.equal(secondBuyer.success, false, "a sold-out SKU must refuse the next buyer");
  assert.equal(store.getStock(testSkuId), 0);
});
