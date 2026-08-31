// The method surface the SDK console exposes.
//
// Each descriptor is written against the real signature in
// packages/buyerSdkTs/src/razorAgentClient.ts. Parameter names here are the SDK's own argument
// names, not invented labels, so the generated snippet is code a reader can actually paste.

import type { SdkMethodDescriptor } from "@/types/sdkConsoleTypes";

// Verbatim from the protocol driver's own layer constant
// (src/server/protocolDriver/stepContext.ts) so the console and the playground name the same
// layer identically rather than adding another variant of the numbering.
const mcpDiscoveryLayer = "Layer 1 - MCP discovery";
const clientSourcePath = "packages/buyerSdkTs/src/razorAgentClient.ts";

export const minimumQuantity = 1;
export const maximumQuantity = 5;
export const minimumLockTtlSeconds = 10;
export const maximumLockTtlSeconds = 120;
export const minimumWeightGrams = 1;
export const maximumWeightGrams = 50_000;

export const sdkMethodCatalog: readonly SdkMethodDescriptor[] = [
  {
    methodId: "getLiveSkuQuote",
    methodName: "getLiveSkuQuote",
    label: "Get a live SKU quote",
    summary:
      "Asks the merchant's MCP server what a SKU costs right now, including the HSN code and GST split used later to build the cart mandate.",
    protocolLayer: mcpDiscoveryLayer,
    implementedBy: clientSourcePath,
    transport: "GET /api/v1/quote",
    parameters: [
      {
        name: "skuId",
        label: "SKU id",
        kind: "string",
        isRequired: true,
        defaultValue: "SKU-CHAIR-001",
        helpText: "A SKU from the merchant catalog. Unknown ids come back as HTTP 404.",
      },
      {
        name: "quantity",
        label: "Quantity",
        kind: "number",
        isRequired: true,
        defaultValue: "2",
        helpText: "Units to price. Bulk tiers can change the unit price.",
        minimum: minimumQuantity,
        maximum: maximumQuantity,
      },
      {
        name: "deliveryPincode",
        label: "Delivery pincode",
        kind: "string",
        // Required by QuoteOptions.deliveryPincode and by the MCP quote tool alike: the
        // pincode decides whether the tax split is CGST+SGST or IGST, so a quote cannot be
        // priced without it. Omitting it returns HTTP 422, so the console asks for it rather
        // than letting a visitor discover that the hard way.
        isRequired: true,
        defaultValue: "560034",
        helpText:
          "Required: the pincode decides whether the tax split is CGST+SGST or IGST.",
      },
      {
        name: "promoCode",
        label: "Promo code",
        kind: "string",
        isRequired: false,
        defaultValue: "",
        helpText: "Optional. An unrecognised code is ignored rather than rejected.",
      },
    ],
  },
  {
    methodId: "verifyShippingSla",
    methodName: "verifyShippingSla",
    label: "Verify a shipping SLA",
    summary:
      "Checks whether the merchant can deliver to a pincode at a given parcel weight, and what the courier promise is.",
    protocolLayer: mcpDiscoveryLayer,
    implementedBy: clientSourcePath,
    transport: "GET /api/v1/sla",
    parameters: [
      {
        name: "pincode",
        label: "Destination pincode",
        kind: "string",
        isRequired: true,
        defaultValue: "560034",
        helpText: "Six-digit Indian pincode.",
      },
      {
        name: "weightGrams",
        label: "Parcel weight (grams)",
        kind: "number",
        isRequired: true,
        defaultValue: "750",
        helpText: "Billable weight. Heavier parcels can fall outside the express SLA.",
        minimum: minimumWeightGrams,
        maximum: maximumWeightGrams,
      },
    ],
  },
  {
    methodId: "reserveInventoryLock",
    methodName: "reserveInventoryLock",
    label: "Reserve an inventory lock",
    summary:
      "Takes a real, time-limited reservation against real stock and returns the lock token the cart mandate is bound to. Transparently solves an HTTP 402 proof-of-work challenge if the server issues one. A lock is bound to a price, so this fetches its prerequisite quote first and shows both exchanges.",
    protocolLayer: mcpDiscoveryLayer,
    implementedBy: clientSourcePath,
    transport: "GET /api/v1/quote, then POST /api/v1/lock",
    sideEffectWarning:
      "This one mutates state: it decrements available stock until the TTL expires. Keep the TTL short so the units come back quickly.",
    parameters: [
      {
        name: "skuId",
        label: "SKU id",
        kind: "string",
        isRequired: true,
        defaultValue: "SKU-CHAIR-001",
        helpText: "The SKU to reserve.",
      },
      {
        name: "quantity",
        label: "Quantity",
        kind: "number",
        isRequired: true,
        defaultValue: "1",
        helpText: "Units to hold. HTTP 409 comes back when stock is short.",
        minimum: minimumQuantity,
        maximum: maximumQuantity,
      },
      {
        name: "deliveryPincode",
        label: "Delivery pincode",
        kind: "string",
        isRequired: true,
        defaultValue: "560034",
        helpText: "Used for the prerequisite quote, whose hash the lock is bound to.",
      },
      {
        name: "lockTtlSeconds",
        label: "Lock TTL (seconds)",
        kind: "number",
        isRequired: true,
        defaultValue: "30",
        helpText: "How long the hold lasts before the sweeper returns the stock.",
        minimum: minimumLockTtlSeconds,
        maximum: maximumLockTtlSeconds,
      },
    ],
  },
];

export const sdkMethodsById: Readonly<Record<string, SdkMethodDescriptor>> = Object.fromEntries(
  sdkMethodCatalog.map((method) => [method.methodId, method])
);
