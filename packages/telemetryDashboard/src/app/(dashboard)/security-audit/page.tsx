"use client";

import React from "react";
import { MandateExplorer } from "@/components/mandateExplorer";
import { useTelemetry } from "@/context/telemetryContext";

const pageTitle = "AP2 Cryptographic Mandate Audit";
const pageDescription = "Ed25519 asymmetric signature chains, Intent/Cart/Execution verification, and RFC 8785 Canonical JCS inspection.";

export default function SecurityAuditPage(): React.JSX.Element {
  const { events } = useTelemetry();

  return (
    <div className="space-y-4 max-w-7xl mx-auto">
      <div>
        <h2 className="text-lg font-semibold text-textPrimary">{pageTitle}</h2>
        <p className="text-xs text-textSecondary">{pageDescription}</p>
      </div>
      <div className="min-h-[640px]">
        <MandateExplorer events={events} />
      </div>
    </div>
  );
}
