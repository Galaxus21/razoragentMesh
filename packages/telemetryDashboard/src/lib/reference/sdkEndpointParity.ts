// Checks that every route the buyer SDKs call is a route some service actually serves.
//
// Both SDKs are tested against mocks -- `httpx.MockTransport` on the Python side, an injected
// `customFetch` on the TypeScript side -- which is fast and hermetic and completely blind to this
// question. A mock answers whatever path the client asks for, so a client aimed at a route that
// no service exposes passes its own suite forever. `test_razorAgentClient.py:29` goes further and
// asserts the wrong path, freezing the mistake in place as if it were the contract.
//
// So the comparison has to come from outside both suites: the routes are read from the servers'
// own constants and from the generated OpenAPI reference, and the callers are read from each
// SDK's constants file. Nothing here mocks anything, and nothing here trusts a test.

import fs from "node:fs";
import path from "node:path";
import { loadHttpApiReference } from "@/lib/reference/referenceTables";

export interface EndpointCaller {
  readonly sdk: string;
  readonly constantName: string;
  readonly route: string;
  readonly service: string;
}

// `export const routeQuote = "/api/v1/quote";` and `export const endpointQuote = "/api/v1/quote" as const;`
const typeScriptRoutePattern = /export const (\w+)\s*=\s*"([^"]+)"/g;
// `endpointLiveSkuQuote: str = "/api/v1/quotes/live"`
const pythonRoutePattern = /^(\w+)\s*:\s*str\s*=\s*"([^"]+)"/gm;
const routePrefix = "/";
// Stands in for "no service", so an unrouted constant is reported rather than silently matched.
export const unroutedService = "unrouted";

function resolveRepositoryRoot(): string {
  // Tests and scripts both run from the dashboard package root, which is two levels below the
  // repository root -- the same assumption scripts/generateExampleSnippets.ts makes.
  return path.resolve(process.cwd(), "..", "..");
}

function readMatches(filePath: string, pattern: RegExp, prefix: string): Map<string, string> {
  const absolutePath = path.join(resolveRepositoryRoot(), filePath);
  if (!fs.existsSync(absolutePath)) {
    throw new Error(`${filePath} is missing, so SDK endpoint parity cannot be checked`);
  }
  const source = fs.readFileSync(absolutePath, "utf-8");
  const found = new Map<string, string>();
  for (const match of source.matchAll(pattern)) {
    if (match[1].startsWith(prefix) && match[2].startsWith(routePrefix)) {
      found.set(match[1], match[2]);
    }
  }
  return found;
}

// Every path any service answers on: the MCP server's routes come from its own constants, the
// three FastAPI services' from the committed OpenAPI dump. Returns a map keyed by serviceId so
// that callers can be matched against the routes of the service they actually address.
export function collectServedRoutes(): ReadonlyMap<string, ReadonlySet<string>> {
  const served = new Map<string, Set<string>>();
  const mcpRoutes = new Set<string>();
  for (const route of readMatches(
    "packages/mcpServer/src/constants/httpAdapterConstants.ts",
    typeScriptRoutePattern,
    "route"
  ).values()) {
    mcpRoutes.add(route);
  }
  served.set("mcpServer", mcpRoutes);
  for (const service of loadHttpApiReference().services) {
    const serviceRoutes = new Set<string>();
    for (const operation of service.operations) {
      serviceRoutes.add(operation.path);
    }
    served.set(service.serviceId, serviceRoutes);
  }
  return served;
}

export function collectEndpointCallers(): readonly EndpointCaller[] {
  const routing = collectClientRouting();
  const callers: EndpointCaller[] = [];
  const declared: Array<[sdk: string, file: string, pattern: RegExp]> = [
    ["buyerSdkTs", "packages/buyerSdkTs/src/sdkConstants.ts", typeScriptRoutePattern],
    ["buyerSdkPy", "packages/buyerSdkPy/razoragent_buyer_sdk/constants.py", pythonRoutePattern],
  ];
  for (const [sdk, file, pattern] of declared) {
    for (const [constantName, route] of readMatches(file, pattern, "endpoint")) {
      // `unrouted` when the client declares the constant but never routes it. That is a real
      // finding, not a gap in this check: `_resolveUrl` raises NetworkClientError for exactly
      // such an endpoint, so the call could never have reached any service.
      const service = routing.get(`${sdk}:${constantName}`) ?? unroutedService;
      callers.push({ sdk, constantName, route, service });
    }
  }
  return callers.sort((left, right) => left.constantName.localeCompare(right.constantName));
}

