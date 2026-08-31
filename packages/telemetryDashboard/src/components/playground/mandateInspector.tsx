"use client";

import React, { useState } from "react";
import { KeyRound, ShieldAlert, ShieldCheck } from "lucide-react";
import {
  AgentKeyManager,
  canonicalizeJsonString,
  computeSha256Digest,
  extractPublicKeyFromDid
} from "@razorpay/agent-buyer-sdk";
import {
  verifyFailLabel,
  verifyIdleLabel,
  verifyPassLabel
} from "@/constants/playgroundConstants";
import type { CryptoArtifact } from "@/types/protocolRunTypes";

// The verification below runs in the VISITOR'S browser, using the same
// @razorpay/agent-buyer-sdk functions the server used to produce the signature -- not a
// re-implementation. That is only possible because the SDK is isomorphic (see
// packages/buyerSdkTs/src/isomorphicCrypto.ts); it previously imported node:crypto and could
// not be bundled for a browser at all.

export interface MandateInspectorProps {
  readonly artifact: CryptoArtifact;
}

type VerificationState = "IDLE" | "PASSED" | "FAILED";

interface VerificationOutcome {
  readonly state: VerificationState;
  readonly recomputedDigest: string;
  readonly detail: string;
}

const idleOutcome: VerificationOutcome = { state: "IDLE", recomputedDigest: "", detail: "" };

function runBrowserVerification(artifact: CryptoArtifact): VerificationOutcome {
  try {
    // 1. Re-canonicalise the payload here rather than trusting the canonicalJson we were sent.
    const unsignedPayload = { ...(artifact.payload as Record<string, unknown>) };
    delete unsignedPayload[artifact.signatureFieldName];
    const recanonicalised = canonicalizeJsonString(unsignedPayload);
    const recomputedDigest = computeSha256Digest(recanonicalised);

    if (recomputedDigest !== artifact.sha256Digest) {
      return {
        state: "FAILED",
        recomputedDigest,
        detail: `Digest mismatch. The payload does not hash to the digest that was signed, so the mandate was altered after signing. Expected ${artifact.sha256Digest}, recomputed ${recomputedDigest}.`
      };
    }

    // 2. Verify the Ed25519 signature against the public key embedded in the signer's DID.
    const publicKeyHex = extractPublicKeyFromDid(artifact.signerDid);
    const verifier = new AgentKeyManager();
    const isSignatureValid = verifier.verifyPayloadSignature(
      unsignedPayload,
      artifact.signatureHex,
      publicKeyHex
    );

    return isSignatureValid
      ? {
          state: "PASSED",
          recomputedDigest,
          detail: `Recomputed the canonical form, hashed it, and checked the Ed25519 signature against the public key in ${artifact.signerDid.slice(0, 24)}… — all in this tab.`
        }
      : {
          state: "FAILED",
          recomputedDigest,
          detail: "The digest matches but the Ed25519 signature does not verify against the signer's public key."
        };
  } catch (error) {
    const failure = error as Error;
    return { state: "FAILED", recomputedDigest: "", detail: failure.message };
  }
}

function PipelineRow({
  stageLabel,
  children
}: {
  readonly stageLabel: string;
  readonly children: React.ReactNode;
}): React.JSX.Element {
  return (
    <div className="grid grid-cols-[128px_minmax(0,1fr)] gap-3 py-2 border-b border-borderSubtle last:border-b-0">
      <span className="text-label-caps uppercase text-textMuted pt-0.5">{stageLabel}</span>
      <div className="min-w-0">{children}</div>
    </div>
  );
}

export function MandateInspector({ artifact }: MandateInspectorProps): React.JSX.Element {
  const [outcome, setOutcome] = useState<VerificationOutcome>(idleOutcome);

  const badgeClass =
    outcome.state === "PASSED"
      ? "bg-statusSuccess/10 text-statusSuccess border-statusSuccess/30"
      : "bg-statusError/10 text-statusError border-statusError/30";

  return (
    <div className="rounded-lg border border-borderSubtle bg-bgBase overflow-hidden">
      <div className="flex items-center justify-between gap-3 px-4 py-2.5 bg-surfaceContainer border-b border-borderSubtle">
        <div className="flex items-center gap-2 min-w-0">
          <KeyRound className="h-4 w-4 text-accentPrimary shrink-0" />
          <span className="text-body-sm font-semibold text-textPrimary truncate">
            {artifact.label}
          </span>
          <span className="text-body-sm text-textMuted truncate">· {artifact.signerRole}</span>
        </div>
        <button
          type="button"
          onClick={() => setOutcome(runBrowserVerification(artifact))}
          className="shrink-0 rounded-md border border-accentPrimary/30 bg-accentPrimary/10 px-3 py-1 text-label-sm font-semibold text-accentPrimary hover:bg-accentPrimary/20 transition-colors cursor-pointer"
        >
          {verifyIdleLabel}
        </button>
      </div>

      <div className="px-4 py-2">
        <PipelineRow stageLabel="Signer DID">
          <code className="block text-[11px] font-mono text-textSecondary break-all">
            {artifact.signerDid}
          </code>
        </PipelineRow>

        <PipelineRow stageLabel="Canonical JSON">
          <pre className="max-h-32 overflow-auto custom-scrollbar text-[11px] font-mono text-textSecondary whitespace-pre-wrap break-all m-0">
            {artifact.canonicalJson}
          </pre>
          <span className="mt-1 block text-[11px] text-textMuted">
            RFC 8785 · {artifact.canonicalByteLength} bytes
          </span>
        </PipelineRow>

        <PipelineRow stageLabel="SHA-256">
          <code className="block text-[11px] font-mono text-textSecondary break-all">
            {artifact.sha256Digest}
          </code>
        </PipelineRow>

        <PipelineRow stageLabel="Ed25519 sig">
          <code className="block text-[11px] font-mono text-textSecondary break-all">
            {artifact.signatureHex}
          </code>
        </PipelineRow>

        {artifact.linkedHashes && (
          <PipelineRow stageLabel="Chains to">
            <div className="space-y-1">
              {Object.entries(artifact.linkedHashes).map(([name, hash]) => (
                <div key={name} className="min-w-0">
                  <span className="text-[11px] text-textMuted">{name}: </span>
                  <code className="text-[11px] font-mono text-textSecondary break-all">{hash}</code>
                </div>
              ))}
            </div>
          </PipelineRow>
        )}
      </div>

      {outcome.state !== "IDLE" && (
        <div className="border-t border-borderSubtle px-4 py-3">
          <div className={`inline-flex items-center gap-1.5 rounded-full border px-2.5 py-1 text-label-sm font-semibold ${badgeClass}`}>
            {outcome.state === "PASSED" ? (
              <ShieldCheck className="h-3.5 w-3.5" />
            ) : (
              <ShieldAlert className="h-3.5 w-3.5" />
            )}
            {outcome.state === "PASSED" ? verifyPassLabel : verifyFailLabel}
          </div>
          <p className="mt-2 text-body-sm text-textSecondary">{outcome.detail}</p>
        </div>
      )}
    </div>
  );
}
