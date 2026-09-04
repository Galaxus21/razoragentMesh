"use client";

import React from "react";
import { FileCode2, Layers, ShieldCheck } from "lucide-react";
import { DocCodeGroup } from "@/components/docs/docCodeGroup";
import { MandateInspector } from "@/components/playground/mandateInspector";
import { WireExchangeViewer } from "@/components/playground/wireExchangeViewer";
import { detailScrollClass, stepStatusPresentation } from "@/constants/playgroundConstants";
import { buildStepSnippets } from "@/lib/snippetGenerator";
import type { ProtocolStepRecord } from "@/types/protocolRunTypes";

export interface StepDetailPanelProps {
  readonly step: ProtocolStepRecord;
}

function SectionHeading({
  icon: Icon,
  label
}: {
  readonly icon: React.ComponentType<{ className?: string }>;
  readonly label: string;
}): React.JSX.Element {
  return (
    <div className="mb-2 flex items-center gap-1.5">
      <Icon className="h-3.5 w-3.5 text-accentPrimary" />
      <span className="text-label-caps uppercase text-textMuted">{label}</span>
    </div>
  );
}

export function StepDetailPanel({ step }: StepDetailPanelProps): React.JSX.Element {
  const presentation = stepStatusPresentation[step.status];
  const snippets = buildStepSnippets(step);

  return (
    <div className={detailScrollClass}>
      <div className="space-y-5 pr-1">
        <header>
          <div className="flex flex-wrap items-center gap-2">
            <span
              className={`rounded-full border px-2.5 py-0.5 text-label-sm font-semibold ${presentation.badgeClass}`}
            >
              {presentation.label}
            </span>
            <span className="text-[11px] font-mono text-textMuted">{step.durationMs}ms</span>
            {step.invariant && (
              <span className="rounded-full border border-borderSubtle bg-surfaceContainer px-2 py-0.5 text-[10px] font-semibold text-textSecondary">
                {step.invariant}
              </span>
            )}
          </div>
          <h3 className="mt-2 text-headline-sm text-textPrimary">{step.title}</h3>
          <p className="mt-1.5 text-body-sm leading-relaxed text-textSecondary">{step.narrative}</p>
          <div className="mt-2 flex flex-wrap items-center gap-x-4 gap-y-1 text-[11px] text-textMuted">
            <span className="inline-flex items-center gap-1">
              <Layers className="h-3 w-3" />
              {step.protocolLayer}
            </span>
            <code className="font-mono break-all">{step.implementedBy}</code>
          </div>
        </header>

        {step.refusal && (
          <section
            className={`rounded-lg border p-3 ${
              step.status === "REFUSED"
                ? "border-accentPrimary/30 bg-accentPrimary/5"
                : "border-statusError/30 bg-statusError/5"
            }`}
          >
            <SectionHeading
              icon={ShieldCheck}
              label={step.status === "REFUSED" ? "Refused — protocol worked" : "Failure"}
            />
            <p className="text-body-sm font-semibold text-textPrimary">{step.refusal.errorName}</p>
            <p className="mt-1 text-body-sm text-textSecondary break-words">
              {step.refusal.message}
            </p>
            {step.refusal.invariantViolated && (
              <p className="mt-2 text-[11px] text-textMuted">
                Caught by{" "}
                <span className="font-semibold text-textSecondary">
                  {step.refusal.invariantViolated}
                </span>
              </p>
            )}
          </section>
        )}

        <section>
          <SectionHeading icon={FileCode2} label="The SDK call that produced this" />
          <DocCodeGroup
            items={snippets.map((snippet) => ({
              language: snippet.language,
              code: snippet.code
            }))}
          />
        </section>

        {step.artifacts.length > 0 && (
          <section>
            <SectionHeading icon={ShieldCheck} label="Cryptographic artifacts" />
            <div className="space-y-3">
              {step.artifacts.map((artifact) => (
                <MandateInspector key={artifact.artifactId} artifact={artifact} />
              ))}
            </div>
          </section>
        )}

        {step.exchanges.length > 0 && (
          <section>
            <SectionHeading icon={Layers} label="Wire traffic" />
            <div className="space-y-2">
              {step.exchanges.map((exchange, index) => (
                <WireExchangeViewer
                  key={`${exchange.method}-${exchange.url}-${index}`}
                  exchange={exchange}
                  index={index}
                />
              ))}
            </div>
          </section>
        )}

        {step.resultSummary && (
          <section>
            <SectionHeading icon={FileCode2} label="Result" />
            <pre className="max-h-64 overflow-auto custom-scrollbar rounded-lg border border-borderSubtle bg-bgBase p-3 text-[11px] font-mono leading-relaxed text-textSecondary whitespace-pre-wrap break-all m-0">
              {JSON.stringify(step.resultSummary, null, 2)}
            </pre>
          </section>
        )}
      </div>
    </div>
  );
}
