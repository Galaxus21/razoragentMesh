// Returns stock held by reservations that have since expired.
//
// An inventory lock is a TIME-BOUNDED reservation, not a sale: if the buyer never settles, the
// stock must become available again when the lock lapses. Both lockers previously decremented
// stock on acquire and never restored it -- the in-memory one recorded an `expiresAt` nothing
// ever read, and the Redis one SETEX'd only the lock key, so when that key expired the
// decremented quantity was simply lost. Stock therefore leaked monotonically to zero and every
// later reservation failed with HTTP 409 permanently.
//
// Sweeping runs lazily, immediately before each acquire attempt, so there is no background
// timer to supervise and the restore is always observed by the request that needs it.

import type { Redis } from "ioredis";
import type { CatalogStore } from "../catalog/catalogStore.js";
import {
  activeReservationsKey,
  reservationQuantitiesKey,
  reservationEntrySeparator,
  stockKeyPrefix
} from "./inventoryKeys.js";

export interface ReservationRecord {
  readonly skuId: string;
  readonly quantity: number;
  readonly expiresAtUnixMs: number;
}

export interface SweepResult {
  readonly releasedLockCount: number;
  readonly restoredUnits: number;
}

// Atomically pops every reservation whose expiry has passed and credits its quantity back to
// that SKU's stock counter. One EVAL, so a concurrent acquire can never observe a half-swept
// state; the ZREM return value gates the restore, so a reservation cannot be released twice
// even if two clients sweep at the same instant.
export const sweepExpiredLocksLuaScript = `
local nowMs = tonumber(ARGV[1])
local stockPrefix = ARGV[2]
local separator = ARGV[3]
local expired = redis.call('ZRANGEBYSCORE', KEYS[1], '-inf', nowMs)
local releasedCount = 0
local restoredUnits = 0
for i = 1, #expired do
  local entry = expired[i]
  if redis.call('ZREM', KEYS[1], entry) == 1 then
    local separatorIndex = string.find(entry, separator, 1, true)
    if separatorIndex then
      local skuId = string.sub(entry, separatorIndex + 1)
      local quantity = tonumber(redis.call('HGET', KEYS[2], entry) or '0')
      if quantity > 0 then
        redis.call('INCRBY', stockPrefix .. skuId, quantity)
        restoredUnits = restoredUnits + quantity
      end
      redis.call('HDEL', KEYS[2], entry)
      releasedCount = releasedCount + 1
    end
  end
end
return {releasedCount, restoredUnits}
`;

const sweepLuaKeysCount = 2;

export async function sweepExpiredRedisLocks(redis: Redis, nowMs: number): Promise<SweepResult> {
  const result = (await redis.eval(
    sweepExpiredLocksLuaScript,
    sweepLuaKeysCount,
    activeReservationsKey,
    reservationQuantitiesKey,
    nowMs.toString(),
    stockKeyPrefix,
    reservationEntrySeparator
  )) as [number, number];

  return { releasedLockCount: Number(result[0]), restoredUnits: Number(result[1]) };
}

// In-memory equivalent for the no-Redis path used by tests and single-process runs.
export function sweepExpiredInMemoryLocks(
  catalogStore: CatalogStore,
  reservations: Map<string, ReservationRecord>,
  nowMs: number
): SweepResult {
  let releasedLockCount = 0;
  let restoredUnits = 0;

  for (const [lockToken, reservation] of reservations) {
    if (reservation.expiresAtUnixMs > nowMs) {
      continue;
    }
    reservations.delete(lockToken);
    catalogStore.updateStock(reservation.skuId, reservation.quantity);
    releasedLockCount += 1;
    restoredUnits += reservation.quantity;
  }

  return { releasedLockCount, restoredUnits };
}
