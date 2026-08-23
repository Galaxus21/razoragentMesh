import { CatalogSkuItem } from "../types/mcpToolTypes.js";

export const catalogFixturesTwo: readonly CatalogSkuItem[] = [
  {
    skuId: "SKU-COFFEE-801",
    name: "Roasted Arabica Coffee Beans 1kg Espresso Roast",
    category: "Pantry & Groceries",
    description: "Single origin Coorg shade grown medium dark roast whole beans",
    hsnCode: "09012100",
    gstRatePercent: 5,
    baseUnitPricePaise: 120000,
    availableStock: 120,
    volumeTiers: [
      { minQuantity: 10, discountBps: 500 },
      { minQuantity: 30, discountBps: 1000 }
    ],
    brand: "CoorgRoast",
    weightGrams: 1050,
    dimensionsCm: { length: 12, width: 8, height: 28 },
    originPincode: "560001"
  },
  {
    skuId: "SKU-TEA-802",
    name: "Assam Orthodox Whole Leaf Black Tea 1kg",
    category: "Pantry & Groceries",
    description: "TGFOP premium golden tippy whole leaf aromatic export grade tea",
    hsnCode: "09024020",
    gstRatePercent: 5,
    baseUnitPricePaise: 85000,
    availableStock: 90,
    volumeTiers: [
      { minQuantity: 10, discountBps: 500 },
      { minQuantity: 30, discountBps: 1000 }
    ],
    brand: "AssamSelect",
    weightGrams: 1050,
    dimensionsCm: { length: 12, width: 8, height: 26 },
    originPincode: "560001"
  },
  {
    skuId: "SKU-CABLE-901",
    name: "Cat6 Ethernet Patch Cable 5m Snagless Shielded",
    category: "Networking",
    description: "Gigabit 550MHz 24AWG pure bare copper RJ45 patch cord",
    hsnCode: "85444999",
    gstRatePercent: 18,
    baseUnitPricePaise: 35000,
    availableStock: 200,
    volumeTiers: [
      { minQuantity: 20, discountBps: 600 },
      { minQuantity: 50, discountBps: 1200 }
    ],
    brand: "NetLink",
    weightGrams: 180,
    dimensionsCm: { length: 15, width: 10, height: 3 },
    originPincode: "560001"
  },
  {
    skuId: "SKU-ROUTER-902",
    name: "Dual-Band Gigabit Enterprise WiFi 6 Router AX3000",
    category: "Networking",
    description: "MU-MIMO OFDMA WPA3 VLAN multi-SSID enterprise gateway",
    hsnCode: "85176290",
    gstRatePercent: 18,
    baseUnitPricePaise: 890000,
    availableStock: 35,
    volumeTiers: [
      { minQuantity: 5, discountBps: 400 },
      { minQuantity: 15, discountBps: 800 }
    ],
    brand: "NetLink",
    weightGrams: 750,
    dimensionsCm: { length: 24, width: 16, height: 5 },
    originPincode: "560001"
  },
  {
    skuId: "SKU-TONER-903",
    name: "Black High-Yield Laser Toner Cartridge 5000 Pages",
    category: "Office Supplies",
    description: "OEM compatible smudge resistant high density black toner",
    hsnCode: "84439950",
    gstRatePercent: 18,
    baseUnitPricePaise: 380000,
    availableStock: 45,
    volumeTiers: [
      { minQuantity: 5, discountBps: 500 },
      { minQuantity: 20, discountBps: 1000 }
    ],
    brand: "PrintMax",
    weightGrams: 920,
    dimensionsCm: { length: 32, width: 11, height: 16 },
    originPincode: "560001"
  },
  {
    skuId: "SKU-BOX-1001",
    name: "Heavy Duty Corrugated Shipping Boxes 3-Ply Pack of 25",
    category: "Packaging",
    description: "12x10x8 inch kraft paper brown packing boxes for e-commerce dispatch",
    hsnCode: "48191010",
    gstRatePercent: 18,
    baseUnitPricePaise: 95000,
    availableStock: 150,
    volumeTiers: [
      { minQuantity: 10, discountBps: 600 },
      { minQuantity: 50, discountBps: 1500 }
    ],
    brand: "PackPro",
    weightGrams: 4200,
    dimensionsCm: { length: 50, width: 35, height: 25 },
    originPincode: "560001"
  },
  {
    skuId: "SKU-TAPE-1002",
    name: "Industrial Packaging Tape Transparent 65m Pack of 6",
    category: "Packaging",
    description: "48mm wide 50 micron high tack BOPP sealing adhesive tape",
    hsnCode: "39191000",
    gstRatePercent: 18,
    baseUnitPricePaise: 42000,
    availableStock: 220,
    volumeTiers: [
      { minQuantity: 10, discountBps: 500 },
      { minQuantity: 50, discountBps: 1200 }
    ],
    brand: "PackPro",
    weightGrams: 1100,
    dimensionsCm: { length: 12, width: 12, height: 28 },
    originPincode: "560001"
  },
  {
    skuId: "SKU-SANITIZER-1101",
    name: "WHO Formulation 80% Alcohol Hand Sanitizer 5L Can",
    category: "Hygiene & Safety",
    description: "Instant germ protection liquid disinfectant with moisturizers",
    hsnCode: "38089400",
    gstRatePercent: 18,
    baseUnitPricePaise: 110000,
    availableStock: 75,
    volumeTiers: [
      { minQuantity: 5, discountBps: 500 },
      { minQuantity: 20, discountBps: 1000 }
    ],
    brand: "PureGuard",
    weightGrams: 4600,
    dimensionsCm: { length: 18, width: 14, height: 30 },
    originPincode: "560001"
  },
  {
    skuId: "SKU-HEADSET-1201",
    name: "Enterprise USB ANC Wired Headset Dual Ear",
    category: "Peripherals",
    description: "Noise cancelling microphone inline call controls for call centers",
    hsnCode: "85183000",
    gstRatePercent: 18,
    baseUnitPricePaise: 520000,
    availableStock: 50,
    volumeTiers: [
      { minQuantity: 10, discountBps: 500 },
      { minQuantity: 30, discountBps: 1000 }
    ],
    brand: "SoundWave",
    weightGrams: 210,
    dimensionsCm: { length: 18, width: 16, height: 6 },
    originPincode: "560001"
  },
  {
    skuId: "SKU-SERVER-1301",
    name: "Enterprise Rackmount Server 1U 64GB ECC 2x1TB NVMe",
    category: "IT Hardware",
    description: "Dual 16-core Xeon Silver redundant 550W PSU server chassis",
    hsnCode: "84715000",
    gstRatePercent: 18,
    baseUnitPricePaise: 18000000,
    availableStock: 8,
    volumeTiers: [
      { minQuantity: 2, discountBps: 400 },
      { minQuantity: 5, discountBps: 800 }
    ],
    brand: "CoreServe",
    weightGrams: 16000,
    dimensionsCm: { length: 65, width: 44, height: 4 },
    originPincode: "560001"
  },
  {
    skuId: "SKU-UPS-1401",
    name: "Online UPS 2kVA Pure Sine Wave Double Conversion",
    category: "Power Solutions",
    description: "LCD display SNMP management smart battery charger enterprise UPS",
    hsnCode: "85044090",
    gstRatePercent: 18,
    baseUnitPricePaise: 2250000,
    availableStock: 12,
    volumeTiers: [
      { minQuantity: 2, discountBps: 300 },
      { minQuantity: 5, discountBps: 600 }
    ],
    brand: "VoltSafe",
    weightGrams: 19500,
    dimensionsCm: { length: 42, width: 19, height: 32 },
    originPincode: "560001"
  }
];
