"use client";

import React from "react";
import { CreditCard } from "lucide-react";
import { panelClass } from "@/constants/playgroundConstants";
import {
  testCardCvv,
  testCardExpiry,
  testCardNumber,
  testUpiId,
} from "./settleConstants";

// Razorpay's test instruments, on the page rather than in the README.
//
// Nothing here can move real money: these only work against test-mode keys, and the mandate
// engine refuses to create an order at all unless test credentials are configured.
export function TestCredentialsCard(): React.JSX.Element {
  return (
    <div className={`${panelClass} p-4`}>
      <div className="mb-3 flex items-center gap-2">
        <CreditCard className="h-4 w-4 text-accentPrimary" />
        <h3 className="text-label-sm font-semibold text-textPrimary">
          Test credentials — no real money can move
        </h3>
      </div>

      <dl className="grid grid-cols-1 gap-x-6 gap-y-2 sm:grid-cols-2">
        <div className="flex items-baseline justify-between gap-3">
          <dt className="text-body-sm text-textSecondary">Card</dt>
          <dd className="font-mono text-body-sm tabular-nums text-textPrimary">{testCardNumber}</dd>
        </div>
        <div className="flex items-baseline justify-between gap-3">
          <dt className="text-body-sm text-textSecondary">Expiry</dt>
          <dd className="font-mono text-body-sm tabular-nums text-textPrimary">{testCardExpiry}</dd>
        </div>
        <div className="flex items-baseline justify-between gap-3">
          <dt className="text-body-sm text-textSecondary">CVV</dt>
          <dd className="font-mono text-body-sm tabular-nums text-textPrimary">{testCardCvv}</dd>
        </div>
        <div className="flex items-baseline justify-between gap-3">
          <dt className="text-body-sm text-textSecondary">UPI</dt>
          <dd className="font-mono text-body-sm text-textPrimary">{testUpiId}</dd>
        </div>
      </dl>
    </div>
  );
}
