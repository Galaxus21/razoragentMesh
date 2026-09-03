// GET/PUT /api/mesh/policy -> the merchant API's negotiation-policy surface, proxied server-side.
//
// Sibling of ../catalog/route.ts and exists for the same reason: the browser cannot reach the
// merchant API directly (inside Docker it is a compose service name, and the dashboard origin is
// port 3000 with no rewrites), so the hop has to happen where MERCHANT_API_URL is meaningful.
//
// What this carries is the merchant's opt-in. Negotiation is off for every merchant until a
// policy with negotiationEnabled arrives here, so without this route the Studio could publish a
// SKU but never authorise a single bid against it -- the switch existed only in a Redis key
// nothing in the UI could write.

import { resolveServiceUrls } from "@/server/protocolDriver/driverConfig";

export const runtime = "nodejs";
// The response reports whether the mesh accepted this specific policy, so it must never be
// served from cache.
export const dynamic = "force-dynamic";

const policyPathPrefix = "/api/v1/merchant";
const policyPathSuffix = "/policy";
const upstreamTimeoutMs = 10_000;

interface ProxyFailure {
  readonly error: string;
  readonly detail: string;
}

function badRequest(detail: string): Response {
  return Response.json({ error: "InvalidRequest", detail } satisfies ProxyFailure, {
    status: 400
  });
}

/**
 * Forwards to the merchant API and returns its real status and body.
 *
 * Transparent on purpose. NegotiationPolicy is extra="forbid", so a 422 names the offending
 * field, and a 404 from GET means "this merchant has not configured a policy" -- which is the
 * default state and something the panel needs to render as "not enabled" rather than as an error.
 */
async function forwardToMerchantApi(
  method: "GET" | "PUT",
  path: string,
  body?: unknown
): Promise<Response> {
  const { merchantApiUrl } = resolveServiceUrls();
  const target = `${merchantApiUrl}${path}`;

  try {
    const upstream = await fetch(target, {
      method,
      headers: { "Content-Type": "application/json" },
      ...(body !== undefined ? { body: JSON.stringify(body) } : {}),
      signal: AbortSignal.timeout(upstreamTimeoutMs)
    });

    const text = await upstream.text();
    return new Response(text, {
      status: upstream.status,
      headers: { "Content-Type": upstream.headers.get("content-type") ?? "application/json" }
    });
  } catch (error: unknown) {
    const detail = error instanceof Error ? error.message : String(error);
    return Response.json(
      {
        error: "MeshUnreachable",
        detail: `Could not reach the merchant API at ${merchantApiUrl}: ${detail}`
      } satisfies ProxyFailure,
      { status: 502 }
    );
  }
}

function buildPolicyPath(merchantDid: string): string {
  return `${policyPathPrefix}/${encodeURIComponent(merchantDid)}${policyPathSuffix}`;
}

/** GET /api/mesh/policy?merchantDid=.. */
export async function GET(request: Request): Promise<Response> {
  const merchantDid = new URL(request.url).searchParams.get("merchantDid");
  if (!merchantDid) {
    return badRequest("The merchantDid query parameter is required.");
  }
  return forwardToMerchantApi("GET", buildPolicyPath(merchantDid));
}

/**
 * PUT /api/mesh/policy
 *
 * The merchantDid is read out of the body and used to build the path, mirroring the catalog
 * proxy, so the caller states it once and the two cannot disagree.
 */
export async function PUT(request: Request): Promise<Response> {
  let policy: unknown;
  try {
    policy = await request.json();
  } catch {
    return badRequest("Request body is not valid JSON.");
  }

  if (policy === null || typeof policy !== "object") {
    return badRequest("The policy body must be a JSON object.");
  }
  const merchantDid = (policy as Record<string, unknown>).merchantDid;
  if (typeof merchantDid !== "string" || merchantDid.trim().length === 0) {
    return badRequest("The policy must carry a non-empty merchantDid.");
  }

  return forwardToMerchantApi("PUT", buildPolicyPath(merchantDid), policy);
}
