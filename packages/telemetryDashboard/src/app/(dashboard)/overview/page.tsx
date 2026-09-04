"use client";

// The first screen: what the mesh is, whether it is up, and how to make it do something.
//
// This page used to render MetricsBar plus AgentTracePanel, NegotiationChart, MandateExplorer,
// HealingDiffViewer and WebhookFeed -- the exact six components /visualise renders, from the
// exact same event array. Overview was a strict subset of Visualise, so a reader who opened both
// saw the same five panels twice and had no way to tell which page was the one to watch.
//
// The split now follows the question each page answers. Visualise answers "what is happening
// right now", and keeps every live panel. This page answers the two questions that come BEFORE
// that and have no live component at all: what are these six layers, and is the mesh actually
// running? The layer map with its health probe moved here from /visualise/protocol for the same
// reason -- static architecture and a liveness check are orientation, not observation.
//
// The one live thing kept here is the metrics bar, because "has anything settled yet" is part of
// knowing whether the system is working, and it is a single row rather than a second dashboard.

import React, { useMemo, useState } from "react";
import Link from "next/link";
import { AlertTriangle, ArrowRight, RefreshCw } from "lucide-react";
import { MetricsBar } from "@/components/metricsBar";
import { LayerCard } from "@/components/protocolMap/layerCard";
import { LayerDetailPanel } from "@/components/protocolMap/layerDetailPanel";
import { panelClass } from "@/constants/playgroundConstants";
import { protocolLayerNodes } from "@/constants/protocolLayerMap";
import { useTelemetry } from "@/context/telemetryContext";
import { useMeshHealth } from "@/hooks/useMeshHealth";

const pageTitle = "RazorAgent Mesh";
const pageDescription =
  "A protocol an autonomous agent buys through: it is screened at the edge, discovers and quotes " +
  "a SKU over MCP, negotiates, is healed around an out-of-stock line, and settles against a " +
  "signed Google AP2 mandate chain on real Razorpay rails. Every service below is probed live.";

const firstLayerId = protocolLayerNodes[0]?.layerId ?? "";

interface TryItStep {
  readonly ordinal: number;
  readonly title: string;
  readonly body: string;
  readonly href: string;
  readonly linkLabel: string;
}

const tryItSteps: ReadonlyArray<TryItStep> = [
  {
    ordinal: 1,
    title: "Publish something to sell",
    body:
      "Author a SKU in the Merchant Studio with its price, GST rate, volume tiers and any " +
      "scheduled promotion. Publishing writes it to the live catalog an agent searches.",
    href: "/merchant-studio",
    linkLabel: "Open Merchant Studio",
  },
  {
    ordinal: 2,
    title: "Point an agent at the mesh",
    body:
      "Connect any MCP client to http://localhost:4001/mcp and ask it to buy what you just " +
      "published. Nothing is scripted: the agent chooses its own tools.",
    href: "/docs/agent-quickstart",
    linkLabel: "Agent quickstart",
  },
  {
    ordinal: 3,
    title: "Watch it happen",
    body:
      "The protocol stack lights up stage by stage as the agent works, and the run ends with a " +
      "real Razorpay order you can finish by hand.",
    href: "/visualise",
    linkLabel: "Open Visualise",
  },
];

