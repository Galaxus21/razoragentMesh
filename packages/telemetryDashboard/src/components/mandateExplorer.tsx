"use client";

import React, { useState } from "react";
import { CheckCircle2, Copy, FileCode, KeyRound, Link2, ShieldCheck, X } from "lucide-react";
import { copyFeedbackTimeoutMs, defaultMandateChainNodes } from "@/constants/dashboardConstants";
import { truncateHash } from "@/lib/eventFormatter";
import { MandateSignedPayload, TelemetryEvent } from "@/types/telemetryEventTypes";

export interface MandateExplorerProps {
  readonly events: ReadonlyArray<TelemetryEvent>;
}

export function MandateExplorer({ events }: MandateExplorerProps): React.JSX.Element {
  const [selectedJcs, setSelectedJcs] = useState<{ title: string; jcs: string } | null>(null);
  const [copiedHash, setCopiedHash] = useState<string | null>(null);

  const signedMandates = events.filter((e): e is TelemetryEvent & { payload: MandateSignedPayload } => {
    return e.eventType === "MANDATE_SIGNED";
  });

  const handleCopy = (hash: string) => {
    navigator.clipboard.writeText(hash);
    setCopiedHash(hash);
    setTimeout(() => setCopiedHash(null), copyFeedbackTimeoutMs);
  };

  return (
    <div className="flex h-full flex-col rounded-lg border border-borderSubtle bg-bgSurface p-4">
      <div className="flex items-center justify-between border-b border-borderSubtle pb-3">
        <div className="flex items-center gap-2">
          <ShieldCheck className="h-4 w-4 text-statusInfo" />
          <h2 className="text-sm font-semibold text-textPrimary">AP2 Cryptographic Mandate Chain</h2>
          <span className="rounded bg-accentSubtle px-1.5 py-0.5 text-xs font-mono text-accentPrimary">
            Ed25519 + JCS
          </span>
        </div>
      </div>

      <div className="mt-3 flex-1 space-y-2.5 overflow-y-auto pr-1 max-h-[380px] custom-scrollbar">
        {defaultMandateChainNodes.map((node) => {
          const match = signedMandates.find((m) => m.payload.mandateType === node.kind);
          const isSigned = Boolean(match);
          const isValid = match?.payload.verificationStatus !== "INVALID";
          const mandateHash = match?.payload.mandateHash ?? null;
          const signerRole = match?.payload.signerKeyDid ?? node.signerRole;

          return (
            <div
              key={node.kind}
              className="relative rounded-md border border-borderSubtle bg-surfaceContainer p-3 transition hover:border-borderSubtle/80 hover:bg-bgSurfaceHover"
            >
              <div className="flex items-start justify-between">
                <div>
                  <div className="flex items-center gap-2">
                    <span className="font-mono text-xs font-bold text-textPrimary">{node.title}</span>
                    {isSigned ? (
                      <span
                        className={`inline-flex items-center gap-1 rounded px-1.5 py-0.5 text-[10px] font-semibold ${
                          isValid
                            ? "bg-statusSuccess/10 text-statusSuccess border border-statusSuccess/30"
                            : "bg-statusError/10 text-statusError border border-statusError/30"
                        }`}
                      >
                        <CheckCircle2 className="h-3 w-3" />
                        {isValid ? "VALID" : "INVALID"}
                      </span>
                    ) : (
                      <span className="inline-flex items-center gap-1 rounded border border-borderSubtle bg-bgBase px-1.5 py-0.5 text-[10px] font-semibold text-textMuted">
                        PENDING
                      </span>
                    )}
                  </div>
                  <p className="mt-0.5 text-xs text-textSecondary">{node.description}</p>
                </div>

                {isSigned && match?.payload.canonicalJcsPreview && (
                  <button
                    type="button"
                    onClick={() =>
                      setSelectedJcs({
                        title: node.title,
                        jcs: match.payload.canonicalJcsPreview ?? "",
                      })
                    }
                    className="flex items-center gap-1 rounded border border-borderSubtle bg-bgSurface px-2 py-1 text-xs text-textSecondary hover:bg-bgSurfaceHover hover:text-textPrimary"
                  >
                    <FileCode className="h-3 w-3 text-statusInfo" />
                    <span>JCS</span>
                  </button>
                )}
              </div>

              <div className="mt-2.5 flex flex-wrap items-center justify-between gap-2 border-t border-borderSubtle pt-2 text-xs font-mono">
                <div className="flex items-center gap-1 text-textSecondary">
                  <KeyRound className="h-3 w-3 text-textMuted" />
                  <span className="truncate max-w-[160px] text-textSecondary">
                    {signerRole}
                  </span>
                </div>

                <div className="flex items-center gap-1">
                  <span className="text-textMuted">SHA-256:</span>
                  <span className="rounded bg-bgBase border border-borderSubtle px-1.5 py-0.5 text-textPrimary">
                    {mandateHash ? truncateHash(mandateHash) : "—"}
                  </span>
                  {mandateHash && (
                    <button
                      type="button"
                      onClick={() => handleCopy(mandateHash)}
                      className="text-textMuted hover:text-textPrimary"
                    >
                      <Copy className="h-3 w-3" />
                    </button>
                  )}
                </div>
              </div>
            </div>
          );
        })}
      </div>

      {selectedJcs && (
        <div className="fixed inset-0 z-50 flex items-center justify-center bg-black/60 p-4">
          <div className="w-full max-w-lg rounded-lg border border-borderSubtle bg-bgSurface p-4 shadow-2xl">
            <div className="flex items-center justify-between border-b border-borderSubtle pb-2">
              <span className="text-xs font-semibold text-textPrimary font-mono">
                RFC 8785 Canonical JCS — {selectedJcs.title}
              </span>
              <button
                type="button"
                onClick={() => setSelectedJcs(null)}
                className="text-textSecondary hover:text-textPrimary"
              >
                <X className="h-4 w-4" />
              </button>
            </div>
            <pre className="mt-3 max-h-64 overflow-y-auto rounded bg-bgBase border border-borderSubtle p-3 font-mono text-xs text-textPrimary custom-scrollbar">
              {selectedJcs.jcs}
            </pre>
          </div>
        </div>
      )}
    </div>
  );
}
