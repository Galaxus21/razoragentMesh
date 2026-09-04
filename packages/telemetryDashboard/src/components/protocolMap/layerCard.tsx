"use client";

import React from "react";
import { ArrowDown } from "lucide-react";
import { meshServicesById } from "@/constants/meshServiceRegistry";
import type { ProtocolLayerNode } from "@/constants/protocolLayerMap";
import type { MeshServiceStatus } from "@/server/meshHealth/probeMeshServices";

export interface LayerCardProps {
  readonly layer: ProtocolLayerNode;
  readonly statuses: readonly MeshServiceStatus[];
  readonly isProbing: boolean;
  readonly isSelected: boolean;
  readonly isLast: boolean;
  readonly onSelect: (layerId: string) => void;
}

// A healthy service is the expected case, so it gets no colour: it is named in muted text and
// nothing else. Green pills on every row meant six of them were lit at all times, which made the
// one that mattered -- a service that had actually fallen over -- no more visible than the five
// that were fine. Colour is spent on the exception now, not the norm.
const downServiceClass = "text-statusError";
const settledServiceClass = "text-textMuted";
const probingSuffix = "...";
const unknownSuffix = "?";

function findStatus(
  statuses: readonly MeshServiceStatus[],
  serviceId: string
): MeshServiceStatus | undefined {
  return statuses.find((status) => status.serviceId === serviceId);
}

export function LayerCard({
  layer,
  statuses,
  isProbing,
  isSelected,
  isLast,
  onSelect,
}: LayerCardProps): React.JSX.Element {
  return (
    <li>
      <button
        type="button"
        onClick={() => onSelect(layer.layerId)}
        className={`w-full rounded-xl border p-4 text-left transition-colors cursor-pointer ${
          isSelected
            ? "border-accentPrimary bg-accentSubtle/40"
            : "border-borderSubtle bg-bgSurface hover:bg-bgSurfaceHover"
        }`}
      >
        <div className="flex flex-wrap items-center gap-2">
          <span className="rounded-full border border-borderSubtle bg-surfaceContainer px-2 py-0.5 text-[10px] font-mono font-semibold text-textSecondary">
            L{layer.ordinal}
          </span>
          <h3 className="text-body-md font-semibold text-textPrimary">{layer.title}</h3>

          {layer.serviceIds.map((serviceId) => {
            const status = findStatus(statuses, serviceId);
            const service = meshServicesById[serviceId];
            const isDown = Boolean(status) && status?.health !== "UP";
            return (
              <span
                key={serviceId}
                title={
                  status?.detail ??
                  `${service.displayName} ${service.healthPath} - ${status?.latencyMs ?? 0}ms`
                }
                className={`inline-flex items-center gap-1 text-[10px] ${
                  isDown ? downServiceClass : settledServiceClass
                }`}
              >
                {isDown && <span className="h-1.5 w-1.5 rounded-full bg-statusError" />}
                {service.displayName}
                {isDown ? ` ${status?.health}` : !status ? (isProbing ? probingSuffix : unknownSuffix) : ""}
              </span>
            );
          })}
        </div>

        <p className="mt-1.5 text-body-sm leading-relaxed text-textSecondary">{layer.tagline}</p>
      </button>

      {!isLast && (
        <div className="flex justify-center py-1">
          <ArrowDown className="h-3.5 w-3.5 text-textMuted" aria-hidden="true" />
        </div>
      )}
    </li>
  );
}
