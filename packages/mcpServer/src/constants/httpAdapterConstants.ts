// REST face of the MCP tool layer. The MCP server itself speaks JSON-RPC over stdio; these
// constants describe the parallel HTTP surface that the buyer SDKs target, so that
// `RazorAgentClient.getLiveSkuQuote` / `reserveInventoryLock` / `verifyShippingSla` have
// something to reach. The route strings must stay identical to `buyerSdkTs/src/sdkConstants.ts`
// (endpointQuote / endpointLock / endpointSla) and to `buyerSdkPy`'s equivalents.

export const defaultHttpPort = 4001;
export const httpPortEnvVar = "PORT";
export const httpBindHost = "0.0.0.0";

export const routeHealth = "/health";
export const routeQuote = "/api/v1/quote";
export const routeLock = "/api/v1/lock";
export const routeSla = "/api/v1/sla";
export const routeRpc = "/rpc";
export const routeToolsManifest = "/api/v1/tools";
// The MCP Streamable HTTP transport. Unlike /rpc this carries the full session lifecycle, so a
// spec-compliant client can connect by URL alone.
export const routeMcp = "/mcp";

export const methodGet = "GET";
export const methodPost = "POST";
export const methodOptions = "OPTIONS";
export const methodDelete = "DELETE";

export const statusOk = 200;
export const statusBadRequest = 400;
export const statusNotFound = 404;
export const statusMethodNotAllowed = 405;
export const statusConflict = 409;
export const statusPayloadTooLarge = 413;
export const statusUnprocessable = 422;
export const statusServerError = 500;
export const statusNoContent = 204;
// A JSON-RPC notification carries no reply. Over HTTP that is 202 with an empty body.
export const statusAccepted = 202;

export const headerContentType = "Content-Type";
export const headerAllowOrigin = "Access-Control-Allow-Origin";
export const headerAllowMethods = "Access-Control-Allow-Methods";
export const headerAllowHeaders = "Access-Control-Allow-Headers";
export const headerExposeHeaders = "Access-Control-Expose-Headers";
export const headerMaxAge = "Access-Control-Max-Age";

// Node lowercases incoming header names, so this is the key to read off request.headers.
export const sessionHeaderName = "mcp-session-id";

export const mediaTypeJson = "application/json";
export const corsAllowAllOrigins = "*";
export const corsAllowedMethods = "GET, POST, DELETE, OPTIONS";
export const corsAllowedHeaders =
  "Content-Type, Accept, Mcp-Session-Id, Mcp-Protocol-Version, Last-Event-ID, " +
  "X-Pow-Challenge, X-Pow-Solution, X-Buyer-Agent-Did, X-Escrow-Token";
// A browser-based MCP client cannot read the session id it was issued unless it is exposed.
export const corsExposedHeaders = "Mcp-Session-Id";
export const corsPreflightMaxAgeSeconds = "86400";

// Bengaluru 560001 -- consistent with `defaultMerchantState = "KA"` in protocolConstants.ts.
// The SLA tool needs an origin to compute a courier zone, but the SDK's `verifyShippingSla`
// only supplies the destination, so the adapter supplies the merchant's own origin.
export const defaultOriginPincode = "560001";

export const maxRequestBodyBytes = 1_048_576;

export const healthStatusOk = "ok";
export const errorFieldName = "error";
export const errorDetailFieldName = "detail";
