// POST /api/demo/invoke -> run one buyer-SDK method and return what it did.
//
// Node runtime, like /api/demo/run: the buyer SDK is imported directly here. A single JSON
// response rather than a stream, because one call has one result.

import { NextRequest } from "next/server";
import {
  InvalidSdkParametersError,
  UnknownSdkMethodError,
  invokeSdkMethod,
} from "@/server/sdkConsole/invokeSdkMethod";
import type { SdkInvocationRequest } from "@/types/sdkConsoleTypes";

export const runtime = "nodejs";
// Every invocation hits live services; a cached response would show stale wire traffic.
export const dynamic = "force-dynamic";

const badRequestStatus = 400;
const notFoundStatus = 404;
const unprocessableStatus = 422;
const serverErrorStatus = 500;

export async function POST(request: NextRequest): Promise<Response> {
  let body: Partial<SdkInvocationRequest>;
  try {
    body = (await request.json()) as Partial<SdkInvocationRequest>;
  } catch {
    return Response.json({ error: "Request body must be JSON" }, { status: badRequestStatus });
  }

  if (!body.methodId) {
    return Response.json({ error: "methodId is required" }, { status: badRequestStatus });
  }

  try {
    const result = await invokeSdkMethod({
      methodId: body.methodId,
      parameters: body.parameters ?? {},
    });
    return Response.json(result);
  } catch (error) {
    if (error instanceof UnknownSdkMethodError) {
      return Response.json({ error: error.message }, { status: notFoundStatus });
    }
    if (error instanceof InvalidSdkParametersError) {
      return Response.json(
        { error: error.message, violations: error.violations },
        { status: unprocessableStatus }
      );
    }
    const failure = error as Error;
    return Response.json({ error: failure.message }, { status: serverErrorStatus });
  }
}
