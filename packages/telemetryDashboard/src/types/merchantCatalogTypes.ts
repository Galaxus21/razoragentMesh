export type TabIdentifier = "telemetryMesh" | "merchantSkuStudio";

export type DomainFacetType = "none" | "jewelry" | "apparel" | "pharma" | "fmcg";

export type OracleFeedSymbol =
  | "MCX_GOLD_24K_INR_PER_GRAM"
  | "MCX_GOLD_22K_INR_PER_GRAM"
  | "MCX_SILVER_INR_PER_KG";

export type MakingChargesType = "FIXED_PAISE" | "PERCENTAGE_OF_GOLD";

export type ApparelGender = "M" | "F" | "UNISEX";

export type JewelryPurityCarat = 18 | 22 | 24;

export interface VolumeTierInput {
  readonly minQuantity: number;
  readonly discountBps: number;
}

/**
 * Which of the three discount shapes a promotion uses. ScheduledPromotionSchema accepts
 * discountBps, discountPaise or fixedPricePaise and requires at least one, so the form asks
 * which one rather than showing three fields and hoping the merchant fills exactly one in.
 */
export type PromotionDiscountKind = "PERCENT" | "FLAT_OFF" | "FIXED_PRICE";

/**
 * A scheduled flash sale, in the shape the form holds it. Amounts are rupee strings here and
 * become paise in the payload, matching how basePriceInr is handled.
 *
 * This is what get_live_sku_quote reports as `upcoming_promotions` with an expected_savings_paise
 * -- the "wait for the sale" advice a buyer agent gives. The backend has supported it from the
 * start; until now the Studio could not author one, so it could only be demonstrated by posting
 * raw JSON to the merchant API.
 */
export interface ScheduledPromotionInput {
  readonly campaignId: string;
  readonly name: string;
  readonly startsAtUnix: number;
  readonly endsAtUnix: number;
  readonly discountKind: PromotionDiscountKind;
  readonly discountBps: number;
  readonly discountInr: string;
  readonly fixedPriceInr: string;
  /** 0 means unlimited. The backend omits the field entirely rather than sending a zero. */
  readonly limitedStockAllocated: number;
}

export interface BullionPricingFormData {
  readonly enabled: boolean;
  readonly oracleFeedSymbol: OracleFeedSymbol;
  readonly purityMultiplier: number;
  readonly netWeightGrams: number;
  readonly makingChargesInr: string;
  readonly makingChargesType: MakingChargesType;
  readonly stoneChargesInr: string;
  readonly maxQuoteTtlSeconds: number;
}

export interface JewelryFacetFormData {
  readonly purityCarat: JewelryPurityCarat;
  readonly grossWeightGrams: number;
  readonly hallmarkNumber: string;
}

export interface ApparelFacetFormData {
  readonly size: string;
  readonly color: string;
  readonly fabric: string[];
  readonly fitType: string;
  readonly gender: ApparelGender;
}

export interface PharmaFacetFormData {
  readonly activeSalt: string;
  readonly dosageMg: number;
  readonly schedule: string;
  readonly prescriptionRequired: boolean;
}

export interface FmcgFacetFormData {
  readonly allergens: string[];
  readonly shelfLifeDays: number;
  readonly isVeg: boolean;
  readonly fssaiNumber: string;
}

export interface MerchantCatalogFormData {
  readonly skuId: string;
  readonly merchantDid: string;
  readonly title: string;
  readonly description: string;
  readonly category: string;
  readonly hsnCode: string;
  readonly gstRatePercent: number;
  readonly basePriceInr: string;
  readonly availableStock: number;
  readonly originPincode: string;
  readonly currency: "INR";
  readonly minimumOrderQuantity: number;
  readonly volumeTiers: ReadonlyArray<VolumeTierInput>;
  readonly promotions: ReadonlyArray<ScheduledPromotionInput>;
  readonly offers: MerchantOffersFormData;
  readonly bullionPricing: BullionPricingFormData;
  readonly selectedFacet: DomainFacetType;
  readonly jewelryFacet: JewelryFacetFormData;
  readonly apparelFacet: ApparelFacetFormData;
  readonly pharmaFacet: PharmaFacetFormData;
  readonly fmcgFacet: FmcgFacetFormData;
}

/**
 * The offers a merchant writes for one SKU: their own campaign, their own UPI cashback, and
 * their own promo codes.
 *
 * Until this existed, three of the four discount types a quote applies were global constants in
 * the MCP server -- one festive percentage, one cashback amount, one corporate promo code --
 * identical for every SKU in the mesh and unwritable by any merchant. Only volume tiers and
 * scheduled sales were genuinely theirs.
 */
export interface MerchantPromoCodeInput {
  readonly code: string;
  readonly discountBps: number;
  readonly label: string;
}

