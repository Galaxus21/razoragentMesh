"use client";

import React, { useCallback, useEffect } from "react";
import { AgentTracePanel } from "@/components/agentTracePanel";
import { DashboardHeader } from "@/components/dashboardHeader";
import { HealingDiffViewer } from "@/components/healingDiffViewer";
import { MandateExplorer } from "@/components/mandateExplorer";
import { MetricsBar } from "@/components/metricsBar";
import { NegotiationChart } from "@/components/negotiationChart";
import { WebhookFeed } from "@/components/webhookFeed";
import { useSseStream } from "@/hooks/useSseStream";
import {
  createNegotiationScenarioEvents,
  createNominalSettlementEvents,
  createOosHealingScenarioEvents,
} from "@/lib/mockScenarioGenerator";

export default function TelemetryDashboardPage(): React.JSX.Element {
  const {
    events,
    connectionState,
    isConnected,
    isMockActive,
    clearEvents,
    injectMockEvent,
  } = useSseStream({
    autoConnect: true,
    enableMockFallback: true,
  });

  const simulateFullAgenticFlow = useCallback(() => {
    const sessionId = `session-${Date.now()}`;
    const allScenarios = [
      ...createNominalSettlementEvents(sessionId),
      ...createNegotiationScenarioEvents(sessionId),
      ...createOosHealingScenarioEvents(sessionId),
    ];

    allScenarios.forEach((evt, idx) => {
      setTimeout(() => {
        injectMockEvent(evt);
      }, idx * 60);
    });
  }, [injectMockEvent]);

  useEffect(() => {
    // Seed initial baseline events on mount if event buffer is empty
    if (events.length === 0) {
      simulateFullAgenticFlow();
    }
  }, [events.length, simulateFullAgenticFlow]);

  return (
    <div className="flex min-h-screen flex-col bg-[#070a12] text-slate-100">
      <DashboardHeader
        connectionState={connectionState}
        isConnected={isConnected}
        isMockActive={isMockActive}
        totalEventsCount={events.length}
        onClearEvents={clearEvents}
        onSimulateFlow={simulateFullAgenticFlow}
      />

      <main className="flex-1 space-y-4 pb-8">
        <MetricsBar events={events} />

        {/* 5-Panel High-Density Grid */}
        <div className="grid grid-cols-1 lg:grid-cols-12 gap-4 px-6">
          {/* Panel 1: Agent Trace & MCP Tool Calls */}
          <section className="lg:col-span-6 min-h-[420px]">
            <AgentTracePanel events={events} />
          </section>

          {/* Panel 2: Dynamic B2B Negotiation Convergence */}
          <section className="lg:col-span-6 min-h-[420px]">
            <NegotiationChart events={events} />
          </section>

          {/* Panel 3: AP2 Cryptographic Mandate Chain */}
          <section className="lg:col-span-4 min-h-[380px]">
            <MandateExplorer events={events} />
          </section>

          {/* Panel 4: Sub-300ms Self-Healing Visualizer */}
          <section className="lg:col-span-4 min-h-[380px]">
            <HealingDiffViewer events={events} />
          </section>

          {/* Panel 5: Live Razorpay Webhook & 2PC Split Feed */}
          <section className="lg:col-span-4 min-h-[380px]">
            <WebhookFeed events={events} />
          </section>
        </div>
      </main>
    </div>
  );
}
