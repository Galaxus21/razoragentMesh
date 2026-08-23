import { CatalogSkuItem } from "../types/mcpToolTypes.js";

export const catalogFixturesOne: readonly CatalogSkuItem[] = [
  {
    skuId: "SKU-CHAIR-001",
    name: "Ergonomic Office Chair Mesh High Back",
    category: "Office Furniture",
    description: "Adjustable lumbar support breathable mesh chair with 3D armrests",
    hsnCode: "94013000",
    gstRatePercent: 18,
    baseUnitPricePaise: 420000,
    availableStock: 50,
    volumeTiers: [
      { minQuantity: 5, discountBps: 300 },
      { minQuantity: 10, discountBps: 500 },
      { minQuantity: 50, discountBps: 1000 }
    ],
    brand: "ErgoComfort",
    weightGrams: 14000,
    dimensionsCm: { length: 65, width: 65, height: 115 },
    originPincode: "560001"
  },
  {
    skuId: "SKU-CHAIR-004",
    name: "Executive Ergonomic Chair Mesh High Back Pro",
    category: "Office Furniture",
    description: "Premium executive mesh chair with synchronous tilt mechanism",
    hsnCode: "94013000",
    gstRatePercent: 18,
    baseUnitPricePaise: 425000,
    availableStock: 100,
    volumeTiers: [
      { minQuantity: 5, discountBps: 300 },
      { minQuantity: 10, discountBps: 500 },
      { minQuantity: 50, discountBps: 1000 }
    ],
    brand: "ErgoComfort",
    weightGrams: 14500,
    dimensionsCm: { length: 66, width: 66, height: 118 },
    originPincode: "560001"
  },
  {
    skuId: "SKU-OIL-201",
    name: "Cold Pressed Peanut Cooking Oil 1L",
    category: "Pantry & Groceries",
    description: "100% pure traditional wood-pressed groundnut oil for commercial kitchens",
    hsnCode: "15089000",
    gstRatePercent: 5,
    baseUnitPricePaise: 28000,
    availableStock: 0,
    volumeTiers: [
      { minQuantity: 10, discountBps: 400 },
      { minQuantity: 50, discountBps: 800 }
    ],
    allergens: ["peanut"],
    brand: "FarmPure",
    weightGrams: 950,
    dimensionsCm: { length: 8, width: 8, height: 26 },
    originPincode: "560001"
  },
  {
    skuId: "SKU-OIL-205",
    name: "Organic Sunflower Cooking Oil 1L",
    category: "Pantry & Groceries",
    description: "Refined cold filtered sunflower edible oil allergen free",
    hsnCode: "15121910",
    gstRatePercent: 5,
    baseUnitPricePaise: 29000,
    availableStock: 40,
    volumeTiers: [
      { minQuantity: 10, discountBps: 400 },
      { minQuantity: 50, discountBps: 800 }
    ],
    allergens: [],
    brand: "SunRich",
    weightGrams: 920,
    dimensionsCm: { length: 8, width: 8, height: 26 },
    originPincode: "560001"
  },
  {
    skuId: "SKU-LAPTOP-101",
    name: "Enterprise Business Laptop 16GB 512GB SSD",
    category: "IT Hardware",
    description: "14 inch FHD Intel Core i7 16GB RAM TPM 2.0 corporate laptop",
    hsnCode: "84713010",
    gstRatePercent: 18,
    baseUnitPricePaise: 6500000,
    availableStock: 15,
    volumeTiers: [
      { minQuantity: 5, discountBps: 400 },
      { minQuantity: 20, discountBps: 800 }
    ],
    brand: "TechMatrix",
    weightGrams: 1400,
    dimensionsCm: { length: 32, width: 22, height: 2 },
    originPincode: "560001"
  },
  {
    skuId: "SKU-LAPTOP-104",
    name: "Executive Business Laptop 16GB 1TB SSD Pro",
    category: "IT Hardware",
    description: "14 inch 2K Intel Core i7 16GB RAM 1TB SSD corporate workstation",
    hsnCode: "84713010",
    gstRatePercent: 18,
    baseUnitPricePaise: 6700000,
    availableStock: 25,
    volumeTiers: [
      { minQuantity: 5, discountBps: 400 },
      { minQuantity: 20, discountBps: 800 }
    ],
    brand: "TechMatrix",
    weightGrams: 1450,
    dimensionsCm: { length: 32, width: 22, height: 2 },
    originPincode: "560001"
  },
  {
    skuId: "SKU-MONITOR-301",
    name: "27-inch 4K UHD IPS Commercial Monitor",
    category: "IT Hardware",
    description: "Color calibrated 4K UHD 60Hz 99% sRGB USB-C 90W PD monitor",
    hsnCode: "85285200",
    gstRatePercent: 18,
    baseUnitPricePaise: 2400000,
    availableStock: 30,
    volumeTiers: [
      { minQuantity: 5, discountBps: 300 },
      { minQuantity: 15, discountBps: 600 }
    ],
    brand: "ViewClear",
    weightGrams: 6200,
    dimensionsCm: { length: 61, width: 20, height: 45 },
    originPincode: "560001"
  },
  {
    skuId: "SKU-KEYBOARD-401",
    name: "Wireless Mechanical Keyboard Hot-Swappable",
    category: "Peripherals",
    description: "Compact 84-key RGB wireless Bluetooth 5.1 mechanical keyboard",
    hsnCode: "84716060",
    gstRatePercent: 18,
    baseUnitPricePaise: 450000,
    availableStock: 60,
    volumeTiers: [
      { minQuantity: 10, discountBps: 500 },
      { minQuantity: 50, discountBps: 1000 }
    ],
    brand: "KeyPulse",
    weightGrams: 850,
    dimensionsCm: { length: 31, width: 12, height: 4 },
    originPincode: "560001"
  },
  {
    skuId: "SKU-MOUSE-501",
    name: "Ergonomic Wireless Rechargeable Mouse",
    category: "Peripherals",
    description: "Silent switch multi-device 4000 DPI ergonomic office mouse",
    hsnCode: "84716060",
    gstRatePercent: 18,
    baseUnitPricePaise: 220000,
    availableStock: 80,
    volumeTiers: [
      { minQuantity: 10, discountBps: 500 },
      { minQuantity: 50, discountBps: 1000 }
    ],
    brand: "KeyPulse",
    weightGrams: 110,
    dimensionsCm: { length: 11, width: 7, height: 4 },
    originPincode: "560001"
  },
  {
    skuId: "SKU-DESK-601",
    name: "Motorized Dual-Motor Height Adjustable Desk 140x70",
    category: "Office Furniture",
    description: "Heavy duty steel frame anti-collision memory preset standing desk",
    hsnCode: "94031000",
    gstRatePercent: 18,
    baseUnitPricePaise: 1850000,
    availableStock: 20,
    volumeTiers: [
      { minQuantity: 5, discountBps: 500 },
      { minQuantity: 10, discountBps: 1000 }
    ],
    brand: "ErgoComfort",
    weightGrams: 32000,
    dimensionsCm: { length: 140, width: 70, height: 72 },
    originPincode: "560001"
  },
  {
    skuId: "SKU-PAPER-701",
    name: "A4 Copier Paper 75GSM 500 Sheets Carton of 5 Reams",
    category: "Office Supplies",
    description: "High brightness acid free multipurpose laser printing paper",
    hsnCode: "48025610",
    gstRatePercent: 12,
    baseUnitPricePaise: 32000,
    availableStock: 500,
    volumeTiers: [
      { minQuantity: 20, discountBps: 500 },
      { minQuantity: 100, discountBps: 1200 }
    ],
    brand: "PaperKraft",
    weightGrams: 2300,
    dimensionsCm: { length: 30, width: 21, height: 5 },
    originPincode: "560001"
  }
];