export interface MerchantOffersFormData {
  /** Off means "do not send merchantOffers at all", which keeps the mesh's default offers. */
  readonly authorOffers: boolean;
  readonly campaignEnabled: boolean;
  readonly campaignLabel: string;
  readonly campaignDiscountBps: number;
  /** Blank is uncapped. Not the same as "0", which caps the campaign at nothing. */
  readonly campaignCapInr: string;
  readonly paymentRailCashbackInr: string;
  readonly promoCodes: ReadonlyArray<MerchantPromoCodeInput>;
}

export interface MerchantPromoCodePayload {
  readonly code: string;
  readonly discountBps: number;
  readonly label?: string;
}

export interface MerchantOffersPayload {
  readonly campaign?: {
    readonly label?: string;
    readonly discountBps: number;
    readonly capPaise?: number;
  };
  readonly paymentRailCashbackPaise?: number;
  readonly promoCodes: ReadonlyArray<MerchantPromoCodePayload>;
}

// No "offline" state: a publish either reached the mesh or it did not, and the dashboard
// knows which. The removed state reported a failed publish as an amber warning reading
// "Validated payload synthesized and ready for deployment", which a merchant reads as success.
export type CatalogSubmissionStatus = "idle" | "submitting" | "success" | "error";

export interface CatalogSubmissionResult {
  readonly status: CatalogSubmissionStatus;
  readonly message: string;
  readonly skuId?: string;
  readonly merchantDid?: string;
  readonly timestampMs?: number;
}

export type FormValidationErrors = Record<string, string>;

export interface FormValidationResult {
  readonly isValid: boolean;
  readonly errors: FormValidationErrors;
}

export interface DynamicPricingRulePayload {
  readonly pricingType: "STATIC" | "FORMULA_SPOT_LINKED";
  readonly oracleFeedSymbol?: OracleFeedSymbol;
  readonly purityMultiplier?: string;
  readonly netWeightGrams?: string;
  readonly makingChargesPaise?: number;
  readonly makingChargesType?: MakingChargesType;
  readonly stoneChargesPaise?: number;
  readonly maxQuoteTtlSeconds?: number;
}

export interface JewelryFacetPayload {
  readonly purityCarat: JewelryPurityCarat;
  readonly grossWeightGrams: string;
  readonly hallmarkNumber: string;
  readonly dynamicPricingRule?: DynamicPricingRulePayload;
}

export interface ApparelFacetPayload {
  readonly size: string;
  readonly color: string;
  readonly fabric: ReadonlyArray<string>;
  readonly fitType: string;
  readonly gender: ApparelGender;
}

export interface PharmaFacetPayload {
  readonly activeSalt: string;
  readonly dosageMg: number;
  readonly schedule: string;
  readonly prescriptionRequired: boolean;
}

export interface FmcgFacetPayload {
  readonly allergens: ReadonlyArray<string>;
  readonly shelfLifeDays: number;
  readonly isVeg: boolean;
  readonly fssaiNumber: string;
}

export interface ScheduledPromotionPayload {
  readonly campaignId: string;
  readonly name: string;
  readonly startsAtUnix: number;
  readonly endsAtUnix: number;
  readonly discountBps?: number;
  readonly discountPaise?: number;
  readonly fixedPricePaise?: number;
  readonly limitedStockAllocated?: number;
}

export interface UniversalProductListingPayload {
  readonly skuId: string;
  readonly merchantDid: string;
  readonly title: string;
  readonly description: string;
  readonly category: string;
  readonly hsnCode: string;
  readonly gstRatePercent: number;
  readonly baseUnitPricePaise: number;
  readonly availableStock: number;
  readonly originPincode: string;
  readonly currency: "INR";
  readonly minimumOrderQuantity: number;
  readonly volumeTiers: ReadonlyArray<{
    readonly minQuantity: number;
    readonly discountBps: number;
  }>;
  /**
   * Omitted entirely when empty rather than sent as []. ScheduledPromotionSchema's parent is
   * extra="forbid" and each optional discount field is dropped unless it is the one in use, so
   * the payload carries exactly the keys the backend model declares.
   */
  readonly promotions?: ReadonlyArray<ScheduledPromotionPayload>;
  /**
   * Omitted unless the merchant actually authored something. Presence is a complete statement:
   * a listing that carries merchantOffers gets exactly what it declares, so sending an empty
   * object would silently switch off the campaign and cashback the mesh applies by default.
   */
  readonly merchantOffers?: MerchantOffersPayload;
  readonly jewelryFacet?: JewelryFacetPayload;
  readonly apparelFacet?: ApparelFacetPayload;
  readonly pharmaFacet?: PharmaFacetPayload;
  readonly fmcgFacet?: FmcgFacetPayload;
}
