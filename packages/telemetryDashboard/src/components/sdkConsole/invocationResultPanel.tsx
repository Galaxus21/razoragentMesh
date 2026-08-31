"use client";

import React from "react";
import { FileCode2, Layers, ShieldAlert } from "lucide-react";
import { DocCodeGroup } from "@/components/docs/docCodeGroup";
import { WireExchangeViewer } from "@/components/playground/wireExchangeViewer";
import { detailScrollClass } from "@/constants/playgroundConstants";
import { buildInvocationSnippets } from "@/lib/snippetGenerator";
import type { SdkInvocationResult } from "@/types/sdkConsoleTypes";

export interface InvocationResultPanelProps {
  readonly result: SdkInvocationResult;
}

const succeededBadgeClass = "bg-statusSuccess/10 text-statusSuccess border-statusSuccess/30";
const failedBadgeClass = "bg-statusWarning/10 text-statusWarning border-statusWarning/30";

function SectionHeading({
  icon: Icon,
  label,
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

export function InvocationResultPanel({
  result,
}: InvocationResultPanelProps): React.JSX.Element {
  const hasSucceeded = result.status === "SUCCEEDED";
  const snippets = buildInvocationSnippets(result.methodName, result.exchanges);

  return (
    <div className={detailScrollClass}>
      <div className="space-y-5 pr-1">
        <header className="flex flex-wrap items-center gap-2">
          <span
            className={`rounded-full border px-2.5 py-0.5 text-label-sm font-semibold ${
              hasSucceeded ? succeededBadgeClass : failedBadgeClass
            }`}
          >
            {hasSucceeded ? "SUCCEEDED" : "REJECTED"}
          </span>
          <code className="font-mono text-body-sm text-textPrimary">{result.methodName}</code>
          <span className="text-[11px] font-mono text-textMuted">{result.durationMs}ms</span>
        </header>

        {result.failure && (
          <section className="rounded-lg border border-statusWarning/30 bg-statusWarning/5 p-3">
            <SectionHeading icon={ShieldAlert} label="The mesh rejected this call" />
            <p className="text-body-sm font-semibold text-textPrimary">
              {result.failure.errorName}
              {result.failure.statusCode ? ` (HTTP ${result.failure.statusCode})` : ""}
            </p>
            <p className="mt-1 break-words text-body-sm text-textSecondary">
              {result.failure.message}
            </p>
            <p className="mt-2 text-[11px] text-textMuted">
              A rejection is a real answer, not a broken page. The exchange below is the request
              that was actually sent and the response that actually came back.
            </p>
          </section>
        )}

        <section>
          <SectionHeading icon={FileCode2} label="The call you just made" />
          <DocCodeGroup
            items={snippets.map((snippet) => ({
              language: snippet.language,
              code: snippet.code,
            }))}
          />
        </section>

        {result.exchanges.length > 0 && (
          <section>
            <SectionHeading icon={Layers} label="Wire traffic" />
            <div className="space-y-2">
              {result.exchanges.map((exchange, index) => (
                <WireExchangeViewer
                  key={`${exchange.method}-${exchange.url}-${index}`}
                  exchange={exchange}
                  index={index}
                />
              ))}
            </div>
          </section>
        )}

        {result.returnValue !== undefined && (
          <section>
            <SectionHeading icon={FileCode2} label="What the SDK returned" />
            <pre className="max-h-96 overflow-auto custom-scrollbar rounded-lg border border-borderSubtle bg-bgBase p-3 text-[11px] font-mono leading-relaxed text-textSecondary whitespace-pre-wrap break-all m-0">
              {JSON.stringify(result.returnValue, null, 2)}
            </pre>
          </section>
        )}
      </div>
    </div>
  );
}
