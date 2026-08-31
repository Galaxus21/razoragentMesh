// Resolves the URLs the guides print against the ports and routes the services actually serve.
//
// Two different mistakes live here. The first is a port: onboarding.mdx configured the SDK with
// mcpServerUrl "http://localhost:8001" and x402GatewayUrl "http://localhost:8000" -- both real
// ports of other things, so the reader gets a connection that succeeds and then behaves
// strangely. The second is a path: a curl against a route the service does not expose.
//
// Only ports the registry knows are checked. A snippet pointing at localhost:6379 is talking to
// Redis, and this file has no opinion about Redis.

import type { HttpApiReference, HttpServiceSurface } from "@/types/referenceTypes";
import type { CodeFence, SnippetFinding } from "@/types/docSnippetTypes";
import type { SnippetFacts } from "@/lib/reference/docSnippetExtractor";
import { meshServiceRegistry, meshServicesById } from "@/constants/meshServiceRegistry";

// Which SDK configuration key is meant to address which service. The SDK takes three separate
// URLs rather than one base, so a value swapped between two of these keys is invisible to the
// type system -- both sides are strings.
const sdkUrlKeyToServiceId: Readonly<Record<string, string>> = {
  mcpServerUrl: "mcpServer",
  mcp_server_url: "mcpServer",
  merchantApiUrl: "merchantApi",
  merchant_api_url: "merchantApi",
  mandateEngineUrl: "mandateEngine",
  mandate_engine_url: "mandateEngine",
  x402GatewayUrl: "x402Gateway",
  x402_gateway_url: "x402Gateway",
  // The Python client takes the same four addresses under different names, on a config
  // object rather than on the client itself. Its gatewayBaseUrl is the Mandate Engine.
  gatewayBaseUrl: "mandateEngine",
  mcpBaseUrl: "mcpServer",
  merchantApiBaseUrl: "merchantApi",
  x402GatewayBaseUrl: "x402Gateway",
};

const urlPortPattern = /localhost:(\d+)/;
// Trailing punctuation is prose bleeding into the match: "curl localhost:4002/health." ends a
// sentence, and the full stop is not part of the route.
// Colons belong in the path class: merchant routes are addressed by DID, and
// /api/v1/merchant/did:razoragent:merchant:9f8e/policy is one path segment, not four.
const documentUrlPattern = /localhost:(\d+)(\/[\w\-/{}.:]*)/g;
const trailingPunctuation = /[.,;:)"'`]+$/;
const pathParameterSegment = /^\{.+\}$/;

function readPort(url: string): number | null {
  const match = urlPortPattern.exec(url);
  return match ? Number(match[1]) : null;
}

export function checkServiceUrls(fence: CodeFence, facts: SnippetFacts): readonly SnippetFinding[] {
  const findings: SnippetFinding[] = [];

  for (const serviceUrl of facts.serviceUrls) {
    const serviceId = sdkUrlKeyToServiceId[serviceUrl.key];
    const service = serviceId ? meshServicesById[serviceId] : undefined;
    const port = readPort(serviceUrl.url);
    if (!service || port === null || port === service.composePort) {
      continue;
    }
    const occupant = meshServiceRegistry.find((entry) => entry.composePort === port);
    findings.push({
      sourcePath: fence.sourcePath,
      line: fence.line,
      message:
        `${serviceUrl.key} points at port ${port}, but ${service.displayName} listens on ` +
        `${service.composePort}` +
        (occupant ? ` -- ${port} is ${occupant.displayName}` : ""),
    });
  }
  return findings;
}

function pathMatchesOperation(documentedPath: string, operationPath: string): boolean {
  const documented = documentedPath.split("/");
  const operation = operationPath.split("/");
  if (documented.length !== operation.length) {
    return false;
  }
  return operation.every(
    (segment, index) => pathParameterSegment.test(segment) || segment === documented[index]
  );
}

// One line per path, not one per operation: GET, PUT and DELETE on the same route are the same
// answer to "does this URL exist".
function describeRoutes(service: HttpServiceSurface): string {
  return [...new Set(service.operations.map((operation) => operation.path))].join(", ");
}

function describeService(reference: HttpApiReference, port: number): HttpServiceSurface | undefined {
  const service = meshServiceRegistry.find((entry) => entry.composePort === port);
  return service
    ? reference.services.find((candidate) => candidate.serviceId === service.serviceId)
    : undefined;
}

// Scans the whole document, not just its fences: the URL a reader copies is as likely to be in a
// `curl` line or a sentence as in a typed snippet.
export function checkDocumentedEndpoints(
  sourcePath: string,
  body: string,
  reference: HttpApiReference
): readonly SnippetFinding[] {
  const findings: SnippetFinding[] = [];

  body.split("\n").forEach((text, index) => {
    for (const match of text.matchAll(documentUrlPattern)) {
      const port = Number(match[1]);
      const documentedPath = match[2].replace(trailingPunctuation, "");
      const service = describeService(reference, port);
      // No OpenAPI document for that port means nothing to check against: the MCP server speaks
      // JSON-RPC over one route, and the dashboard is a Next.js app.
      if (!service || documentedPath.length <= 1) {
        continue;
      }
      const matched = service.operations.some((operation) =>
        pathMatchesOperation(documentedPath, operation.path)
      );
      if (!matched) {
        findings.push({
          sourcePath,
          line: index + 1,
          message:
            `localhost:${port}${documentedPath} is not a route ${service.title} serves. ` +
            `Its routes are: ${describeRoutes(service)}`,
        });
      }
    }
  });

  return findings;
}
