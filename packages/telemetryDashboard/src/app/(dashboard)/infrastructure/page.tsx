"use client";

import React from "react";
import { WebhookFeed } from "@/components/webhookFeed";
import { useTelemetry } from "@/context/telemetryContext";

const pageTitle = "Razorpay Rails & 2PC Infrastructure";
const pageDescription = "Live webhook ingestion, multi-party Route split transfers, 2PC saga rollback execution, and GSTR-1 tax hashing.";

export default function InfrastructurePage(): React.JSX.Element {
  const { events } = useTelemetry();

  return (
    <div className="space-y-4 max-w-7xl mx-auto">
      <div>
        <h2 className="text-lg font-semibold text-textPrimary">{pageTitle}</h2>
        <p className="text-xs text-textSecondary">{pageDescription}</p>
      </div>
      <div className="min-h-[640px]">
        <WebhookFeed events={events} />
      </div>
    </div>
  );
}
