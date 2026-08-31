// Pins the stock-leak fix: an inventory lock is a time-bounded reservation, so stock it held
// must return when it lapses. Before the sweeper, `executeLock` decremented stock and recorded
// an `expiresAt` that nothing read, so repeated reservations drove availability to zero
// permanently and every later caller got HTTP 409 with no way to recover.

import assert from "node:assert/strict";
import test from "node:test";
import { CatalogStore } from "../src/catalog/catalogStore.js";
import { InMemoryAtomicLocker } from "../src/inventory/redisLockManager.js";
import {
  sweepExpiredInMemoryLocks,
  type ReservationRecord
} from "../src/inventory/lockExpirySweeper.js";

const testSkuId = "SKU-CHAIR-001";
const shortTtlSeconds = 10;
const ttlOverrunMs = 11_000;

// `new CatalogStore()` seeds itself from the real catalog fixtures, so these tests exercise the
// same SKU shape the running service uses rather than a hand-rolled stand-in.
function buildSeededStore(): { store: CatalogStore; initialStock: number } {
  const store = new CatalogStore();
  return { store, initialStock: store.getStock(testSkuId) };
}

test("stock held by an expired reservation is returned", () => {
  const { store, initialStock } = buildSeededStore();
  const reservations = new Map<string, ReservationRecord>();
  const nowMs = Date.now();

  store.updateStock(testSkuId, -4);
  reservations.set("lock-a", {
    skuId: testSkuId,
    quantity: 4,
    expiresAtUnixMs: nowMs + shortTtlSeconds * 1000
  });
  assert.equal(store.getStock(testSkuId), initialStock - 4);

  // Before expiry: nothing is reclaimed.
  const earlySweep = sweepExpiredInMemoryLocks(store, reservations, nowMs);
  assert.equal(earlySweep.releasedLockCount, 0);
  assert.equal(store.getStock(testSkuId), initialStock - 4);

  // After expiry: the reservation lapses and its units come back.
  const lateSweep = sweepExpiredInMemoryLocks(store, reservations, nowMs + ttlOverrunMs);
  assert.equal(lateSweep.releasedLockCount, 1);
  assert.equal(lateSweep.restoredUnits, 4);
  assert.equal(store.getStock(testSkuId), initialStock);
});

test("an expired reservation is never released twice", () => {
  const { store, initialStock } = buildSeededStore();
  const reservations = new Map<string, ReservationRecord>();
  store.updateStock(testSkuId, -3);
  reservations.set("lock-b", { skuId: testSkuId, quantity: 3, expiresAtUnixMs: 1 });

  sweepExpiredInMemoryLocks(store, reservations, Date.now());
  sweepExpiredInMemoryLocks(store, reservations, Date.now());

  assert.equal(store.getStock(testSkuId), initialStock, "double sweep must not credit stock twice");
  assert.equal(reservations.size, 0);
});

test("repeated reservations do not exhaust stock permanently", () => {
  const { store, initialStock } = buildSeededStore();
  const locker = new InMemoryAtomicLocker();
  const lockQuantity = 2;
  const lockCount = Math.floor(initialStock / lockQuantity);

  // Reserve the entire available stock across a series of small locks.
  for (let index = 0; index < lockCount; index += 1) {
    const result = locker.executeLock(store, testSkuId, lockQuantity, shortTtlSeconds, `lock-${index}`);
    assert.equal(result.success, true, `lock ${index} should succeed while stock remains`);
  }
  assert.ok(store.getStock(testSkuId) < lockQuantity, "stock should now be exhausted");

  // A sixth attempt fails now -- correct, the stock really is held.
  assert.equal(
    locker.executeLock(store, testSkuId, lockQuantity, shortTtlSeconds, "lock-overflow").success,
    false
  );

  // Once those reservations lapse, availability must return. This is the assertion that
  // failed before the fix: the catalog stayed at zero forever.
  const originalDateNow = Date.now;
  Date.now = () => originalDateNow() + ttlOverrunMs;
  try {
    const afterExpiry = locker.executeLock(store, testSkuId, lockQuantity, shortTtlSeconds, "lock-post-expiry");
    assert.equal(afterExpiry.success, true, "expired reservations must free their stock");
  } finally {
    Date.now = originalDateNow;
  }
});
