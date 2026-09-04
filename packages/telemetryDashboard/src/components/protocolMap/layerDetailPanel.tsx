"use client";

import React from "react";
import Link from "next/link";
import { BookOpen, Play } from "lucide-react";
import { meshServicesById } from "@/constants/meshServiceRegistry";
import type { ProtocolLayerNode } from "@/constants/protocolLayerMap";
import type { MeshServiceStatus } from "@/server/meshHealth/probeMeshServices";

export interface LayerDetailPanelProps {
  readonly layer: ProtocolLayerNode;
  readonly statuses: readonly MeshServiceStatus[];
}

// The three headings below used to each carry their own lucide glyph. None of them distinguished
// anything -- a clipboard beside "responsibilities" and a box beside "packages" tell the reader
// nothing the words do not -- and three accent-coloured icons in one narrow column read as
// decoration applied by rote. The label alone does the work.
function SectionHeading({ label }: { readonly label: string }): React.JSX.Element {
  return <p className="mb-2 text-label-caps uppercase text-textMuted">{label}</p>;
}

export function LayerDetailPanel({
  layer,
  statuses,
}: LayerDetailPanelProps): React.JSX.Element {
  return (
    <div className="space-y-5">
      <header>
        <div className="flex items-baseline gap-2">
          <span className="font-mono text-[11px] font-semibold text-textMuted">L{layer.ordinal}</span>
          <h3 className="text-headline-sm text-textPrimary">{layer.title}</h3>
        </div>
        <p className="mt-1.5 text-body-sm leading-relaxed text-textSecondary">{layer.tagline}</p>
      </header>

      <section>
        <SectionHeading label="What it is responsible for" />
        <ul className="space-y-1.5">
          {layer.responsibilities.map((responsibility) => (
            <li key={responsibility} className="flex gap-2 text-body-sm text-textSecondary">
              <span className="mt-1.5 h-1 w-1 shrink-0 rounded-full bg-accentPrimary" />
              <span className="leading-relaxed">{responsibility}</span>
            </li>
          ))}
        </ul>
      </section>

      <section>
        <SectionHeading label="Telemetry it emits" />
        <div className="flex flex-wrap gap-1.5">
          {layer.eventsEmitted.map((eventType) => (
            <span
              key={eventType}
              className="rounded-full border border-borderSubtle bg-surfaceContainer px-2 py-0.5 text-[10px] font-mono text-textSecondary"
            >
              {eventType}
            </span>
          ))}
        </div>
      </section>

      <section>
        <SectionHeading label="Where the code lives" />
        <ul className="space-y-1">
          {layer.implementedBy.map((packagePath) => (
            <li key={packagePath}>
              <code className="font-mono text-[11px] break-all text-textSecondary">
                {packagePath}
              </code>
            </li>
          ))}
        </ul>
        {layer.serviceIds.length > 0 && (
          <ul className="mt-2 space-y-1">
            {layer.serviceIds.map((serviceId) => {
              const service = meshServicesById[serviceId];
              const status = statuses.find((entry) => entry.serviceId === serviceId);
              return (
                <li key={serviceId} className="text-[11px] text-textMuted">
                  <span className="text-textSecondary">{service.displayName}</span> - port{" "}
                  {service.composePort}, probe{" "}
                  <code className="font-mono">{service.healthPath}</code>
                  {status ? ` - ${status.health} in ${status.latencyMs}ms` : ""}
                  {status?.detail ? ` (${status.detail})` : ""}
                </li>
              );
            })}
          </ul>
        )}
      </section>

      <section className="flex flex-wrap gap-2">
        <Link
          href={{ pathname: "/visualise/run", query: { scenario: layer.scenarioId } }}
          className="inline-flex items-center gap-1.5 rounded-md border border-accentPrimary/30 bg-accentPrimary/10 px-3 py-1.5 text-label-sm font-semibold text-accentPrimary transition-colors hover:bg-accentPrimary/20"
        >
          <Play className="h-3.5 w-3.5" />
          Run this stage
        </Link>
        <Link
          href={layer.docRoute}
          className="inline-flex items-center gap-1.5 rounded-md border border-borderSubtle bg-bgSurface px-3 py-1.5 text-label-sm font-semibold text-textSecondary transition-colors hover:bg-bgSurfaceHover hover:text-textPrimary"
        >
          <BookOpen className="h-3.5 w-3.5" />
          Read the docs
        </Link>
      </section>
      <p className="text-[11px] leading-relaxed text-textMuted">{layer.scenarioHint}</p>
    </div>
  );
}
