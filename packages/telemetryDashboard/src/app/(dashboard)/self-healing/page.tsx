"use client";

import React from "react";
import { HealingDiffViewer } from "@/components/healingDiffViewer";
import { useTelemetry } from "@/context/telemetryContext";

const pageTitle = "Sub-300ms Vector Self-Healing";
const pageDescription = "Qdrant ANN cosine similarity matching, out-of-stock item substitution, and negative constraint audit.";

export default function SelfHealingPage(): React.JSX.Element {
  const { events } = useTelemetry();

  return (
    <div className="space-y-4 max-w-7xl mx-auto">
      <div>
        <h2 className="text-lg font-semibold text-textPrimary">{pageTitle}</h2>
        <p className="text-xs text-textSecondary">{pageDescription}</p>
      </div>
      <div className="min-h-[640px]">
        <HealingDiffViewer events={events} />
      </div>
    </div>
  );
}
