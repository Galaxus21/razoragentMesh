import {
  ApparelGender,
  DomainFacetType,
  JewelryPurityCarat,
  MakingChargesType,
  MerchantCatalogFormData,
  OracleFeedSymbol,
} from "@/types/merchantCatalogTypes";

export const defaultGstRatePercent = 18;
export const defaultMinOrderQuantity = 1;
export const defaultQuoteTtlSeconds = 60;
export const minVolumeQuantity = 1;
export const maxDiscountBps = 10000;
export const minQuoteTtlSeconds = 10;
export const maxQuoteTtlSeconds = 300;
export const paisePerInrUnit = 100;

export const hsnGstLookupTable: Readonly<Record<string, number>> = {
  "7113": 3,
  "7114": 3,
  "7118": 3,
  "6109": 5,
  "6110": 12,
  "6203": 12,
  "4820": 12,
  "9503": 12,
  "3004": 12,
  "3002": 5,
  "1508": 5,
  "1511": 5,
  "0401": 0,
  "4901": 0,
  "8471": 18,
  "8517": 18,
  "9403": 18,
  "9401": 18,
  "2106": 18,
  "3401": 18,
  "6402": 18,
  "6403": 18,
};

export const categoryOptions: ReadonlyArray<string> = [
  "Jewelry",
  "Apparel",
  "Pharma",
  "FMCG",
  "Electronics",
  "Furniture",
  "General",
];

export const gstRateOptions: ReadonlyArray<number> = [0, 3, 5, 12, 18, 28];

export interface OracleFeedOption {
  readonly symbol: OracleFeedSymbol;
  readonly label: string;
  readonly defaultPurity: number;
}

export const oracleFeedOptions: ReadonlyArray<OracleFeedOption> = [
  {
    symbol: "MCX_GOLD_24K_INR_PER_GRAM",
    label: "MCX Gold 24K (99.9% Purity)",
    defaultPurity: 1.0,
  },
  {
    symbol: "MCX_GOLD_22K_INR_PER_GRAM",
    label: "MCX Gold 22K (91.67% Purity)",
    defaultPurity: 0.9167,
  },
  {
    symbol: "MCX_SILVER_INR_PER_KG",
    label: "MCX Silver 999 (99.9% Purity)",
    defaultPurity: 0.999,
  },
];

export interface PurityChoice {
  readonly carat: JewelryPurityCarat;
  readonly label: string;
  readonly multiplier: number;
}

export const metalPurityChoices: ReadonlyArray<PurityChoice> = [
  { carat: 24, label: "24 Karat (99.9% Pure)", multiplier: 1.0 },
  { carat: 22, label: "22 Karat (91.67% Pure)", multiplier: 0.9167 },
  { carat: 18, label: "18 Karat (75.0% Pure)", multiplier: 0.75 },
];

export interface HsnPresetOption {
  readonly hsn: string;
  readonly description: string;
  readonly gstRate: number;
  readonly category: string;
}

export const hsnPresetOptions: ReadonlyArray<HsnPresetOption> = [
  { hsn: "71131910", description: "Gold Jewelry (22K/24K)", gstRate: 3, category: "Jewelry" },
  { hsn: "71131120", description: "Silver Jewelry (925 Sterling)", gstRate: 3, category: "Jewelry" },
  { hsn: "61091000", description: "Cotton T-Shirts & Polos", gstRate: 5, category: "Apparel" },
  { hsn: "62034200", description: "Men Cotton Trousers", gstRate: 12, category: "Apparel" },
  { hsn: "30049099", description: "Pharmaceutical Formulations", gstRate: 12, category: "Pharma" },
  { hsn: "21069099", description: "Packaged FMCG Food Products", gstRate: 18, category: "FMCG" },
  { hsn: "84713010", description: "Laptops & Microcomputers", gstRate: 18, category: "Electronics" },
  { hsn: "94033010", description: "Wooden Office Furniture", gstRate: 18, category: "Furniture" },
];

export const facetTabOptions: ReadonlyArray<{ readonly type: DomainFacetType; readonly label: string }> = [
  { type: "none", label: "Standard (No Facet)" },
  { type: "jewelry", label: "Jewelry" },
  { type: "apparel", label: "Apparel" },
  { type: "pharma", label: "Pharma" },
  { type: "fmcg", label: "FMCG" },
];

export const apparelGenderOptions: ReadonlyArray<{ readonly value: ApparelGender; readonly label: string }> = [
  { value: "UNISEX", label: "Unisex" },
  { value: "M", label: "Men" },
  { value: "F", label: "Women" },
];

export const makingChargesTypeOptions: ReadonlyArray<{ readonly value: MakingChargesType; readonly label: string }> = [
  { value: "FIXED_PAISE", label: "Fixed Amount (INR)" },
  { value: "PERCENTAGE_OF_GOLD", label: "Percentage of Gold Value" },
];

export const defaultCatalogFormState: MerchantCatalogFormData = {
  skuId: "",
  merchantDid: "",
  title: "",
  description: "",
  category: "General",
  hsnCode: "",
  gstRatePercent: defaultGstRatePercent,
  basePriceInr: "",
  availableStock: 0,
  originPincode: "",
  currency: "INR",
  minimumOrderQuantity: defaultMinOrderQuantity,
  volumeTiers: [],
  bullionPricing: {
    enabled: false,
    oracleFeedSymbol: "MCX_GOLD_24K_INR_PER_GRAM",
    purityMultiplier: 1.0,
    netWeightGrams: 0,
    makingChargesInr: "0.00",
    makingChargesType: "FIXED_PAISE",
    stoneChargesInr: "0.00",
    maxQuoteTtlSeconds: defaultQuoteTtlSeconds,
  },
  selectedFacet: "none",
  jewelryFacet: {
    purityCarat: 22,
    grossWeightGrams: 0,
    hallmarkNumber: "",
  },
  apparelFacet: {
    size: "M",
    color: "",
    fabric: [],
    fitType: "Regular Fit",
    gender: "UNISEX",
  },
  pharmaFacet: {
    activeSalt: "",
    dosageMg: 0,
    schedule: "OTC",
    prescriptionRequired: false,
  },
  fmcgFacet: {
    allergens: [],
    shelfLifeDays: 180,
    isVeg: true,
    fssaiNumber: "",
  },
};
