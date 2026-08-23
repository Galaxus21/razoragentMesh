import { z } from "zod";
import {
  minQuantity,
  maxQuantity,
  minLockTtlSeconds,
  maxLockTtlSeconds,
  defaultLockTtlSeconds,
  deliveryTierStandard,
  deliveryTierExpress,
  deliveryTierSameDay,
  currencyInr
} from "./mcpConstants.js";

export interface VolumeTier {
  readonly minQuantity: number;
  readonly discountBps: number;
}

export interface TaxBreakdown {
  readonly cgstPaise: number;
  readonly sgstPaise: number;
  readonly igstPaise: number;
  readonly totalTaxPaise: number;
}

export interface CatalogSkuItem {
  readonly skuId: string;
  readonly name: string;
  readonly category: string;
  readonly description: string;
  readonly hsnCode: string;
  readonly gstRatePercent: number;
  readonly baseUnitPricePaise: number;
  readonly availableStock: number;
  readonly volumeTiers: VolumeTier[];
  readonly embeddingVector?: number[];
  readonly allergens?: string[];
  readonly brand?: string;
  readonly weightGrams?: number;
  readonly dimensionsCm?: {
    readonly length: number;
    readonly width: number;
    readonly height: number;
  };
  readonly originPincode?: string;
}

export interface SkuFilterCriteria {
  readonly category?: string;
  readonly hsnCode?: string;
  readonly minStock?: number;
  readonly brand?: string;
}

export const volumeTierSchema = z.object({
  minQuantity: z.number().int().min(1),
  discountBps: z.number().int().min(0).max(10000)
});

export const taxBreakdownSchema = z.object({
  cgstPaise: z.number().int().min(0),
  sgstPaise: z.number().int().min(0),
  igstPaise: z.number().int().min(0),
  totalTaxPaise: z.number().int().min(0)
});

export const catalogSkuItemSchema = z.object({
  skuId: z.string().min(1),
  name: z.string().min(1),
  category: z.string().min(1),
  description: z.string().min(1),
  hsnCode: z.string().regex(/^[0-9]{4,8}$/),
  gstRatePercent: z.number().min(0).max(100),
  baseUnitPricePaise: z.number().int().min(0),
  availableStock: z.number().int().min(0),
  volumeTiers: z.array(volumeTierSchema),
  embeddingVector: z.array(z.number()).optional(),
  allergens: z.array(z.string()).optional(),
  brand: z.string().optional(),
  weightGrams: z.number().int().min(1).optional(),
  dimensionsCm: z
    .object({
      length: z.number().positive(),
      width: z.number().positive(),
      height: z.number().positive()
    })
    .optional(),
  originPincode: z.string().regex(/^[1-9][0-9]{5}$/).optional()
});

export const skuQuoteRequestSchema = z.object({
  sku_id: z.string().regex(/^SKU-[A-Z0-9_-]{3,32}$/),
  quantity: z.number().int().min(minQuantity).max(maxQuantity),
  buyer_agent_id: z.string().regex(/^did:agent:[a-z0-9_\-\.:]+$/),
  delivery_pincode: z.string().regex(/^[1-9][0-9]{5}$/)
});

export type SkuQuoteRequest = z.infer<typeof skuQuoteRequestSchema>;

export const skuQuoteResponseSchema = z.object({
  sku_id: z.string(),
  available_stock: z.number().int().min(0),
  base_unit_price_paise: z.number().int().min(0),
  offered_unit_price_paise: z.number().int().min(0),
  currency: z.literal(currencyInr),
  hsn_code: z.string(),
  gst_rate_percent: z.number(),
  tax_breakdown: z.object({
    cgst_paise: z.number().int().min(0),
    sgst_paise: z.number().int().min(0),
    igst_paise: z.number().int().min(0),
    total_tax_paise: z.number().int().min(0)
  }),
  quote_expiry_timestamp: z.number().int().positive(),
  quote_hash: z.string().min(1)
});

export type SkuQuoteResponse = z.infer<typeof skuQuoteResponseSchema>;

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

export const shippingSlaRequestSchema = z.object({
  origin_pincode: z.string().regex(/^[1-9][0-9]{5}$/),
  delivery_pincode: z.string().regex(/^[1-9][0-9]{5}$/),
  package_weight_grams: z.number().int().min(1),
  required_delivery_tier: z.enum([
    deliveryTierStandard,
    deliveryTierExpress,
    deliveryTierSameDay
  ])
});

export type ShippingSlaRequest = z.infer<typeof shippingSlaRequestSchema>;

export const shippingSlaResponseSchema = z.object({
  guaranteed_sla_hours: z.number().int().positive(),
  shipping_cost_paise: z.number().int().min(0),
  courier_partner: z.string(),
  zone_code: z.string(),
  serviceable: z.boolean()
});

export type ShippingSlaResponse = z.infer<typeof shippingSlaResponseSchema>;

export class ArithmeticDriftException extends Error {
  readonly code = "ARITHMETIC_DRIFT";
  constructor(message: string) {
    super(message);
    this.name = "ArithmeticDriftException";
  }
}

export class SkuNotFoundException extends Error {
  readonly code = "SKU_NOT_FOUND";
  constructor(skuId: string) {
    super(`SKU with identifier ${skuId} was not found in catalog`);
    this.name = "SkuNotFoundException";
  }
}

export class InsufficientStockException extends Error {
  readonly code = "INSUFFICIENT_STOCK";
  constructor(skuId: string, requested: number, available: number) {
    super(`Insufficient stock for ${skuId}: requested ${requested}, available ${available}`);
    this.name = "InsufficientStockException";
  }
}

export class InvalidPincodeException extends Error {
  readonly code = "INVALID_PINCODE";
  constructor(pincode: string) {
    super(`Invalid delivery pincode provided: ${pincode}`);
    this.name = "InvalidPincodeException";
  }
}
