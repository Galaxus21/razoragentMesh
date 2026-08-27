"use client";

import React from "react";
import { NegotiationChart } from "@/components/negotiationChart";
import { useTelemetry } from "@/context/telemetryContext";

const pageTitle = "B2B Dynamic Negotiation Hub";
const pageDescription = "x402-INR bilateral discount curves, micro-fee anti-spam escrow, and AST contract verification.";

export default function NegotiationHubPage(): React.JSX.Element {
  const { events } = useTelemetry();

  return (
    <div className="space-y-4 max-w-7xl mx-auto">
      <div>
        <h2 className="text-lg font-semibold text-textPrimary">{pageTitle}</h2>
        <p className="text-xs text-textSecondary">{pageDescription}</p>
      </div>
      <div className="min-h-[640px]">
        <NegotiationChart events={events} />
      </div>
    </div>
  );
}
