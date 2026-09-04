"use client";

import React from "react";
import { Boxes } from "lucide-react";
import { summarisePackageUsage } from "@/lib/packagePipeline";
import type { ProtocolStepRecord } from "@/types/protocolRunTypes";

const stripLabel = "Packages touched";
const idleDotClass = "bg-textMuted";
const activeDotClass = "bg-accentPrimary";
const multiplicationSign = "×";

export interface PackagesTouchedStripProps {
  readonly steps: readonly ProtocolStepRecord[];
}

// Zero counts are rendered, not filtered out: "did this run touch the healer?" is answered by a
// visible `vectorHealer x0` rather than by a package silently missing from the strip.
export function PackagesTouchedStrip({ steps }: PackagesTouchedStripProps): React.JSX.Element {
  const usage = summarisePackageUsage(steps);

  return (
    <div>
      <div className="mb-2 flex items-center gap-1.5 px-1">
        <Boxes className="h-3.5 w-3.5 text-accentPrimary" />
        <span className="text-label-caps uppercase text-textMuted">{stripLabel}</span>
      </div>
      <ul className="flex flex-wrap gap-1.5">
        {usage.map((entry) => {
          const isActive = entry.stepCount > 0;
          return (
            <li
              key={entry.packageName}
              title={
                entry.layerTitles.length > 0
                  ? `Layers: ${entry.layerTitles.join(", ")}`
                  : undefined
              }
              className={`inline-flex items-center gap-1.5 rounded-md border px-2 py-1 font-mono text-[11px] ${
                isActive
                  ? "border-accentPrimary/30 bg-accentPrimary/5 text-textPrimary"
                  : "border-borderSubtle text-textMuted"
              }`}
            >
              <span
                className={`h-1.5 w-1.5 shrink-0 rounded-full ${isActive ? activeDotClass : idleDotClass}`}
              />
              {entry.packageName}
              <span className={isActive ? "text-textSecondary" : "text-textMuted"}>
                {multiplicationSign}
                {entry.stepCount}
              </span>
            </li>
          );
        })}
      </ul>
    </div>
  );
}