// Which service each SDK actually addresses, READ FROM THE CLIENTS THEMSELVES.
//
// Restating the routing here as a literal table would defeat the check. The whole point of the
// host-aware comparison is to catch an SDK aimed at the wrong service; a hand-maintained copy of
// the routing would keep answering with the OLD host after the SDK changed, and the guard would
// go on passing while the client was broken -- the same shape of failure as the path-only version
// it replaced. So the mapping is parsed out of each client's own source, and a client that stops
// declaring its routing fails loudly rather than falling back to an assumption.

// `(endpointSettlementExecute, config.gatewayBaseUrl),` inside `_serviceRoutingTable`.
const pythonRoutingPattern = /\(\s*(endpoint\w+)\s*,\s*(?:config\.)?(\w+)\s*\)/g;
// `const url = `${this._mcpServerUrl}${endpointQuote}`` in each client method.
const typeScriptRoutingPattern = /\$\{this\.(_\w+Url)\}\$\{(endpoint\w+)\}/g;

// The base-URL identifier each client uses, to the serviceId the OpenAPI dump publishes.
const baseUrlToService: ReadonlyMap<string, string> = new Map([
  ["gatewayBaseUrl", "mandateEngine"],
  ["mcpBaseUrl", "mcpServer"],
  ["merchantApiBaseUrl", "merchantApi"],
  ["x402GatewayBaseUrl", "x402Gateway"],
  ["_mandateEngineUrl", "mandateEngine"],
  ["_mcpServerUrl", "mcpServer"],
  ["_merchantApiUrl", "merchantApi"],
  ["_x402GatewayUrl", "x402Gateway"],
]);

function readSource(filePath: string): string {
  const absolutePath = path.join(resolveRepositoryRoot(), filePath);
  if (!fs.existsSync(absolutePath)) {
    throw new Error(`${filePath} is missing, so SDK endpoint parity cannot be checked`);
  }
  return fs.readFileSync(absolutePath, "utf-8");
}

// `mcpBaseUrl = config.mcpBaseUrl or config.gatewayBaseUrl` -- the Python client aliases the
// config fields locally, so resolve an alias back to the config field it was assigned from.
function resolvePythonAliases(source: string): ReadonlyMap<string, string> {
  const aliases = new Map<string, string>();
  for (const match of source.matchAll(/^\s*(\w+)\s*=\s*config\.(\w+)/gm)) {
    aliases.set(match[1], match[2]);
  }
  return aliases;
}

function collectClientRouting(): ReadonlyMap<string, string> {
  const routing = new Map<string, string>();

  const pythonSource = readSource("packages/buyerSdkPy/razoragent_buyer_sdk/razorAgentClient.py");
  const aliases = resolvePythonAliases(pythonSource);
  for (const match of pythonSource.matchAll(pythonRoutingPattern)) {
    const baseUrlName = aliases.get(match[2]) ?? match[2];
    const service = baseUrlToService.get(baseUrlName);
    if (service) {
      routing.set(`buyerSdkPy:${match[1]}`, service);
    }
  }

  const typeScriptSource = readSource("packages/buyerSdkTs/src/razorAgentClient.ts");
  for (const match of typeScriptSource.matchAll(typeScriptRoutingPattern)) {
    const service = baseUrlToService.get(match[1]);
    if (service) {
      routing.set(`buyerSdkTs:${match[2]}`, service);
    }
  }

  if (routing.size === 0) {
    throw new Error(
      "No service routing could be read from either SDK client. The parity check cannot tell " +
      "which host a caller addresses, so it would pass vacuously."
    );
  }
  return routing;
}

// A templated FastAPI path (`/api/v1/alerts/price-drop/{alertId}`) is served for every concrete
// id, so a caller naming the un-templated prefix is matched against the segment before the brace.
function isServedBy(route: string, servedRoute: string): boolean {
  if (route === servedRoute) {
    return true;
  }
  const braceIndex = servedRoute.indexOf("{");
  return braceIndex > 0 && route === servedRoute.slice(0, braceIndex - 1);
}

export function findUnservedCallers(): readonly EndpointCaller[] {
  const served = collectServedRoutes();
  return collectEndpointCallers().filter((caller) => {
    // Get the routes served by this caller's target service
    const serviceRoutes = served.get(caller.service);
    if (!serviceRoutes) {
      return true; // Unserved: the service itself doesn't exist
    }
    // Check if the caller's route is served by this service
    return ![...serviceRoutes].some((servedRoute) => isServedBy(caller.route, servedRoute));
  });
}
