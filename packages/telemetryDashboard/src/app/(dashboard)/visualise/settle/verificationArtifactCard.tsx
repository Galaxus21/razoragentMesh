"use client";

import React from "react";
import { ShieldCheck } from "lucide-react";
import { panelClass } from "@/constants/playgroundConstants";
import type { VerificationArtifact } from "./settleConstants";

interface VerificationArtifactCardProps {
  readonly artifact: VerificationArtifact | null;
}

// The artifact is the point of this page, not the modal.
//
// A completed payment proves only that Razorpay accepted a card. What is worth showing is that
// the mandate engine recomputed HMAC-SHA256 over `order_id|payment_id` with the key secret and
// got the same signature Razorpay sent -- server-side, with a constant-time comparison. The
// signature is rendered in full rather than truncated so it can be checked against the Razorpay
// dashboard by eye.
export function VerificationArtifactCard({
  artifact,
}: VerificationArtifactCardProps): React.JSX.Element | null {
  if (!artifact) {
    return null;
  }

  return (
    <div className={`${panelClass} border-l-4 border-l-statusSuccess p-5`}>
      <div className="mb-3 flex items-center gap-2">
        <ShieldCheck className="h-4 w-4 text-statusSuccess" />
        <h3 className="text-label-sm font-semibold text-textPrimary">
          Signature verified server-side
        </h3>
      </div>

      <p className="mb-3 text-body-sm text-textSecondary">
        The mandate engine recomputed <code className="font-mono text-[11px]">HMAC-SHA256</code> over{" "}
        <code className="font-mono text-[11px]">order_id|payment_id</code> and compared it against
        Razorpay&apos;s signature in constant time. The key secret never left the engine.
      </p>

      <dl className="space-y-2">
        <div>
          <dt className="text-label-caps uppercase text-textMuted">Order</dt>
          <dd className="break-all font-mono text-body-sm text-textPrimary">{artifact.orderId}</dd>
        </div>
        <div>
          <dt className="text-label-caps uppercase text-textMuted">Payment</dt>
          <dd className="break-all font-mono text-body-sm text-textPrimary">{artifact.paymentId}</dd>
        </div>
        <div>
          <dt className="text-label-caps uppercase text-textMuted">Signature</dt>
          <dd className="break-all font-mono text-[11px] leading-relaxed text-textSecondary">
            {artifact.signature}
          </dd>
        </div>
      </dl>
    </div>
  );
}
