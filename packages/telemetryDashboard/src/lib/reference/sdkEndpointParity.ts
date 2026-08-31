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
}

// `export const routeQuote = "/api/v1/quote";` and `export const endpointQuote = "/api/v1/quote" as const;`
const typeScriptRoutePattern = /export const (\w+)\s*=\s*"([^"]+)"/g;
// `endpointLiveSkuQuote: str = "/api/v1/quotes/live"`
const pythonRoutePattern = /^(\w+)\s*:\s*str\s*=\s*"([^"]+)"/gm;
const routePrefix = "/";

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
// three FastAPI services' from the committed OpenAPI dump.
export function collectServedRoutes(): ReadonlySet<string> {
  const served = new Set<string>();
  for (const route of readMatches(
    "packages/mcpServer/src/constants/httpAdapterConstants.ts",
    typeScriptRoutePattern,
    "route"
  ).values()) {
    served.add(route);
  }
  for (const service of loadHttpApiReference().services) {
    for (const operation of service.operations) {
      served.add(operation.path);
    }
  }
  return served;
}

export function collectEndpointCallers(): readonly EndpointCaller[] {
  const callers: EndpointCaller[] = [];
  for (const [constantName, route] of readMatches(
    "packages/buyerSdkTs/src/sdkConstants.ts",
    typeScriptRoutePattern,
    "endpoint"
  )) {
    callers.push({ sdk: "buyerSdkTs", constantName, route });
  }
  for (const [constantName, route] of readMatches(
    "packages/buyerSdkPy/razoragent_buyer_sdk/constants.py",
    pythonRoutePattern,
    "endpoint"
  )) {
    callers.push({ sdk: "buyerSdkPy", constantName, route });
  }
  return callers.sort((left, right) => left.constantName.localeCompare(right.constantName));
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
  return collectEndpointCallers().filter(
    (caller) => ![...served].some((servedRoute) => isServedBy(caller.route, servedRoute))
  );
}
