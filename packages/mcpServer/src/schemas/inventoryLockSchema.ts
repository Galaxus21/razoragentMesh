import { z } from "zod";
import {
  minQuantity,
  minLockTtlSeconds,
  maxLockTtlSeconds,
  defaultLockTtlSeconds
} from "../constants/protocolConstants.js";

export const inventoryLockRequestSchema = z.object({
  sku_id: z.string(),
  quantity: z.number().int().min(minQuantity),
  lock_ttl_seconds: z
    .number()
    .int()
    .min(minLockTtlSeconds)
    .max(maxLockTtlSeconds)
    .default(defaultLockTtlSeconds),
  buyer_agent_id: z.string(),
  quote_hash: z.string()
});

export type InventoryLockRequest = z.infer<typeof inventoryLockRequestSchema>;

export const inventoryLockResponseSchema = z.object({
  lock_token: z.string().uuid(),
  fencing_token: z.number().int().positive(),
  sku_id: z.string(),
  quantity_locked: z.number().int().positive(),
  expires_at_unix_ms: z.number().int().positive(),
  signature: z.string().min(1)
});

export type InventoryLockResponse = z.infer<typeof inventoryLockResponseSchema>;
