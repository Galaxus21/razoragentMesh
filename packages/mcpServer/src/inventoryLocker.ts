import { v4 as uuidv4 } from "uuid";
import type { Redis } from "ioredis";
import {
  defaultMerchantPrivateKeyHex,
  defaultLockTtlSeconds,
  millisPerSecond
} from "./mcpConstants.js";
import {
  InventoryLockRequest,
  InventoryLockResponse,
  inventoryLockRequestSchema,
  inventoryLockResponseSchema,
  InsufficientStockException,
  SkuNotFoundException
} from "./mcpTypes.js";
import { defaultCatalogStore, CatalogStore } from "./catalogStore.js";
import { signLockPayload } from "./cryptoUtils.js";

export interface LockOptions {
  readonly redisClient?: Redis;
  readonly privateKeyHex?: string;
  readonly catalogStore?: CatalogStore;
}

export const stockKeyPrefix = "inventory:stock:";
export const lockKeyPrefix = "inventory:lock:";
export const globalFencingKey = "inventory:fencing:global";

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

class InMemoryAtomicLocker {
  private fencingCounter = 1000;
  private readonly locks = new Map<string, { skuId: string; quantity: number; expiresAt: number }>();

  public executeLock(
    catalogStore: CatalogStore,
    skuId: string,
    quantity: number,
    lockTtlSeconds: number,
    lockToken: string
  ): { success: boolean; remainingStock: number; fencingToken: number } {
    const currentStock = catalogStore.getStock(skuId);
    if (currentStock < quantity) {
      return { success: false, remainingStock: currentStock, fencingToken: 0 };
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

export function normalizeLockRequest(rawInput: unknown): InventoryLockRequest {
  const inputObj = rawInput as Record<string, unknown>;
  const normalized = {
    sku_id: inputObj.sku_id ?? inputObj.skuId,
    quantity: inputObj.quantity,
    lock_ttl_seconds: inputObj.lock_ttl_seconds ?? inputObj.lockTtlSeconds ?? defaultLockTtlSeconds,
    buyer_agent_id: inputObj.buyer_agent_id ?? inputObj.buyerAgentId,
    quote_hash: inputObj.quote_hash ?? inputObj.quoteHash
  };

  return inventoryLockRequestSchema.parse(normalized);
}

async function executeRedisLock(
  redis: Redis,
  skuId: string,
  quantity: number,
  ttlSeconds: number,
  lockToken: string,
  lockRecordJson: string
): Promise<{ success: boolean; remainingStock: number; fencingToken: number }> {
  const stockKey = `${stockKeyPrefix}${skuId}`;
  const lockKey = `${lockKeyPrefix}${lockToken}`;
  const result = (await redis.eval(
    atomicLockLuaScript,
    3,
    stockKey,
    lockKey,
    globalFencingKey,
    quantity,
    ttlSeconds,
    lockRecordJson
  )) as [number, number, number];

  return {
    success: result[0] === 1,
    remainingStock: Number(result[1]),
    fencingToken: Number(result[2])
  };
}

export async function reserveInventoryLock(
  rawRequest: unknown,
  options: LockOptions = {}
): Promise<InventoryLockResponse> {
  const request = normalizeLockRequest(rawRequest);
  const store = options.catalogStore ?? defaultCatalogStore;
  const sku = store.getSku(request.sku_id);

  if (!sku) {
    throw new SkuNotFoundException(request.sku_id);
  }

  const lockToken = uuidv4();
  const expiresAtUnixMs = Date.now() + request.lock_ttl_seconds * millisPerSecond;
  const lockRecord = JSON.stringify({
    lockToken,
    skuId: request.sku_id,
    quantity: request.quantity,
    buyerAgentId: request.buyer_agent_id,
    quoteHash: request.quote_hash,
    expiresAtUnixMs
  });

  const lockResult = options.redisClient
    ? await executeRedisLock(
        options.redisClient,
        request.sku_id,
        request.quantity,
        request.lock_ttl_seconds,
        lockToken,
        lockRecord
      )
    : defaultInMemoryLocker.executeLock(
        store,
        request.sku_id,
        request.quantity,
        request.lock_ttl_seconds,
        lockToken
      );

  if (!lockResult.success) {
    throw new InsufficientStockException(
      request.sku_id,
      request.quantity,
      lockResult.remainingStock
    );
  }

  const privateKey = options.privateKeyHex ?? defaultMerchantPrivateKeyHex;
  const signature = signLockPayload(
    {
      lockToken,
      fencingToken: lockResult.fencingToken,
      skuId: request.sku_id,
      quantityLocked: request.quantity,
      expiresAtUnixMs
    },
    privateKey
  );

  const response: InventoryLockResponse = {
    lock_token: lockToken,
    fencing_token: lockResult.fencingToken,
    sku_id: request.sku_id,
    quantity_locked: request.quantity,
    expires_at_unix_ms: expiresAtUnixMs,
    signature
  };

  return inventoryLockResponseSchema.parse(response);
}
