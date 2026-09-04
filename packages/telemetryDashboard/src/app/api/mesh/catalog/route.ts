// POST/DELETE /api/mesh/catalog -> the merchant API's catalog surface, proxied server-side.
//
// Why this exists: Merchant Studio's "Publish to Mesh" has never worked. It POSTed the relative
// path /api/v1/merchant/{did}/catalog, which resolves against the DASHBOARD origin (port 3000),
// and next.config.ts declares no rewrites -- so every publish hit a Next 404 and the merchant
// API never saw a listing. The browser cannot call port 4002 directly either: inside Docker the
// merchant API is reachable by compose service name, not by a URL a browser could resolve.
//
// So the hop has to happen server-side, where MERCHANT_API_URL is meaningful. The URL is
// resolved through the driver's existing resolveServiceUrls() rather than a second resolver,
// so the dashboard cannot end up with two disagreeing ideas of where the mesh lives.

import { resolveServiceUrls } from "@/server/protocolDriver/driverConfig";

export const runtime = "nodejs";
// A publish must never be served from cache: the response reports whether the mesh accepted
// this specific listing.
export const dynamic = "force-dynamic";

const catalogPathPrefix = "/api/v1/merchant";
const catalogPathSuffix = "/catalog";
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
 * Deliberately transparent: a 422 from the merchant API must reach the operator as a 422 with
 * its validation detail intact. The schema is extra="forbid", so its rejection text names the
 * offending field -- swallowing it would hide the only useful diagnostic.
 */
async function forwardToMerchantApi(
  method: "GET" | "POST" | "DELETE",
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
    // The mesh being unreachable is a real failure and is reported as one. The previous
    // client-side handler reported this case as "Validated payload synthesized and ready for
    // deployment", which read like success.
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

function readMerchantDid(value: unknown): string | undefined {
  if (value === null || typeof value !== "object") {
    return undefined;
  }
  const candidate = (value as Record<string, unknown>).merchantDid;
  return typeof candidate === "string" && candidate.trim().length > 0 ? candidate : undefined;
}

/**
 * GET /api/mesh/catalog?merchantDid=..
 *
 * Lists what this merchant has actually published. The human checkout page used to carry its
 * product list as a hard-coded array, so a SKU a judge authored in Merchant Studio and published
 * successfully was nowhere to be found on the page that sells it -- the publish looked like it
 * had silently failed. This is the read side that array was standing in for.
 */
export async function GET(request: Request): Promise<Response> {
  const merchantDid = new URL(request.url).searchParams.get("merchantDid");
  if (!merchantDid) {
    return badRequest("The merchantDid query parameter is required.");
  }

  const path = `${catalogPathPrefix}/${encodeURIComponent(merchantDid)}${catalogPathSuffix}`;
  return forwardToMerchantApi("GET", path);
}

export async function POST(request: Request): Promise<Response> {
  let listing: unknown;
  try {
    listing = await request.json();
  } catch {
    return badRequest("Request body is not valid JSON.");
  }

  const merchantDid = readMerchantDid(listing);
  if (!merchantDid) {
    return badRequest("The listing must carry a non-empty merchantDid.");
  }

  const path =
    `${catalogPathPrefix}/${encodeURIComponent(merchantDid)}${catalogPathSuffix}`;
  return forwardToMerchantApi("POST", path, listing);
}

/**
 * DELETE /api/mesh/catalog?merchantDid=..&skuId=..
 *
 * Present so a demo can be run more than once: every publish creates a real SKU that a buyer
 * agent can lock stock against, and without a way to remove them the catalog fills up with
 * rehearsal data.
 */
export async function DELETE(request: Request): Promise<Response> {
  const params = new URL(request.url).searchParams;
  const merchantDid = params.get("merchantDid");
  const skuId = params.get("skuId");

  if (!merchantDid || !skuId) {
    return badRequest("Both merchantDid and skuId query parameters are required.");
  }

  const path =
    `${catalogPathPrefix}/${encodeURIComponent(merchantDid)}` +
    `${catalogPathSuffix}/${encodeURIComponent(skuId)}`;
  return forwardToMerchantApi("DELETE", path);
}
