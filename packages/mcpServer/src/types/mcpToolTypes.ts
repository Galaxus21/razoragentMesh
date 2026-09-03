import { z } from "zod";

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

export interface AppliedDiscountItem {
  readonly type: "VOLUME_TIER" | "CAMPAIGN" | "PAYMENT_RAIL" | "PROMO_CODE";
  readonly label: string;
  readonly discountBps?: number;
  readonly discountPaise?: number;
}

export interface DiscountStackResult {
  readonly offeredUnitPricePaise: number;
  readonly appliedDiscounts: readonly AppliedDiscountItem[];
  readonly totalSavingsPaise: number;
}

export interface RedisChannelSubscriber {
  subscribe(...channels: (string | Buffer)[]): unknown;
  on(event: string, listener: (...args: unknown[]) => void): unknown;
}

export interface ScheduledPromotion {
  readonly campaignId: string;
  readonly name: string;
  readonly startsAtUnix: number;
  readonly endsAtUnix: number;
  readonly discountBps?: number;
  readonly discountPaise?: number;
  readonly fixedPricePaise?: number;
  readonly limitedStockAllocated?: number;
}

export interface UpcomingPromotion {
  readonly campaign_id: string;
  readonly name: string;
  readonly starts_at_unix: number;
  readonly ends_at_unix: number;
  readonly expected_unit_price_paise: number;
  readonly expected_savings_paise: number;
  readonly limited_stock_allocated?: number;
}

export interface EvaluatedPromotionsResult {
  readonly activePromotions: readonly UpcomingPromotion[];
  readonly upcomingPromotions: readonly UpcomingPromotion[];
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
  readonly promotions?: readonly ScheduledPromotion[];
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

export interface JsonRpcRequest {
  readonly jsonrpc: string;
  readonly id?: string | number | null;
  readonly method: string;
  readonly params?: Record<string, unknown>;
}

export interface JsonRpcResponse {
  readonly jsonrpc: string;
  readonly id: string | number | null;
  readonly result?: unknown;
  readonly error?: {
    readonly code: number;
    readonly message: string;
    readonly data?: unknown;
  };
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

export const scheduledPromotionSchema = z.preprocess(
  (val: unknown) => {
    if (val && typeof val === "object") {
      const obj = val as Record<string, unknown>;
      return {
        campaignId: obj.campaignId ?? obj.campaign_id,
        name: obj.name,
        startsAtUnix: obj.startsAtUnix ?? obj.starts_at_unix,
        endsAtUnix: obj.endsAtUnix ?? obj.ends_at_unix,
        discountBps: obj.discountBps ?? obj.discount_bps,
        discountPaise: obj.discountPaise ?? obj.discount_paise,
        fixedPricePaise: obj.fixedPricePaise ?? obj.fixed_price_paise,
        limitedStockAllocated: obj.limitedStockAllocated ?? obj.limited_stock_allocated
      };
    }
    return val;
  },
  z.object({
    campaignId: z.string().min(1),
    name: z.string().min(1),
    startsAtUnix: z.number().int().positive(),
    endsAtUnix: z.number().int().positive(),
    discountBps: z.number().int().min(0).max(10000).optional(),
    discountPaise: z.number().int().min(0).optional(),
    fixedPricePaise: z.number().int().min(0).optional(),
    limitedStockAllocated: z.number().int().min(0).optional()
  })
);

export const catalogSkuItemSchema = z.preprocess(
  (val: unknown) => {
    if (val && typeof val === "object") {
      const obj = val as Record<string, unknown>;
      return {
        ...obj,
        name: obj.name ?? obj.title ?? obj.skuId,
        volumeTiers: obj.volumeTiers ?? [],
        promotions: obj.promotions ?? []
      };
    }
    return val;
  },
  z.object({
    skuId: z.string().min(1),
    name: z.string().min(1),
    category: z.string().min(1),
    description: z.string().min(1),
    hsnCode: z.string().regex(/^[0-9]{4,8}$/),
    gstRatePercent: z.number().min(0).max(100),
    baseUnitPricePaise: z.number().int().min(0),
    availableStock: z.number().int().min(0),
    volumeTiers: z.array(volumeTierSchema),
    promotions: z.array(scheduledPromotionSchema).optional(),
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
  })
);

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
  /**
   * `reason` is appended when the pincode is well-formed but unusable -- an unmapped prefix, say.
   * Only err.message reaches an MCP agent, so the distinction has to live in the message.
   */
  constructor(pincode: string, reason?: string) {
    super(
      reason === undefined
        ? `Invalid delivery pincode provided: ${pincode}`
        : `Invalid delivery pincode provided: ${pincode} -- ${reason}`
    );
    this.name = "InvalidPincodeException";
  }
}
