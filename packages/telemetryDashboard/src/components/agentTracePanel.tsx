"use client";

import React, { useState } from "react";
import { ChevronDown, ChevronRight, Clock, Code2, Search, Terminal } from "lucide-react";
import { traceEventTypes } from "@/constants/dashboardConstants";
import { formatLatency } from "@/lib/currencyUtils";
import { formatPrettyJson, formatTimestampToTime, getEventStyle } from "@/lib/eventFormatter";
import { TelemetryEvent } from "@/types/telemetryEventTypes";

export interface AgentTracePanelProps {
  readonly events: ReadonlyArray<TelemetryEvent>;
}

export function AgentTracePanel({ events }: AgentTracePanelProps): React.JSX.Element {
  const [expandedCallId, setExpandedCallId] = useState<string | null>(null);
  const [searchQuery, setSearchQuery] = useState<string>("");

  const traceEvents = events.filter((evt) => {
    if (!traceEventTypes.has(evt.eventType)) {
      return false;
    }
    if (!searchQuery) {
      return true;
    }
    const query = searchQuery.toLowerCase();
    const eventTypeMatch = evt.eventType.toLowerCase().includes(query);
    const payloadMatch = JSON.stringify(evt.payload).toLowerCase().includes(query);
    return eventTypeMatch || payloadMatch;
  });

  const toggleExpand = (id: string) => {
    setExpandedCallId((prev) => (prev === id ? null : id));
  };

  return (
    <div className="flex h-full flex-col rounded-xl border border-slate-800 bg-slate-950/70 p-4 shadow-xl backdrop-blur-md">
      <div className="flex items-center justify-between border-b border-slate-800/80 pb-3">
        <div className="flex items-center gap-2">
          <Terminal className="h-4 w-4 text-cyan-400" />
          <h2 className="text-sm font-semibold text-white">Agent Thought & MCP Trace</h2>
          <span className="rounded bg-cyan-950/70 px-1.5 py-0.5 text-[11px] font-mono text-cyan-300">
            {traceEvents.length}
          </span>
        </div>
        <div className="relative">
          <Search className="absolute left-2 top-2 h-3.5 w-3.5 text-slate-500" />
          <input
            type="text"
            placeholder="Filter traces..."
            value={searchQuery}
            onChange={(e) => setSearchQuery(e.target.value)}
            className="h-7 w-36 rounded-md border border-slate-800 bg-slate-900/90 pl-7 pr-2 text-xs text-slate-200 placeholder-slate-500 focus:border-cyan-500 focus:outline-none"
          />
        </div>
      </div>

      <div className="flex-1 overflow-y-auto pt-3 space-y-2.5 pr-1 max-h-[380px] custom-scrollbar">
        {traceEvents.length === 0 ? (
          <div className="flex h-32 flex-col items-center justify-center text-xs text-slate-500">
            <Code2 className="mb-2 h-6 w-6 text-slate-600" />
            <span>Awaiting MCP JSON-RPC tool events...</span>
          </div>
        ) : (
          traceEvents.map((evt) => {
            const style = getEventStyle(evt.eventType);
            const isExpanded = expandedCallId === evt.eventId;

            return (
              <div
                key={evt.eventId}
                className={`rounded-lg border bg-slate-900/60 p-2.5 transition ${style.borderColor} hover:bg-slate-900`}
              >
                <div
                  onClick={() => toggleExpand(evt.eventId)}
                  className="flex cursor-pointer items-center justify-between text-xs"
                >
                  <div className="flex items-center gap-2">
                    {isExpanded ? (
                      <ChevronDown className="h-3.5 w-3.5 text-slate-400" />
                    ) : (
                      <ChevronRight className="h-3.5 w-3.5 text-slate-400" />
                    )}
                    <span
                      className={`rounded px-1.5 py-0.5 font-mono text-[10px] font-semibold ${style.badgeBg} ${style.badgeText}`}
                    >
                      {style.label}
                    </span>
                    <span className="font-mono text-slate-200 font-medium truncate max-w-[140px] sm:max-w-[200px]">
                      {"toolName" in evt.payload
                        ? (evt.payload.toolName as string)
                        : evt.eventType}
                    </span>
                  </div>

                  <div className="flex items-center gap-2">
                    {"durationMs" in evt.payload && (
                      <span className="flex items-center gap-1 font-mono text-[11px] text-cyan-400">
                        <Clock className="h-3 w-3" />
                        {formatLatency(evt.payload.durationMs as number)}
                      </span>
                    )}
                    <span className="font-mono text-[10px] text-slate-500">
                      {formatTimestampToTime(evt.timestampMs)}
                    </span>
                  </div>
                </div>

                {isExpanded && (
                  <div className="mt-2.5 border-t border-slate-800 pt-2">
                    <pre className="max-h-48 overflow-x-auto rounded bg-slate-950 p-2 font-mono text-[11px] text-slate-300 custom-scrollbar">
                      {formatPrettyJson(evt.payload)}
                    </pre>
                  </div>
                )}
              </div>
            );
          })
        )}
      </div>
    </div>
  );
}
