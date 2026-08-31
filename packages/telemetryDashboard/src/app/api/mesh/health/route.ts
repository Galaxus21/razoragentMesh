// GET /api/mesh/health -> liveness of every mesh service, probed server-side.

import { probeMeshServices } from "@/server/meshHealth/probeMeshServices";

export const runtime = "nodejs";
// A cached health report is a wrong health report.
export const dynamic = "force-dynamic";

export async function GET(): Promise<Response> {
  const services = await probeMeshServices();
  return Response.json({ services, probedAtMs: Date.now() });
}
