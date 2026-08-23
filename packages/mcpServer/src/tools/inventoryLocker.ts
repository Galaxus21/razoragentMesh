import { v4 as uuidv4 } from "uuid";
import type { Redis } from "ioredis";
import {
  defaultMerchantPrivateKeyHex,
  defaultLockTtlSeconds,
  millisPerSecond
} from "../constants/protocolConstants.js";
import {
  InventoryLockRequest,
  InventoryLockResponse,
  inventoryLockRequestSchema,
  inventoryLockResponseSchema
} from "../schemas/inventoryLockSchema.js";
import {
  InsufficientStockException,
  SkuNotFoundException
} from "../types/mcpToolTypes.js";
import { defaultCatalogStore, CatalogStore } from "../catalog/catalogStore.js";
import { signLockPayload } from "../crypto/lockSignatureGenerator.js";
import {
  defaultInMemoryLocker,
  executeRedisLock
} from "../inventory/redisLockManager.js";

export interface LockOptions {
  readonly redisClient?: Redis;
  readonly privateKeyHex?: string;
  readonly catalogStore?: CatalogStore;
}

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
