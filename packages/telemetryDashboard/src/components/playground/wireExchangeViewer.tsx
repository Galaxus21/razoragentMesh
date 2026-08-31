"use client";

import React, { useState } from "react";
import { ChevronDown, ChevronRight } from "lucide-react";
import type { WireExchange } from "@/types/protocolRunTypes";

// Shows the request/response verbatim. Collapsed by default because a settlement body runs to
// several hundred lines, but one click away because "show me the actual bytes" is the question
// a sceptical reader asks first.

export interface WireExchangeViewerProps {
  readonly exchange: WireExchange;
  readonly index: number;
}

function statusToneClass(statusCode: number): string {
  if (statusCode >= 200 && statusCode < 300) {
    return "bg-statusSuccess/10 text-statusSuccess border-statusSuccess/30";
  }
  if (statusCode >= 400 && statusCode < 500) {
    return "bg-statusWarning/10 text-statusWarning border-statusWarning/30";
  }
  return "bg-statusError/10 text-statusError border-statusError/30";
}

function BodyBlock({
  label,
  body
}: {
  readonly label: string;
  readonly body: unknown;
}): React.JSX.Element | null {
  if (body === null || body === undefined) {
    return null;
  }
  const rendered = typeof body === "string" ? body : JSON.stringify(body, null, 2);
  if (rendered.trim().length === 0 || rendered === "{}") {
    return null;
  }
  return (
    <div className="mt-2">
      <span className="text-label-caps uppercase text-textMuted">{label}</span>
      <pre className="mt-1 max-h-64 overflow-auto custom-scrollbar rounded-md border border-borderSubtle bg-bgBase p-2.5 text-[11px] font-mono leading-relaxed text-textSecondary whitespace-pre-wrap break-all m-0">
        {rendered}
      </pre>
    </div>
  );
}

export function WireExchangeViewer({
  exchange,
  index
}: WireExchangeViewerProps): React.JSX.Element {
  const [isExpanded, setIsExpanded] = useState<boolean>(false);

  return (
    <div className="rounded-lg border border-borderSubtle bg-bgBase overflow-hidden">
      <button
        type="button"
        onClick={() => setIsExpanded((previous) => !previous)}
        className="flex w-full items-center gap-2 px-3 py-2 bg-surfaceContainer hover:bg-surfaceContainerHigh transition-colors text-left cursor-pointer"
      >
        {isExpanded ? (
          <ChevronDown className="h-3.5 w-3.5 text-textMuted shrink-0" />
        ) : (
          <ChevronRight className="h-3.5 w-3.5 text-textMuted shrink-0" />
        )}
        <span className="text-[11px] font-mono font-semibold text-accentPrimary shrink-0">
          {exchange.method}
        </span>
        <span className="min-w-0 flex-1 truncate text-[11px] font-mono text-textSecondary">
          {exchange.url}
        </span>
        <span
          className={`shrink-0 rounded-full border px-2 py-0.5 text-[10px] font-semibold ${statusToneClass(exchange.statusCode)}`}
        >
          {exchange.statusCode}
        </span>
        <span className="shrink-0 text-[11px] font-mono text-textMuted">
          {exchange.durationMs}ms
        </span>
      </button>

      {isExpanded && (
        <div className="px-3 py-3 border-t border-borderSubtle">
          <span className="text-label-caps uppercase text-textMuted">
            Request {index + 1} headers
          </span>
          <div className="mt-1 space-y-0.5">
            {Object.entries(exchange.requestHeaders).map(([name, value]) => (
              <div key={name} className="text-[11px] font-mono text-textSecondary break-all">
                <span className="text-textMuted">{name}:</span> {value}
              </div>
            ))}
          </div>
          <BodyBlock label="Request body" body={exchange.requestBody} />
          <BodyBlock label="Response body" body={exchange.responseBody} />
        </div>
      )}
    </div>
  );
}
