// Records what the SDK actually did, without changing what it does.
//
// The recording hook is `RazorAgentClientConfig.customFetch`, which the SDK already supports --
// no forked client, no patched globals. Every request the SDK issues passes through here and is
// captured verbatim, so the dashboard shows the real wire traffic rather than a re-description
// of it.

import {
  canonicalizeJsonString,
  computeMandateHash,
  signatureFieldKeys
} from "@razorpay/agent-buyer-sdk";
import type {
  CryptoArtifact,
  ProtocolStepRecord,
  ProtocolStepStatus,
  SdkCallRecord,
  StepRefusal,
  WireExchange
} from "@/types/protocolRunTypes";

const textEncoder = new TextEncoder();
const redactedHeaderValue = "<redacted>";
const sensitiveHeaderNames: ReadonlySet<string> = new Set([
  "authorization",
  "cookie",
  "set-cookie",
  "x-razorpay-signature"
]);

function collectHeaders(headers: Headers | Readonly<Record<string, string>> | undefined): Record<string, string> {
  const collected: Record<string, string> = {};
  if (!headers) {
    return collected;
  }
  const entries = headers instanceof Headers ? [...headers.entries()] : Object.entries(headers);
  for (const [rawName, rawValue] of entries) {
    const name = rawName.toLowerCase();
    collected[name] = sensitiveHeaderNames.has(name) ? redactedHeaderValue : String(rawValue);
  }
  return collected;
}

function parseBodyText(bodyText: string): unknown {
  if (bodyText.trim().length === 0) {
    return null;
  }
  try {
    return JSON.parse(bodyText);
  } catch {
    return bodyText;
  }
}

export interface RecordingFetch {
  readonly fetchImpl: typeof fetch;
  readonly drainExchanges: () => readonly WireExchange[];
}

export function createRecordingFetch(): RecordingFetch {
  let buffered: WireExchange[] = [];

  const fetchImpl: typeof fetch = async (input, init) => {
    const startedAtMs = performance.now();
    const request = new Request(input as RequestInfo, init);
    // Clone before the SDK's fetch consumes the stream, or the body is gone by capture time.
    const requestBodyText = await request.clone().text();

    const response = await fetch(request);
    const responseBodyText = await response.clone().text();

    buffered.push({
      method: request.method,
      url: request.url,
      requestHeaders: collectHeaders(request.headers),
      requestBody: parseBodyText(requestBodyText),
      statusCode: response.status,
      responseHeaders: collectHeaders(response.headers),
      responseBody: parseBodyText(responseBodyText),
      durationMs: Math.round(performance.now() - startedAtMs)
    });

    return response;
  };

  return {
    fetchImpl,
    drainExchanges: () => {
      const drained = buffered;
      buffered = [];
      return drained;
    }
  };
}

function stripSignatureFields(mandate: Readonly<Record<string, unknown>>): Record<string, unknown> {
  const unsigned: Record<string, unknown> = {};
  for (const [key, value] of Object.entries(mandate)) {
    if (!(signatureFieldKeys as readonly string[]).includes(key)) {
      unsigned[key] = value;
    }
  }
  return unsigned;
}

export interface MandateArtifactParams {
  readonly artifactId: string;
  readonly label: string;
  readonly signerRole: string;
  readonly signerDid: string;
  readonly signatureFieldName: string;
  readonly mandate: Readonly<Record<string, unknown>>;
  readonly linkedHashes?: Readonly<Record<string, string>>;
}

// Exposes exactly the four values a viewer needs to check the signature themselves:
// the unsigned payload, its RFC 8785 canonical form, that form's SHA-256, and the signature.
export function describeMandateArtifact(params: MandateArtifactParams): CryptoArtifact {
  const unsignedPayload = stripSignatureFields(params.mandate);
  const canonicalJson = canonicalizeJsonString(unsignedPayload);
  const signatureHex = String(params.mandate[params.signatureFieldName] ?? "");

  return {
    artifactId: params.artifactId,
    label: params.label,
    signerRole: params.signerRole,
    signerDid: params.signerDid,
    payload: params.mandate,
    canonicalJson,
    canonicalByteLength: textEncoder.encode(canonicalJson).length,
    sha256Digest: computeMandateHash(params.mandate as Record<string, unknown>),
    signatureHex,
    signatureFieldName: params.signatureFieldName,
    ...(params.linkedHashes ? { linkedHashes: params.linkedHashes } : {})
  };
}

export interface StepOutcome {
  readonly status: ProtocolStepStatus;
  readonly artifacts?: readonly CryptoArtifact[];
  readonly refusal?: StepRefusal;
  readonly resultSummary?: Readonly<Record<string, unknown>>;
}

export interface StepDefinition {
  readonly stepId: string;
  readonly title: string;
  readonly narrative: string;
  readonly protocolLayer: string;
  readonly implementedBy: string;
  readonly invariant?: string;
  readonly sdkCall: SdkCallRecord;
}

export function assembleStepRecord(
  definition: StepDefinition,
  ordinal: number,
  outcome: StepOutcome,
  exchanges: readonly WireExchange[],
  durationMs: number
): ProtocolStepRecord {
  return {
    stepId: definition.stepId,
    ordinal,
    title: definition.title,
    narrative: definition.narrative,
    protocolLayer: definition.protocolLayer,
    implementedBy: definition.implementedBy,
    ...(definition.invariant ? { invariant: definition.invariant } : {}),
    sdkCall: definition.sdkCall,
    status: outcome.status,
    durationMs,
    exchanges,
    artifacts: outcome.artifacts ?? [],
    ...(outcome.refusal ? { refusal: outcome.refusal } : {}),
    ...(outcome.resultSummary ? { resultSummary: outcome.resultSummary } : {})
  };
}
