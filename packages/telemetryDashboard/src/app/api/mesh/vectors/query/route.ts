// POST /api/mesh/vectors/query -> runs a real query against the vector index.
//
// Two modes, both forwarded to the merchant API rather than reimplemented here:
//
//   search : POST /api/v1/catalog/search  -- the same route a buyer agent's search_catalog call
//            reaches, so the scores on the map are the scores that decide a purchase.
//   heal   : POST /api/v1/catalog/heal-oos -- Layer 3's substitution search.
//
// The dashboard cannot embed a query itself. fastembed is Python and lives in the merchant API;
// reimplementing MiniLM in the browser to draw a picture would produce a second, disagreeing
// embedder, and the picture would stop describing the mesh.

import { resolveServiceUrls } from "@/server/protocolDriver/driverConfig";
import {
  defaultMaxPriceDeltaPercent,
  defaultSearchLimit,
  defaultSimilarityFloor,
  maxSearchLimit,
  vectorUpstreamTimeoutMs
} from "@/constants/vectorIndexConstants";

export const runtime = "nodejs";
export const dynamic = "force-dynamic";

const searchPath = "/api/v1/catalog/search";
const healPath = "/api/v1/catalog/heal-oos";
const maxQueryLength = 500;

function badRequest(detail: string): Response {
  return Response.json({ error: "InvalidRequest", detail }, { status: 400 });
}

async function forward(path: string, body: unknown): Promise<Response> {
  const { merchantApiUrl } = resolveServiceUrls();
  try {
    const upstream = await fetch(`${merchantApiUrl}${path}`, {
      method: "POST",
      headers: { "Content-Type": "application/json" },
      body: JSON.stringify(body),
      signal: AbortSignal.timeout(vectorUpstreamTimeoutMs)
    });
    const text = await upstream.text();
    // Transparent on purpose: a 422 naming the offending field is the only useful diagnostic
    // when the request shape drifts, and both upstream models are extra="forbid".
    return new Response(text, {
      status: upstream.status,
      headers: { "Content-Type": upstream.headers.get("content-type") ?? "application/json" }
    });
  } catch (error: unknown) {
    const detail = error instanceof Error ? error.message : String(error);
    return Response.json({ error: "MeshUnreachable", detail }, { status: 502 });
  }
}

export async function POST(request: Request): Promise<Response> {
  let body: Record<string, unknown>;
  try {
    body = (await request.json()) as Record<string, unknown>;
  } catch {
    return badRequest("Request body is not valid JSON.");
  }

  const mode = body.mode;

  if (mode === "search") {
    const queryText = body.queryText;
    if (typeof queryText !== "string" || queryText.trim().length === 0) {
      return badRequest("queryText is required and must be a non-empty string.");
    }
    if (queryText.length > maxQueryLength) {
      return badRequest(`queryText must be at most ${maxQueryLength} characters.`);
    }
    const requestedLimit = typeof body.limit === "number" ? body.limit : defaultSearchLimit;
    const limit = Math.min(Math.max(Math.trunc(requestedLimit), 1), maxSearchLimit);
    return forward(searchPath, { queryText: queryText.trim(), limit });
  }

  if (mode === "heal") {
    const failedSkuId = body.failedSkuId;
    if (typeof failedSkuId !== "string" || failedSkuId.trim().length === 0) {
      return badRequest("failedSkuId is required and must be a non-empty string.");
    }
    const requestedQuantity =
      typeof body.requestedQuantity === "number" && body.requestedQuantity > 0
        ? Math.trunc(body.requestedQuantity)
        : 1;
    return forward(healPath, {
      failedSkuId: failedSkuId.trim(),
      requestedQuantity,
      similarityFloor: defaultSimilarityFloor,
      maxPriceDeltaPercent: defaultMaxPriceDeltaPercent
    });
  }

  return badRequest('mode must be "search" or "heal".');
}
