"use client";

import React from "react";
import { AgentTracePanel } from "@/components/agentTracePanel";
import { HealingDiffViewer } from "@/components/healingDiffViewer";
import { MandateExplorer } from "@/components/mandateExplorer";
import { MetricsBar } from "@/components/metricsBar";
import { NegotiationChart } from "@/components/negotiationChart";
import { WebhookFeed } from "@/components/webhookFeed";
import { useTelemetry } from "@/context/telemetryContext";

export default function OverviewPage(): React.JSX.Element {
  const { events } = useTelemetry();

  return (
    <div className="space-y-4">
      <MetricsBar events={events} />
      <div className="grid grid-cols-1 lg:grid-cols-12 gap-4">
        <section className="lg:col-span-6 min-h-[420px]">
          <AgentTracePanel events={events} />
        </section>
        <section className="lg:col-span-6 min-h-[420px]">
          <NegotiationChart events={events} />
        </section>
        <section className="lg:col-span-4 min-h-[380px]">
          <MandateExplorer events={events} />
        </section>
        <section className="lg:col-span-4 min-h-[380px]">
          <HealingDiffViewer events={events} />
        </section>
        <section className="lg:col-span-4 min-h-[380px]">
          <WebhookFeed events={events} />
        </section>
      </div>
    </div>
  );
}
