// Service endpoints for the server-side protocol driver.
//
// These are read at REQUEST time (not baked in like NEXT_PUBLIC_*), because the driver runs in
// the Node runtime inside the container, where services are reachable by compose service name
// rather than localhost. The localhost defaults are what a developer running `npm run dev`
// outside Docker needs.

export const mcpServerUrlEnvVar = "MCP_SERVER_URL";
export const mandateEngineUrlEnvVar = "MANDATE_ENGINE_URL";
export const x402GatewayUrlEnvVar = "X402_GATEWAY_URL";
export const merchantApiUrlEnvVar = "MERCHANT_API_URL";
export const qdrantUrlEnvVar = "QDRANT_URL";

export const fallbackMcpServerUrl = "http://localhost:4001";
export const fallbackMandateEngineUrl = "http://localhost:8000";
export const fallbackX402GatewayUrl = "http://localhost:4003";
export const fallbackMerchantApiUrl = "http://localhost:4002";
export const fallbackQdrantUrl = "http://localhost:6333";

export interface DriverServiceUrls {
  readonly mcpServerUrl: string;
  readonly mandateEngineUrl: string;
  readonly x402GatewayUrl: string;
  readonly merchantApiUrl: string;
  readonly qdrantUrl: string;
}

export function resolveServiceUrls(): DriverServiceUrls {
  return {
    mcpServerUrl: process.env[mcpServerUrlEnvVar] || fallbackMcpServerUrl,
    mandateEngineUrl: process.env[mandateEngineUrlEnvVar] || fallbackMandateEngineUrl,
    x402GatewayUrl: process.env[x402GatewayUrlEnvVar] || fallbackX402GatewayUrl,
    // The driver itself never calls the merchant API -- a buyer agent talks to the MCP server,
    // not to the merchant's ingestion surface -- but the protocol map probes it, so its URL is
    // resolved the same way as the rest rather than being hardcoded in the probe.
    merchantApiUrl: process.env[merchantApiUrlEnvVar] || fallbackMerchantApiUrl,
    // The vector index, read directly by /api/mesh/vectors so the map is drawn from the
    // collection itself rather than from anything the mesh reports about it. Reading Qdrant
    // through a service that also writes it would make the picture unfalsifiable.
    qdrantUrl: process.env[qdrantUrlEnvVar] || fallbackQdrantUrl
  };
}

// Demo fixtures for the buyer side of a run. Real values from the mesh (prices, tax, lock
// tokens) are always fetched live -- only the buyer's own inputs are pinned, so a run is
// reproducible without asking the visitor to fill in a form first.
export interface RunParameters {
  readonly skuId: string;
  readonly quantity: number;
  readonly deliveryPincode: string;
  readonly deliveryStateCode: string;
  readonly promoCode?: string;
  readonly maxBudgetPaise: number;
  readonly singleTransactionLimitPaise: number;
  readonly packageWeightGrams: number;
  readonly lockTtlSeconds: number;
}

export const defaultRunParameters: RunParameters = {
  skuId: "SKU-CHAIR-001",
  // Small quantity and a short lock TTL on purpose. Inventory locks are real reservations
  // against real stock, so a demo that reserves 10 units per click exhausts the catalog's 50
  // units after five runs and every later visitor gets HTTP 409. At 2 units on a 30s TTL the
  // stock recycles faster than anyone can click.
  quantity: 2,
  lockTtlSeconds: 30,
  deliveryPincode: "560034",
  deliveryStateCode: "29",
  maxBudgetPaise: 10_000_000,
  singleTransactionLimitPaise: 7_000_000,
  packageWeightGrams: 750
};

// Checksum-valid: the mandate engine enforces the statutory Luhn Mod-36 check digit
// (packages/mandateEngine/tax/gstinValidator.py), so a made-up GSTIN is rejected at
// settlement with HTTP 422. 29 = Karnataka, matching the merchant origin pincode.
export const merchantGstin = "29AAACR5055K1Z3";
export const merchantStateCode = "29";
export const upiCircleDelegationToken = "upi_circle_del_tok_demo_0001";
// Matched against the category the MERCHANT put on the SKU, casefolded on both sides by
// mandateEngine/verification/budgetGate.py::_verifyCategoryAuthorization. The previous pair --
// "furniture" and "office" -- matched no catalog row: the demo SKU SKU-CHAIR-001 is filed under
// "Office Furniture", which is neither. Adding a category here is a change to what the user
// delegates, so it must name a real catalog category rather than a convenient prefix.
export const authorizedCategories: readonly string[] = ["office furniture", "furniture"];
export const demoMerchantAccount = "acc_demoMerchantRazorAgent";
export const demoPaymentId = "pay_demoRunLocal0001";
export const millisPerSecond = 1000;
