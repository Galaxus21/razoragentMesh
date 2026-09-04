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
import { findSubstituteForOutOfStock } from "../catalog/substituteFinder.js";
import { defaultCatalogStore, CatalogStore } from "../catalog/catalogStore.js";
import { signLockPayload } from "../crypto/lockSignatureGenerator.js";
import {
  defaultInMemoryLocker,
  executeRedisLock
} from "../inventory/redisLockManager.js";
import {
  defaultIssuedQuoteRegistry,
  errorQuoteCoversDifferentPurchase,
  errorQuoteLapsedBeforeLock,
  errorQuoteNotIssued,
  IssuedQuoteRegistry
} from "../inventory/issuedQuoteRegistry.js";

export interface LockOptions {
  readonly redisClient?: Redis;
  readonly privateKeyHex?: string;
  readonly catalogStore?: CatalogStore;
  readonly quoteRegistry?: IssuedQuoteRegistry;
}

export function normalizeLockRequest(rawInput: unknown): InventoryLockRequest {
  const inputObj = rawInput as Record<string, unknown>;
  const normalized = {
    sku_id: inputObj.sku_id ?? inputObj.skuId,
    quantity: inputObj.quantity,
    lock_ttl_seconds: inputObj.lock_ttl_seconds ?? inputObj.lockTtlSeconds ?? defaultLockTtlSeconds,
    buyer_agent_id: inputObj.buyer_agent_id ?? inputObj.buyerAgentId ?? inputObj.buyerAgentDid,
    quote_hash: inputObj.quote_hash ?? inputObj.quoteHash
  };

  return inventoryLockRequestSchema.parse(normalized);
}

export async function reserveInventoryLock(
  rawRequest: unknown,
  options: LockOptions = {}
): Promise<InventoryLockResponse> {
  const { request, store } = _validateLockRequest(rawRequest, options.catalogStore);
  // Before the reservation, never after: the whole point is that an unverifiable quote_hash must
  // not cost the merchant stock. A refusal here has taken nothing.
  _rejectUnissuedQuote(request, options.quoteRegistry);

  let reservation: { lockToken: string; expiresAtUnixMs: number; fencingToken: number };
  try {
    reservation = await _executeAtomicReservation(request, store, options);
  } catch (err: unknown) {
    if (err instanceof InsufficientStockException) {
      const substitute = await findSubstituteForOutOfStock(request.sku_id, request.quantity);
      if (substitute) {
        const priceFormatted = (substitute.unitPricePaise / 100).toFixed(2);
        let similarityText = "";
        if (substitute.embeddingMode === "model" && substitute.cosineScore !== null) {
          similarityText = `, semantic similarity ${substitute.cosineScore.toFixed(2)} to the SKU you asked for`;
        }
        const advice = `No stock was reserved and nothing was charged. A substitute is available: ${substitute.substituteSkuId} (${substitute.title}) at ${priceFormatted} INR per unit${similarityText}. To take it, call get_live_sku_quote for ${substitute.substituteSkuId} and lock that quote.`;
        throw new InsufficientStockException(request.sku_id, request.quantity, err.available, advice);
      }
    }
    throw err;
  }

  return _buildLockResponse(request, reservation.lockToken, reservation.fencingToken, reservation.expiresAtUnixMs, options.privateKeyHex);
}

function _validateLockRequest(
  rawRequest: unknown,
  catalogStore?: CatalogStore
): { request: InventoryLockRequest; store: CatalogStore } {
  const request = normalizeLockRequest(rawRequest);
  const store = catalogStore ?? defaultCatalogStore;
  const sku = store.getSku(request.sku_id);

  if (!sku) {
    throw new SkuNotFoundException(request.sku_id);
  }

  return { request, store };
}

/**
 * Refuses a quote_hash this mesh did not issue for this exact purchase.
 *
 * quote_hash was a required parameter that nothing checked: it was folded into the lock signature
 * as supplied, so any string bought a real lock and real stock, and the agent only found out at
 * create_cart_mandate. The three refusals are deliberately distinct -- "quote first", "quote
 * again" and "you are locking something else" are three different mistakes with three different
 * fixes, and only err.message reaches the agent.
 */
function _rejectUnissuedQuote(
  request: InventoryLockRequest,
  quoteRegistry: IssuedQuoteRegistry = defaultIssuedQuoteRegistry
): void {
  const lookup = {
    quoteHash: request.quote_hash,
    skuId: request.sku_id,
    quantity: request.quantity,
    buyerAgentId: request.buyer_agent_id
  };
  const verdict = quoteRegistry.verify(lookup);

  switch (verdict.outcome) {
    case "issued":
      return;
    case "expired":
      throw new Error(errorQuoteLapsedBeforeLock(verdict.lapsedSeconds));
    case "parametersDiffer":
      throw new Error(errorQuoteCoversDifferentPurchase(verdict.issued, lookup));
    default:
      throw new Error(errorQuoteNotIssued);
  }
}

async function _executeAtomicReservation(
  request: InventoryLockRequest,
  store: CatalogStore,
  options: LockOptions
): Promise<{ lockToken: string; expiresAtUnixMs: number; fencingToken: number }> {
  const lockToken = uuidv4();
  const expiresAtUnixMs = Date.now() + request.lock_ttl_seconds * millisPerSecond;
  const lockRecord = JSON.stringify({
    lockToken, skuId: request.sku_id, quantity: request.quantity,
    buyerAgentId: request.buyer_agent_id, quoteHash: request.quote_hash, expiresAtUnixMs
  });

  const lockResult = options.redisClient
    ? await executeRedisLock(
        options.redisClient, request.sku_id, request.quantity,
        request.lock_ttl_seconds, lockToken, lockRecord
      )
    : defaultInMemoryLocker.executeLock(
        store, request.sku_id, request.quantity, request.lock_ttl_seconds, lockToken
      );

  if (!lockResult.success) {
    throw new InsufficientStockException(request.sku_id, request.quantity, lockResult.remainingStock);
  }

  return { lockToken, expiresAtUnixMs, fencingToken: lockResult.fencingToken };
}

function _buildLockResponse(
  request: InventoryLockRequest,
  lockToken: string,
  fencingToken: number,
  expiresAtUnixMs: number,
  privateKeyHex?: string
): InventoryLockResponse {
  const privateKey = privateKeyHex ?? defaultMerchantPrivateKeyHex;
  const signature = signLockPayload(
    { lockToken, fencingToken, skuId: request.sku_id, quantityLocked: request.quantity, expiresAtUnixMs },
    privateKey
  );

  const response: InventoryLockResponse = {
    lock_token: lockToken,
    fencing_token: fencingToken,
    sku_id: request.sku_id,
    quantity_locked: request.quantity,
    expires_at_unix_ms: expiresAtUnixMs,
    signature
  };

  return inventoryLockResponseSchema.parse(response);
}
