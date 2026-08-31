// POST /api/demo/run -> SSE stream of protocol run events.
//
// Runs in the Node runtime (not edge) because the driver imports the buyer SDK, which uses
// tweetnacl and Node crypto. Streaming rather than returning a single JSON blob so a visitor
// watches the protocol advance step by step instead of staring at a spinner.

import { NextRequest } from "next/server";
import { runScenario } from "@/server/protocolDriver/runScenario";
import { mirrorStepToTelemetryBus } from "@/server/protocolDriver/telemetryMirror";
import type { RunParameters } from "@/server/protocolDriver/driverConfig";

export const runtime = "nodejs";
// A run performs live network calls; a cached response would replay stale wire traffic and
// defeat the entire point of the page.
export const dynamic = "force-dynamic";

const sseContentType = "text/event-stream; charset=utf-8";
const sseDataPrefix = "data: ";
const sseFrameSuffix = "\n\n";

interface RunRequestBody {
  readonly scenarioId?: string;
  readonly parameters?: Partial<RunParameters>;
}

function encodeSseFrame(payload: unknown): Uint8Array {
  return new TextEncoder().encode(`${sseDataPrefix}${JSON.stringify(payload)}${sseFrameSuffix}`);
}

export async function POST(request: NextRequest): Promise<Response> {
  let body: RunRequestBody = {};
  try {
    body = (await request.json()) as RunRequestBody;
  } catch {
    return Response.json({ error: "Request body must be JSON" }, { status: 400 });
  }

  const scenarioId = body.scenarioId;
  if (!scenarioId) {
    return Response.json({ error: "scenarioId is required" }, { status: 400 });
  }

  const stream = new ReadableStream<Uint8Array>({
    async start(controller) {
      try {
        for await (const event of runScenario({ scenarioId, parameters: body.parameters })) {
          controller.enqueue(encodeSseFrame(event));
          if (event.type === "STEP_COMPLETED") {
            // Not awaited: mirroring must never add latency to the visible run.
            void mirrorStepToTelemetryBus(event.runId, event.step);
          }
        }
      } catch (error) {
        const failure = error as Error;
        controller.enqueue(
          encodeSseFrame({ type: "RUN_ERROR", runId: "", message: failure.message })
        );
      } finally {
        controller.close();
      }
    }
  });

  return new Response(stream, {
    headers: {
      "Content-Type": sseContentType,
      "Cache-Control": "no-cache, no-transform",
      Connection: "keep-alive"
    }
  });
}
