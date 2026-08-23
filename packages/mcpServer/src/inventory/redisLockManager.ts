import type { Redis } from "ioredis";
import { millisPerSecond } from "../constants/protocolConstants.js";
import { CatalogStore } from "../catalog/catalogStore.js";

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

export const stockKeyPrefix = "inventory:stock:";
export const lockKeyPrefix = "inventory:lock:";
export const globalFencingKey = "inventory:fencing:global";
export const initialInMemoryFencingCounter = 1000;
export const failureFencingToken = 0;
export const luaKeysCount = 3;
export const luaSuccessCode = 1;

export const atomicLockLuaScript = `
local currentStock = tonumber(redis.call('GET', KEYS[1]) or '0')
local requestedQty = tonumber(ARGV[1])
if currentStock < requestedQty then
  return {0, currentStock, 0}
end
local remainingStock = redis.call('DECRBY', KEYS[1], requestedQty)
local fencingToken = redis.call('INCR', KEYS[3])
redis.call('SETEX', KEYS[2], tonumber(ARGV[2]), ARGV[3])
return {1, remainingStock, fencingToken}
`;

export class InMemoryAtomicLocker {
  private fencingCounter = initialInMemoryFencingCounter;
  private readonly locks = new Map<string, { skuId: string; quantity: number; expiresAt: number }>();

  public executeLock(
    catalogStore: CatalogStore,
    skuId: string,
    quantity: number,
    lockTtlSeconds: number,
    lockToken: string
  ): LockExecutionResult {
    const currentStock = catalogStore.getStock(skuId);
    if (currentStock < quantity) {
      return { success: false, remainingStock: currentStock, fencingToken: failureFencingToken };
    }

    const remainingStock = catalogStore.updateStock(skuId, -quantity);
    this.fencingCounter += 1;
    const fencingToken = this.fencingCounter;
    const expiresAt = Date.now() + lockTtlSeconds * millisPerSecond;

    this.locks.set(lockToken, { skuId, quantity, expiresAt });
    return { success: true, remainingStock, fencingToken };
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
  const stockKey = `${stockKeyPrefix}${skuId}`;
  const lockKey = `${lockKeyPrefix}${lockToken}`;
  const result = (await redis.eval(
    atomicLockLuaScript,
    luaKeysCount,
    stockKey,
    lockKey,
    globalFencingKey,
    quantity,
    ttlSeconds,
    lockRecordJson
  )) as [number, number, number];

  return {
    success: result[0] === luaSuccessCode,
    remainingStock: Number(result[1]),
    fencingToken: Number(result[2])
  };
}
