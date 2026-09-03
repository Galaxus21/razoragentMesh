import type { Redis } from "ioredis";
import { millisPerSecond } from "../constants/protocolConstants.js";
import { CatalogStore } from "../catalog/catalogStore.js";
import {
  activeReservationsKey,
  buildReservationEntry,
  globalFencingKey,
  lockKeyPrefix,
  reservationQuantitiesKey,
  stockKeyPrefix
} from "./inventoryKeys.js";
import {
  ReservationRecord,
  SweepResult,
  sweepExpiredInMemoryLocks,
  sweepExpiredRedisLocks
} from "./lockExpirySweeper.js";

export type { ReservationRecord };
export { stockKeyPrefix, lockKeyPrefix, globalFencingKey };

export interface LockExecutionResult {
  readonly success: boolean;
  readonly remainingStock: number;
  readonly fencingToken: number;
}

export interface LockRecordPayload {
  readonly lockToken: string;
  readonly skuId: string;
  readonly quantity: number;
  readonly buyerAgentId: string;
  readonly quoteHash: string;
  readonly expiresAtUnixMs: number;
}

export const initialInMemoryFencingCounter = 1000;
export const failureFencingToken = 0;
export const luaKeysCount = 5;
export const consumeLuaKeysCount = 2;
export const luaSuccessCode = 1;

// Registers the reservation in a sorted set scored by expiry alongside decrementing stock, so
// the sweeper can later credit the quantity back. Without the ZADD/HSET pair, an expired lock
// key would vanish and take its stock with it.
export const atomicLockLuaScript = `
local currentStock = tonumber(redis.call('GET', KEYS[1]) or '0')
local requestedQty = tonumber(ARGV[1])
if currentStock < requestedQty then
  return {0, currentStock, 0}
end
local remainingStock = redis.call('DECRBY', KEYS[1], requestedQty)
local fencingToken = redis.call('INCR', KEYS[3])
redis.call('SETEX', KEYS[2], tonumber(ARGV[2]), ARGV[3])
redis.call('ZADD', KEYS[4], tonumber(ARGV[4]), ARGV[5])
redis.call('HSET', KEYS[5], ARGV[5], requestedQty)
return {1, remainingStock, fencingToken}
`;

// Retires a reservation WITHOUT crediting its quantity back. A settled purchase and an abandoned
// cart both end with a reservation whose expiry passes; only the sweeper's restore separates
// them, so the sale has to remove its own entry or the sweeper will hand the unit back and the
// SKU oversells. Gated on the ZREM return so consuming twice is a no-op. The lock key itself is
// left to its SETEX to expire -- nothing reads it after the cart is signed.
export const consumeReservationLuaScript = `
local entry = ARGV[1]
local removed = redis.call('ZREM', KEYS[1], entry)
if removed == 1 then
  redis.call('HDEL', KEYS[2], entry)
end
return removed
`;

export class InMemoryAtomicLocker {
  private fencingCounter = initialInMemoryFencingCounter;
  private readonly reservations = new Map<string, ReservationRecord>();

  public executeLock(
    catalogStore: CatalogStore,
    skuId: string,
    quantity: number,
    lockTtlSeconds: number,
    lockToken: string
  ): LockExecutionResult {
    // Reclaim lapsed reservations first, so a caller that arrives after a TTL boundary sees
    // the stock those reservations were holding.
    sweepExpiredInMemoryLocks(catalogStore, this.reservations, Date.now());

    const currentStock = catalogStore.getStock(skuId);
    if (currentStock < quantity) {
      return { success: false, remainingStock: currentStock, fencingToken: failureFencingToken };
    }

    const remainingStock = catalogStore.updateStock(skuId, -quantity);
    this.fencingCounter += 1;
    const fencingToken = this.fencingCounter;
    const expiresAtUnixMs = Date.now() + lockTtlSeconds * millisPerSecond;

    this.reservations.set(lockToken, { skuId, quantity, expiresAtUnixMs });
    return { success: true, remainingStock, fencingToken };
  }

  // Exposed for the READ path. Sweeping only on acquire leaves `availableStock` understated
  // between a reservation lapsing and the next lock attempt, so a quote would advertise stock
  // that is actually free as unavailable. Callers that merely read stock invoke this first.
  public reclaimExpired(catalogStore: CatalogStore): SweepResult {
    return sweepExpiredInMemoryLocks(catalogStore, this.reservations, Date.now());
  }

  // Settled counterpart to the sweeper: drops the reservation so its quantity is never credited
  // back. Returns false when the token is unknown -- already consumed, or already swept.
  public consumeReservation(lockToken: string): boolean {
    return this.reservations.delete(lockToken);
  }

  public getActiveReservationCount(): number {
    return this.reservations.size;
  }
}

export const defaultInMemoryLocker = new InMemoryAtomicLocker();

export async function executeRedisLock(
  redis: Redis,
  skuId: string,
  quantity: number,
  ttlSeconds: number,
  lockToken: string,
  lockRecordJson: string
): Promise<LockExecutionResult> {
  await sweepExpiredRedisLocks(redis, Date.now());

  const stockKey = `${stockKeyPrefix}${skuId}`;
  const lockKey = `${lockKeyPrefix}${lockToken}`;
  const expiresAtUnixMs = Date.now() + ttlSeconds * millisPerSecond;
  const reservationEntry = buildReservationEntry(lockToken, skuId);

  const result = (await redis.eval(
    atomicLockLuaScript,
    luaKeysCount,
    stockKey,
    lockKey,
    globalFencingKey,
    activeReservationsKey,
    reservationQuantitiesKey,
    quantity,
    ttlSeconds,
    lockRecordJson,
    expiresAtUnixMs,
    reservationEntry
  )) as [number, number, number];

  return {
    success: result[0] === luaSuccessCode,
    remainingStock: Number(result[1]),
    fencingToken: Number(result[2])
  };
}

export async function consumeRedisReservation(
  redis: Redis,
  lockToken: string,
  skuId: string
): Promise<boolean> {
  const removed = (await redis.eval(
    consumeReservationLuaScript,
    consumeLuaKeysCount,
    activeReservationsKey,
    reservationQuantitiesKey,
    buildReservationEntry(lockToken, skuId)
  )) as number;

  return Number(removed) === luaSuccessCode;
}