export default function OverviewPage(): React.JSX.Element {
  const { events } = useTelemetry();
  const health = useMeshHealth();
  const [selectedLayerId, setSelectedLayerId] = useState<string>(firstLayerId);

  const selectedLayer = useMemo(
    () =>
      protocolLayerNodes.find((layer) => layer.layerId === selectedLayerId) ??
      protocolLayerNodes[0],
    [selectedLayerId]
  );

  const downCount = health.statuses.filter((status) => status.health === "DOWN").length;

  return (
    <div className="mx-auto max-w-7xl space-y-4">
      <header className="flex flex-wrap items-start justify-between gap-3">
        <div>
          <h2 className="text-headline-sm text-textPrimary">{pageTitle}</h2>
          <p className="mt-1 max-w-3xl text-body-sm text-textSecondary">{pageDescription}</p>
        </div>
        <button
          type="button"
          onClick={() => void health.refresh()}
          disabled={health.isProbing}
          className="inline-flex items-center gap-1.5 rounded-md border border-borderSubtle bg-bgSurface px-3 py-1.5 text-label-sm font-semibold text-textSecondary transition-colors hover:bg-bgSurfaceHover hover:text-textPrimary disabled:cursor-not-allowed disabled:text-textMuted"
        >
          <RefreshCw className={`h-3.5 w-3.5 ${health.isProbing ? "animate-spin" : ""}`} />
          {health.isProbing ? "Probing..." : "Re-probe"}
        </button>
      </header>

      <MetricsBar events={events} />

      {downCount > 0 && (
        <div className="flex items-start gap-2 rounded-xl border border-statusWarning/30 bg-statusWarning/5 p-4">
          <AlertTriangle className="mt-0.5 h-4 w-4 shrink-0 text-statusWarning" />
          <div>
            <p className="text-body-md font-semibold text-textPrimary">
              {downCount} of {health.statuses.length} services are not answering
            </p>
            <p className="mt-1 text-body-sm text-textSecondary">
              Stages backed by those services cannot be exercised until they are up:{" "}
              <code className="font-mono">docker compose up</code>
            </p>
          </div>
        </div>
      )}

      {health.errorMessage && (
        <div className="flex items-start gap-2 rounded-xl border border-statusError/30 bg-statusError/5 p-4">
          <AlertTriangle className="mt-0.5 h-4 w-4 shrink-0 text-statusError" />
          <p className="text-body-sm text-textSecondary">{health.errorMessage}</p>
        </div>
      )}

      <div className="flex flex-col gap-4 lg:flex-row">
        <section className="min-w-0 flex-1">
          <p className="mb-2 px-1 text-label-caps uppercase text-textMuted">Protocol stack</p>
          <ol className="list-none">
            {protocolLayerNodes.map((layer, index) => (
              <LayerCard
                key={layer.layerId}
                layer={layer}
                statuses={health.statuses}
                isProbing={health.isProbing}
                isSelected={layer.layerId === selectedLayer.layerId}
                isLast={index === protocolLayerNodes.length - 1}
                onSelect={setSelectedLayerId}
              />
            ))}
          </ol>
        </section>

        <section className={`${panelClass} min-w-0 flex-1 p-5`}>
          <LayerDetailPanel layer={selectedLayer} statuses={health.statuses} />
        </section>
      </div>

      <section className={`${panelClass} p-5`}>
        <h3 className="text-label-sm font-semibold text-textPrimary">Try it yourself</h3>
        <p className="mt-1 text-body-sm text-textSecondary">
          Nothing on this dashboard is a recording. Three steps put a real agent through the whole
          stack.
        </p>

        <ol className="mt-4 grid grid-cols-1 gap-3 md:grid-cols-3">
          {tryItSteps.map((step) => (
            <li
              key={step.ordinal}
              className="flex flex-col rounded-lg border border-borderSubtle bg-surfaceContainer/40 p-4"
            >
              <span className="inline-flex h-6 w-6 items-center justify-center rounded-full bg-accentPrimary/10 font-mono text-[11px] font-semibold text-accentPrimary">
                {step.ordinal}
              </span>
              <h4 className="mt-2 text-label-sm font-semibold text-textPrimary">{step.title}</h4>
              <p className="mt-1 flex-1 text-[11px] leading-relaxed text-textSecondary">
                {step.body}
              </p>
              <Link
                href={step.href}
                className="mt-3 inline-flex items-center gap-1.5 text-[11px] font-medium text-accentPrimary hover:underline"
              >
                {step.linkLabel}
                <ArrowRight className="h-3 w-3" />
              </Link>
            </li>
          ))}
        </ol>
      </section>
    </div>
  );
}
