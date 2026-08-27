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
  readonly bullionPricing: BullionPricingFormData;
  readonly selectedFacet: DomainFacetType;
  readonly jewelryFacet: JewelryFacetFormData;
  readonly apparelFacet: ApparelFacetFormData;
  readonly pharmaFacet: PharmaFacetFormData;
  readonly fmcgFacet: FmcgFacetFormData;
}

export type CatalogSubmissionStatus = "idle" | "submitting" | "success" | "error" | "offline";

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
  readonly jewelryFacet?: JewelryFacetPayload;
  readonly apparelFacet?: ApparelFacetPayload;
  readonly pharmaFacet?: PharmaFacetPayload;
  readonly fmcgFacet?: FmcgFacetPayload;
}
