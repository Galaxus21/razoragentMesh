// POST /api/mesh/checkout/verify -> proxies to mandateEngine /api/v1/checkout/verify.
//
// Forwards the payment signature verification payload to the mandate engine's
// HMAC-SHA256 enclave where server credentials are safely held.

import { resolveServiceUrls } from "@/server/protocolDriver/driverConfig";

export const runtime = "nodejs";
export const dynamic = "force-dynamic";

const verifyEndpointPath = "/api/v1/checkout/verify";
const upstreamTimeoutMs = 10_000;

interface ProxyFailure {
  readonly error: string;
  readonly detail: string;
}

export async function POST(request: Request): Promise<Response> {
  const { mandateEngineUrl } = resolveServiceUrls();
  const target = `${mandateEngineUrl}${verifyEndpointPath}`;

  let body: unknown;
  try {
    body = await request.json();
  } catch {
    return Response.json(
      { error: "InvalidRequest", detail: "Request body is not valid JSON." } satisfies ProxyFailure,
      { status: 400 }
    );
  }

  try {
    const upstream = await fetch(target, {
      method: "POST",
      headers: { "Content-Type": "application/json" },
      body: JSON.stringify(body),
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
        detail: `Could not reach the mandate engine at ${mandateEngineUrl}: ${detail}`
      } satisfies ProxyFailure,
      { status: 502 }
    );
  }
}
