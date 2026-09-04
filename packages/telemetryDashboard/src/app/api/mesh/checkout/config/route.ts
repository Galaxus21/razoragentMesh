// GET /api/mesh/checkout/config -> proxies to mandateEngine /api/v1/checkout/config.
//
// Exists so the checkout page can open Razorpay's modal on an order the mandate engine already
// created during an agent settlement. The publishable key id is the one thing the browser needs
// and the one thing it cannot derive; fetching it here keeps the dashboard free of any Razorpay
// configuration of its own, exactly as the order proxy beside it does.

import { resolveServiceUrls } from "@/server/protocolDriver/driverConfig";

export const runtime = "nodejs";
export const dynamic = "force-dynamic";

const configEndpointPath = "/api/v1/checkout/config";
const upstreamTimeoutMs = 10_000;

export async function GET(): Promise<Response> {
  const { mandateEngineUrl } = resolveServiceUrls();

  try {
    const upstream = await fetch(`${mandateEngineUrl}${configEndpointPath}`, {
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
      },
      { status: 502 }
    );
  }
}
