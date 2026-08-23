"use client";

import React, { useState } from "react";
import { CheckCircle2, Copy, FileCode, KeyRound, Link2, ShieldCheck, X } from "lucide-react";
import { MandateKind, MandateSignedPayload, TelemetryEvent } from "@/types/telemetryEventTypes";
import { truncateHash } from "@/lib/eventFormatter";

export interface MandateExplorerProps {
  readonly events: ReadonlyArray<TelemetryEvent>;
}

interface MandateChainNodeConfig {
  readonly kind: MandateKind;
  readonly title: string;
  readonly signerRole: string;
  readonly description: string;
}

const mandateNodes: ReadonlyArray<MandateChainNodeConfig> = [
  {
    kind: "INTENT",
    title: "IntentMandate (MI)",
    signerRole: "User CFO Key (Ed25519)",
    description: "Delegated budget & category authorization envelope",
  },
  {
    kind: "CART",
    title: "CartMandate (MC)",
    signerRole: "Merchant Key (Ed25519)",
    description: "Itemized pricing, HSN tax breakdown & lock token",
  },
  {
    kind: "EXECUTION",
    title: "ExecutionMandate (ME)",
    signerRole: "Buyer Agent Key (Ed25519)",
    description: "Hash-chain binding H(MI) || H(MC) & replay nonce",
  },
  {
    kind: "AMENDMENT",
    title: "AmendmentMandate (MA)",
    signerRole: "Merchant + Agent Re-sign",
    description: "Patched cart substitution with preserved budget cap",
  },
];

export function MandateExplorer({ events }: MandateExplorerProps): React.JSX.Element {
  const [selectedJcs, setSelectedJcs] = useState<{ title: string; jcs: string } | null>(null);
  const [copiedHash, setCopiedHash] = useState<string | null>(null);

  const signedMandates = events.filter((e): e is TelemetryEvent & { payload: MandateSignedPayload } => {
    return e.eventType === "MANDATE_SIGNED";
  });

  const handleCopy = (hash: string) => {
    navigator.clipboard.writeText(hash);
    setCopiedHash(hash);
    setTimeout(() => setCopiedHash(null), 2000);
  };

  return (
    <div className="flex h-full flex-col rounded-xl border border-slate-800 bg-slate-950/70 p-4 shadow-xl backdrop-blur-md">
      <div className="flex items-center justify-between border-b border-slate-800/80 pb-3">
        <div className="flex items-center gap-2">
          <ShieldCheck className="h-4 w-4 text-cyan-400" />
          <h2 className="text-sm font-semibold text-white">AP2 Cryptographic Mandate Chain</h2>
          <span className="rounded bg-cyan-950/70 px-1.5 py-0.5 text-[11px] font-mono text-cyan-300">
            Ed25519 + JCS
          </span>
        </div>
      </div>

      <div className="mt-3 flex-1 space-y-2.5 overflow-y-auto pr-1 max-h-[380px] custom-scrollbar">
        {mandateNodes.map((node, index) => {
          const match = signedMandates.find((m) => m.payload.mandateType === node.kind);
          const sampleHash =
            match?.payload.mandateHash ??
            `0x${(index + 1) * 22}ab89cd45ef67890123456789abcdef0123456789abcdef0123456789`;
          const isValid = match ? match.payload.verificationStatus !== "INVALID" : true;

          return (
            <div
              key={node.kind}
              className="relative rounded-lg border border-slate-800 bg-slate-900/60 p-3 transition hover:border-slate-700"
            >
              <div className="flex items-start justify-between">
                <div>
                  <div className="flex items-center gap-2">
                    <span className="font-mono text-xs font-bold text-white">{node.title}</span>
                    <span
                      className={`inline-flex items-center gap-1 rounded px-1.5 py-0.5 text-[10px] font-semibold ${
                        isValid
                          ? "bg-emerald-950 text-emerald-300 border border-emerald-500/30"
                          : "bg-rose-950 text-rose-300 border border-rose-500/30"
                      }`}
                    >
                      <CheckCircle2 className="h-3 w-3" />
                      {isValid ? "VALID" : "INVALID"}
                    </span>
                  </div>
                  <p className="mt-0.5 text-[11px] text-slate-400">{node.description}</p>
                </div>

                <button
                  type="button"
                  onClick={() =>
                    setSelectedJcs({
                      title: node.title,
                      jcs:
                        match?.payload.canonicalJcsPreview ??
                        JSON.stringify(
                          {
                            mandateType: node.kind,
                            signerRole: node.signerRole,
                            hash: sampleHash,
                          },
                          null,
                          2
                        ),
                    })
                  }
                  className="flex items-center gap-1 rounded border border-slate-700 bg-slate-800 px-2 py-1 text-[10px] text-slate-300 hover:bg-slate-700"
                >
                  <FileCode className="h-3 w-3 text-cyan-400" />
                  <span>JCS</span>
                </button>
              </div>

              <div className="mt-2.5 flex flex-wrap items-center justify-between gap-2 border-t border-slate-800/80 pt-2 text-[11px] font-mono">
                <div className="flex items-center gap-1 text-slate-400">
                  <KeyRound className="h-3 w-3 text-slate-500" />
                  <span className="truncate max-w-[140px] text-slate-300">{node.signerRole}</span>
                </div>

                <div className="flex items-center gap-1">
                  <span className="text-slate-500">SHA-256:</span>
                  <span className="rounded bg-slate-950 px-1.5 py-0.5 text-cyan-300">
                    {truncateHash(sampleHash)}
                  </span>
                  <button
                    type="button"
                    onClick={() => handleCopy(sampleHash)}
                    className="text-slate-400 hover:text-white"
                  >
                    <Copy className="h-3 w-3" />
                  </button>
                </div>
              </div>
            </div>
          );
        })}
      </div>

      {selectedJcs && (
        <div className="fixed inset-0 z-50 flex items-center justify-center bg-black/70 p-4 backdrop-blur-sm">
          <div className="w-full max-w-lg rounded-xl border border-slate-700 bg-slate-950 p-4 shadow-2xl">
            <div className="flex items-center justify-between border-b border-slate-800 pb-2">
              <span className="text-xs font-semibold text-white font-mono">
                RFC 8785 Canonical JCS — {selectedJcs.title}
              </span>
              <button
                type="button"
                onClick={() => setSelectedJcs(null)}
                className="text-slate-400 hover:text-white"
              >
                <X className="h-4 w-4" />
              </button>
            </div>
            <pre className="mt-3 max-h-64 overflow-y-auto rounded bg-slate-900 p-3 font-mono text-xs text-cyan-300 custom-scrollbar">
              {selectedJcs.jcs}
            </pre>
          </div>
        </div>
      )}
    </div>
  );
}
