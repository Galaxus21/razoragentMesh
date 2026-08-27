"use client";

import React from "react";
import { AgentTracePanel } from "@/components/agentTracePanel";
import { useTelemetry } from "@/context/telemetryContext";

const pageTitle = "Agent Observability & MCP Traces";
const pageDescription = "Real-time execution log of autonomous buyer/merchant agents and JSON-RPC tool invocations.";

export default function AgentObservabilityPage(): React.JSX.Element {
  const { events } = useTelemetry();

  return (
    <div className="space-y-4 max-w-7xl mx-auto">
      <div>
        <h2 className="text-lg font-semibold text-textPrimary">{pageTitle}</h2>
        <p className="text-xs text-textSecondary">{pageDescription}</p>
      </div>
      <div className="min-h-[640px]">
        <AgentTracePanel events={events} />
      </div>
    </div>
  );
}
