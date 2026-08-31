"use client";

import React, { useMemo, useState } from "react";
import { AlertTriangle, Network, RefreshCw } from "lucide-react";
import { LayerCard } from "@/components/protocolMap/layerCard";
import { LayerDetailPanel } from "@/components/protocolMap/layerDetailPanel";
import { panelClass } from "@/constants/playgroundConstants";
import { protocolLayerNodes } from "@/constants/protocolLayerMap";
import { useMeshHealth } from "@/hooks/useMeshHealth";

const pageTitle = "Protocol Map";
const pageDescription =
  "The six layers of the mesh, L0 through L5, each probed live. Pick a layer to see what it owns, the telemetry it emits, the package that implements it, and a scenario that exercises it.";
const firstLayerId = protocolLayerNodes[0]?.layerId ?? "";

export default function ProtocolMapPage(): React.JSX.Element {
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

      {downCount > 0 && (
        <div className="flex items-start gap-2 rounded-xl border border-statusWarning/30 bg-statusWarning/5 p-4">
          <AlertTriangle className="mt-0.5 h-4 w-4 shrink-0 text-statusWarning" />
          <div>
            <p className="text-body-md font-semibold text-textPrimary">
              {downCount} of {health.statuses.length} services are not answering
            </p>
            <p className="mt-1 text-body-sm text-textSecondary">
              Layers backed by those services cannot be exercised until they are up:{" "}
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
          <div className="mb-2 flex items-center gap-1.5 px-1">
            <Network className="h-3.5 w-3.5 text-accentPrimary" />
            <span className="text-label-caps uppercase text-textMuted">Mesh layers</span>
          </div>
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
    </div>
  );
}
