// Executes one buyer-SDK method against the live mesh and records what it did.
//
// This runs the real `RazorAgentClient`, not a re-implementation of it: the console's whole
// purpose is to show the SDK working, so anything it displays has to come from the SDK. The
// recording hook is the same `customFetch` the protocol driver uses, which means the console
// and the playground capture wire traffic identically.

import { RazorAgentClient } from "@razorpay/agent-buyer-sdk";
import { resolveServiceUrls } from "@/server/protocolDriver/driverConfig";
import { createRecordingFetch } from "@/server/protocolDriver/stepRecorder";
import { sdkMethodsById } from "@/constants/sdkConsoleCatalog";
import { validateSdkParameters } from "@/lib/sdkParameterValidation";
import type { FieldViolation } from "@/lib/sdkParameterValidation";
import type {
  SdkInvocationRequest,
  SdkInvocationResult,
} from "@/types/sdkConsoleTypes";

export class UnknownSdkMethodError extends Error {
  public constructor(methodId: string) {
    super(`Unknown SDK method: ${methodId}`);
    this.name = "UnknownSdkMethodError";
  }
}

export class InvalidSdkParametersError extends Error {
  public readonly violations: readonly FieldViolation[];

  public constructor(violations: readonly FieldViolation[]) {
    super("One or more parameters are invalid");
    this.name = "InvalidSdkParametersError";
    this.violations = violations;
  }
}

type InvocationValues = Readonly<Record<string, string | number>>;

async function dispatchMethod(
  client: RazorAgentClient,
  methodId: string,
  values: InvocationValues
): Promise<unknown> {
  if (methodId === "getLiveSkuQuote") {
    return client.getLiveSkuQuote(String(values.skuId), Number(values.quantity), {
      // Required by the SDK and by the MCP tool. The catalog marks it isRequired, so
      // validateSdkParameters has already rejected the invocation if it is absent.
      deliveryPincode: String(values.deliveryPincode),
      ...(values.promoCode ? { promoCode: String(values.promoCode) } : {}),
    });
  }
  if (methodId === "verifyShippingSla") {
    return client.verifyShippingSla(String(values.pincode), Number(values.weightGrams));
  }
  if (methodId === "reserveInventoryLock") {
    // A lock cannot be taken on its own: the MCP tool requires the quote_hash that binds the
    // reservation to a specific price, and rejects the request with HTTP 422 without it.
    // LockOptions.quoteHash is typed required to match that contract, and the hash is only
    // knowable from a quote. So the console fetches the prerequisite quote and shows BOTH
    // exchanges, rather than
    // hiding the dependency behind one button and reporting a confusing 422.
    const quote = await client.getLiveSkuQuote(String(values.skuId), Number(values.quantity), {
      deliveryPincode: String(values.deliveryPincode),
    });
    return client.reserveInventoryLock(String(values.skuId), Number(values.quantity), {
      lockTtlSeconds: Number(values.lockTtlSeconds),
      quoteHash: quote.quoteHash,
    });
  }
  throw new UnknownSdkMethodError(methodId);
}

export async function invokeSdkMethod(
  request: SdkInvocationRequest
): Promise<SdkInvocationResult> {
  const method = sdkMethodsById[request.methodId];
  if (!method) {
    throw new UnknownSdkMethodError(request.methodId);
  }

  const { violations, values } = validateSdkParameters(method, request.parameters ?? {});
  if (violations.length > 0) {
    throw new InvalidSdkParametersError(violations);
  }

  const { mcpServerUrl, mandateEngineUrl, x402GatewayUrl } = resolveServiceUrls();
  const recorder = createRecordingFetch();
  const client = new RazorAgentClient({
    mcpServerUrl,
    mandateEngineUrl,
    x402GatewayUrl,
    customFetch: recorder.fetchImpl,
  });

  const startedAtMs = performance.now();
  try {
    const returnValue = await dispatchMethod(client, request.methodId, values);
    return {
      methodId: method.methodId,
      methodName: method.methodName,
      status: "SUCCEEDED",
      durationMs: Math.round(performance.now() - startedAtMs),
      argumentSummary: values,
      exchanges: recorder.drainExchanges(),
      returnValue,
    };
  } catch (error) {
    // A rejected call is still a result worth showing -- a 404 for an unknown SKU or a 409 for
    // exhausted stock is the mesh behaving correctly, and the recorded exchange proves it. So
    // this is reported as a completed invocation with a failure, not as a broken page.
    const failure = error as Error & { statusCode?: number };
    return {
      methodId: method.methodId,
      methodName: method.methodName,
      status: "FAILED",
      durationMs: Math.round(performance.now() - startedAtMs),
      argumentSummary: values,
      exchanges: recorder.drainExchanges(),
      failure: {
        errorName: failure.name || "Error",
        message: failure.message,
        ...(failure.statusCode ? { statusCode: failure.statusCode } : {}),
      },
    };
  }
}
