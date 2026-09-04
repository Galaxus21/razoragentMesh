"use client";

// The handoff, rendered where the agent's run is being watched.
//
// This card is the point in the demo where the honest limit of agentic commerce becomes visible.
// The agent verified a three-mandate AP2 chain, passed the budget gate, split the settlement
// across Route recipients, and opened a REAL Razorpay order stamped with the cart and execution
// hashes. What it cannot do is authorise the charge: no Razorpay rail lets a fresh account move
// money without a prior human act. So the run ends with a payable order and a person, which is
// exactly what the protocol is designed to produce -- not a dead end, a deliberate boundary.
//
// The link carries the order id rather than a SKU: the settle page must open the modal on THIS
// order, the one whose notes carry the mandate hashes. Creating a second order for the same
// amount would settle the same money against an order no mandate points at, which is the one
// thing that would make the evidence trail meaningless.

import React from "react";
import Link from "next/link";
import { ArrowRight, Wallet } from "lucide-react";
import type { SettlementOrderHandoff } from "@/lib/liveAgentSteps";

interface SettlementHandoffCardProps {
  readonly order: SettlementOrderHandoff;
}

function formatPaiseToInr(paise: number): string {
  return (paise / 100).toLocaleString("en-IN", {
    style: "currency",
    currency: "INR",
    minimumFractionDigits: 2
  });
}

export function SettlementHandoffCard({ order }: SettlementHandoffCardProps): React.JSX.Element {
  const checkoutHref = `/visualise/settle?orderId=${encodeURIComponent(
    order.razorpayOrderId
  )}&amountPaise=${order.amountPaise}`;

  return (
    <div className="rounded-lg border border-accentPrimary/40 bg-accentPrimary/5 p-4">
      <div className="flex items-center gap-2">
        <Wallet className="h-4 w-4 text-accentPrimary" />
        <h3 className="text-label-sm font-semibold text-textPrimary">
          Agent opened a real Razorpay order
        </h3>
      </div>

      <p className="mt-2 text-body-sm leading-relaxed text-textSecondary">
        The mandate chain verified and the settlement split. The agent then created a live
        test-mode order carrying its cart and execution hashes in Razorpay&apos;s{" "}
        <code className="font-mono text-[11px]">notes</code>. It cannot authorise the charge
        itself, so it hands you the order to complete.
      </p>

      <dl className="mt-3 grid grid-cols-1 gap-2 sm:grid-cols-2">
        <div>
          <dt className="text-label-caps uppercase text-textMuted">Razorpay order</dt>
          <dd className="break-all font-mono text-body-sm text-textPrimary">
            {order.razorpayOrderId}
          </dd>
        </div>
        <div>
          <dt className="text-label-caps uppercase text-textMuted">Amount</dt>
          <dd className="font-mono text-body-sm font-semibold text-textPrimary">
            {formatPaiseToInr(order.amountPaise)}
          </dd>
        </div>
        {order.paymentId && (
          <div className="sm:col-span-2">
            <dt className="text-label-caps uppercase text-textMuted">Mesh settlement id</dt>
            <dd className="break-all font-mono text-[11px] text-textSecondary">
              {order.paymentId}
            </dd>
          </div>
        )}
      </dl>

      <Link
        href={checkoutHref}
        className="mt-3 inline-flex items-center gap-2 rounded-lg bg-brandBlue px-4 py-2 text-label-sm font-medium text-white shadow transition-colors hover:bg-brandBlue/90"
      >
        Complete this payment
        <ArrowRight className="h-4 w-4" />
      </Link>
    </div>
  );
}
