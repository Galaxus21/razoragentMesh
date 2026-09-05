"use client";

// Settle -- the human half of an agentic purchase.
//
// This replaces the old "Human Checkout" tab in the Merchant section, which did two unrelated
// jobs on one screen: it let a person shop the catalog and pay for a SKU like any web store, and
// it also completed orders that buyer agents had opened. The first job did not belong in a
// merchant console at all (a merchant publishes inventory; it does not buy its own stock), and
// mixing them meant the page could CREATE a Razorpay order -- the one action that quietly breaks
// the demo's evidence trail, because a fresh order for the same rupee amount carries no cart or
// execution mandate hash and is therefore settled money no mandate points at.
//
// What is left is the single thing that has to exist: an agent opens a real order, cannot
// authorise it, and hands it to a person. So this page only ever pays an EXISTING order.
//
// It lives under Visualise rather than Merchant because it is the last step of an agent run,
// reached from the handoff card on the Live Agent screen. It is a sibling of that screen rather
// than part of it: Live Agent is for watching, and paying is an act.

import React, { Suspense, useCallback, useEffect, useMemo, useState } from "react";
import Script from "next/script";
import Link from "next/link";
import { useSearchParams } from "next/navigation";
import { AlertCircle, ArrowLeft, ArrowRight, Bot, Inbox, Wallet } from "lucide-react";
import { panelClass } from "@/constants/playgroundConstants";
import { useTelemetry } from "@/context/telemetryContext";
import { TestCredentialsCard } from "./testCredentialsCard";
import { VerificationArtifactCard } from "./verificationArtifactCard";
import { InvoiceCard } from "./invoiceCard";
import {
  CheckoutConfig,
  formatPaiseToInr,
  PayableAgentOrder,
  scriptSrcRazorpayCheckout,
  VerificationArtifact,
} from "./settleConstants";

declare global {
  interface Window {
    Razorpay: any;
  }
}

interface RazorpaySuccessResponse {
  readonly razorpay_payment_id: string;
  readonly razorpay_order_id: string;
  readonly razorpay_signature: string;
}

const pageTitle = "Settle an agent's order";
const pageDescription =
  "A buyer agent verifies its mandate chain, clears the budget gate, splits the settlement across " +
  "Route recipients and opens a real Razorpay order stamped with its cart and execution hashes. " +
  "No Razorpay rail lets it authorise the charge on its own, so the run ends here, with a person. " +
  "Paying below settles that order; nothing new is created.";

/**
 * Every order an agent has opened in the current stream, newest first.
 *
 * Read from PAYMENT_CAPTURED rather than fetched, because the mesh has no "orders awaiting a
 * human" endpoint -- the telemetry stream IS the record of what the agents did. That has an
 * honest consequence worth stating on the page: clearing the stream empties this list without
 * touching the orders, which still exist at Razorpay and are still payable by direct link.
 */
function readPayableOrders(
  events: ReturnType<typeof useTelemetry>["events"]
): readonly PayableAgentOrder[] {
  const seen = new Set<string>();
  const orders: PayableAgentOrder[] = [];

  for (const event of events) {
    if (event.eventType !== "PAYMENT_CAPTURED") {
      continue;
    }
    const { razorpayOrderId, amountPaise, paymentId, invoice } = event.payload;
    if (!razorpayOrderId || seen.has(razorpayOrderId)) {
      continue;
    }
    seen.add(razorpayOrderId);
    orders.push({
      razorpayOrderId,
      amountPaise,
      paymentId: paymentId || null,
      sessionId: event.sessionId ?? null,
      capturedAtMs: event.timestampMs ?? null,
      invoice: invoice ?? null,
    });
  }

  return orders.sort((left, right) => (right.capturedAtMs ?? 0) - (left.capturedAtMs ?? 0));
}

export default function SettlePage(): React.JSX.Element {
  // useSearchParams suspends during prerender; without this boundary the whole route opts out of
  // static generation and the build warns.
  return (
    <Suspense fallback={<p className="p-6 text-body-sm text-textMuted">Loading settlement…</p>}>
      <SettleBody />
    </Suspense>
  );
}

function SettleBody(): React.JSX.Element {
  const searchParams = useSearchParams();
  const { events } = useTelemetry();

  const [selectedOrderId, setSelectedOrderId] = useState<string | null>(null);
  const [isProcessing, setIsProcessing] = useState<boolean>(false);
  const [statusMessage, setStatusMessage] = useState<string | null>(null);
  const [errorMessage, setErrorMessage] = useState<string | null>(null);
  const [verificationArtifact, setVerificationArtifact] = useState<VerificationArtifact | null>(
    null
  );

  const streamOrders = useMemo(() => readPayableOrders(events), [events]);

  // A deep link from the handoff card carries both the order id and its amount, so it still works
  // after the stream is cleared or reloaded -- the link is the durable handle, not the buffer.
  const linkedOrderId = searchParams.get("orderId");
  const linkedAmountPaise = Number(searchParams.get("amountPaise"));
  const linkedOrder: PayableAgentOrder | null =
    linkedOrderId && Number.isFinite(linkedAmountPaise) && linkedAmountPaise > 0
      ? {
          razorpayOrderId: linkedOrderId,
          amountPaise: linkedAmountPaise,
          paymentId: null,
          sessionId: null,
          capturedAtMs: null,
          invoice: null,
        }
      : null;

  // The linked order is merged in rather than shown instead of the list, so arriving by link and
  // arriving by navigation land on the same screen.
  const payableOrders = useMemo(() => {
    if (!linkedOrder) {
      return streamOrders;
    }
    const known = streamOrders.find(
      (order) => order.razorpayOrderId === linkedOrder.razorpayOrderId
    );
    return known ? streamOrders : [linkedOrder, ...streamOrders];
  }, [linkedOrder, streamOrders]);

  useEffect(() => {
    if (linkedOrder) {
      setSelectedOrderId(linkedOrder.razorpayOrderId);
    }
  }, [linkedOrder?.razorpayOrderId]);

  const selectedOrder =
    payableOrders.find((order) => order.razorpayOrderId === selectedOrderId) ??
    payableOrders[0] ??
    null;

  const verifyPaymentSignature = useCallback(
    async (paymentData: RazorpaySuccessResponse): Promise<void> => {
      try {
        const verifyRes = await fetch("/api/mesh/checkout/verify", {
          method: "POST",
          headers: { "Content-Type": "application/json" },
          body: JSON.stringify({
            razorpayOrderId: paymentData.razorpay_order_id,
            razorpayPaymentId: paymentData.razorpay_payment_id,
            razorpaySignature: paymentData.razorpay_signature,
          }),
        });

        const verifyData = await verifyRes.json().catch(() => ({}));
        if (verifyRes.ok && verifyData.verified) {
          setVerificationArtifact({
            verified: true,
            orderId: paymentData.razorpay_order_id,
            paymentId: paymentData.razorpay_payment_id,
            signature: paymentData.razorpay_signature,
          });
          setStatusMessage("Payment captured and signature verified server-side.");
        } else {
          throw new Error(verifyData.detail || "Server signature verification failed");
        }
      } catch (err: unknown) {
        setErrorMessage(err instanceof Error ? err.message : String(err));
      } finally {
        setIsProcessing(false);
      }
    },
    []
  );

  const handlePayOrder = async (): Promise<void> => {
    if (!selectedOrder) {
      return;
    }
    setIsProcessing(true);
    setErrorMessage(null);
    setVerificationArtifact(null);
    setStatusMessage("Fetching checkout configuration…");

    try {
      const configResponse = await fetch("/api/mesh/checkout/config");
      if (!configResponse.ok) {
        throw new Error(`Could not read checkout configuration (${configResponse.status})`);
      }
      const config: CheckoutConfig = await configResponse.json();
      if (!config.credentialsPresent || !config.keyId) {
        throw new Error(
          "The mandate engine is running without Razorpay credentials, so this order cannot be paid."
        );
      }

      if (!window.Razorpay) {
        throw new Error("Razorpay checkout script has not loaded yet. Check your connection.");
      }

      setStatusMessage(`Opening checkout on ${selectedOrder.razorpayOrderId}…`);

      const rzpInstance = new window.Razorpay({
        key: config.keyId,
        amount: selectedOrder.amountPaise,
        currency: "INR",
        name: "RazorAgent Mesh",
        description: `Agent settlement ${selectedOrder.razorpayOrderId}`,
        order_id: selectedOrder.razorpayOrderId,
        prefill: {
          name: "Demo Human Buyer",
          email: "buyer@example.com",
          contact: "9999999999",
        },
        theme: { color: "#0c2340" },
        modal: {
          ondismiss: () => {
            setIsProcessing(false);
            setStatusMessage("Checkout dismissed. No charge was made and the order is still open.");
          },
        },
        handler: async (response: RazorpaySuccessResponse) => {
          setStatusMessage("Payment received. Verifying HMAC-SHA256 signature server-side…");
          await verifyPaymentSignature(response);
        },
      });

      rzpInstance.on("payment.failed", (failure: any) => {
        setIsProcessing(false);
        setStatusMessage(
          `Payment failed or cancelled: ${failure.error?.description || "Payment declined"}`
        );
      });
      rzpInstance.open();
    } catch (err: unknown) {
      setIsProcessing(false);
      setStatusMessage(null);
      setErrorMessage(err instanceof Error ? err.message : String(err));
    }
  };

  return (
    <div className="mx-auto max-w-4xl space-y-4">
      <Script src={scriptSrcRazorpayCheckout} strategy="lazyOnload" />

      <header className="space-y-1.5">
        <div className="flex items-center gap-2">
          <Bot className="h-4 w-4 text-accentPrimary" />
          <h2 className="text-headline-sm text-textPrimary">{pageTitle}</h2>
        </div>
        <p className="max-w-3xl text-body-sm leading-relaxed text-textSecondary">
          {pageDescription}
        </p>
      </header>

      <section className={`${panelClass} p-5`}>
        <div className="flex items-center gap-2 border-b border-borderSubtle pb-3">
          <Inbox className="h-4 w-4 text-textPrimary" />
          <h3 className="text-label-sm font-semibold text-textPrimary">
            Orders awaiting authorisation
          </h3>
          <span className="ml-auto font-mono text-[11px] text-textMuted">
            {payableOrders.length} in this stream
          </span>
        </div>

        {payableOrders.length === 0 ? (
          <div className="flex flex-col items-center gap-2 py-8 text-center">
            <Wallet className="h-5 w-5 text-textMuted" />
            <p className="text-body-sm text-textSecondary">No agent has opened an order yet.</p>
            <p className="max-w-md text-body-sm text-textMuted">
              This list is built from the live telemetry stream, so clearing the stream empties it.
              Orders already opened still exist at Razorpay and stay payable through the link on
              the handoff card.
            </p>
            <Link
              href="/visualise"
              className="mt-1 inline-flex items-center gap-1.5 text-label-sm text-accentPrimary hover:underline"
            >
              <ArrowLeft className="h-3.5 w-3.5" />
              Watch an agent run
            </Link>
          </div>
        ) : (
          <ul className="mt-3 space-y-2">
            {payableOrders.map((order) => {
              const isSelected = order.razorpayOrderId === selectedOrder?.razorpayOrderId;
              return (
                <li key={order.razorpayOrderId}>
                  <button
                    type="button"
                    onClick={() => setSelectedOrderId(order.razorpayOrderId)}
                    className={`w-full rounded-lg border p-3.5 text-left transition-colors ${
                      isSelected
                        ? "border-accentPrimary bg-accentPrimary/5 ring-1 ring-accentPrimary"
                        : "border-borderSubtle bg-bgSurface hover:border-borderStrong"
                    }`}
                  >
                    <div className="flex flex-wrap items-baseline justify-between gap-2">
                      <span className="break-all font-mono text-body-sm text-textPrimary">
                        {order.razorpayOrderId}
                      </span>
                      <span className="font-mono text-body-md font-semibold text-textPrimary">
                        {formatPaiseToInr(order.amountPaise)}
                      </span>
                    </div>
                    {order.paymentId && (
                      <p className="mt-1 break-all font-mono text-[11px] text-textMuted">
                        mesh settlement {order.paymentId}
                      </p>
                    )}
                  </button>
                </li>
              );
            })}
          </ul>
        )}
      </section>

      {selectedOrder && (
        <section className={`${panelClass} space-y-4 border-l-4 border-l-accentPrimary p-5`}>
          <dl className="grid grid-cols-1 gap-3 sm:grid-cols-2">
            <div>
              <dt className="text-label-caps uppercase text-textMuted">Paying order</dt>
              <dd className="break-all font-mono text-body-sm text-textPrimary">
                {selectedOrder.razorpayOrderId}
              </dd>
            </div>
            <div>
              <dt className="text-label-caps uppercase text-textMuted">Amount payable</dt>
              <dd className="font-mono text-xl font-bold text-textPrimary">
                {formatPaiseToInr(selectedOrder.amountPaise)}
              </dd>
            </div>
          </dl>

          <InvoiceCard
            invoice={selectedOrder.invoice}
            razorpayOrderId={selectedOrder.razorpayOrderId}
          />

          <div className="flex flex-col gap-3 border-t border-borderSubtle pt-4 sm:flex-row sm:items-center sm:justify-between">
            <Link
              href="/visualise"
              className="inline-flex items-center gap-1.5 text-label-sm text-accentPrimary hover:underline"
            >
              <ArrowLeft className="h-3.5 w-3.5" />
              Back to the agent run
            </Link>
            <button
              type="button"
              onClick={handlePayOrder}
              disabled={isProcessing}
              className="flex items-center justify-center gap-2 rounded-lg bg-brandBlue px-5 py-2.5 text-label-sm font-medium text-white shadow transition-colors hover:bg-brandBlue/90 disabled:opacity-50"
            >
              {isProcessing ? "Processing…" : "Pay this order"}
              <ArrowRight className="h-4 w-4" />
            </button>
          </div>

          {statusMessage && (
            <div className="flex items-center gap-2 rounded-lg bg-surfaceContainer/60 p-3 text-body-sm text-textSecondary">
              <span className="h-2 w-2 rounded-full bg-statusInfo animate-pulseFast" />
              <span>{statusMessage}</span>
            </div>
          )}

          {errorMessage && (
            <div className="flex items-start gap-2 rounded-lg border border-statusError/30 bg-statusError/10 p-3.5 text-body-sm text-statusError">
              <AlertCircle className="mt-0.5 h-4 w-4 shrink-0" />
              <div>
                <p className="font-semibold">Payment halted</p>
                <p className="mt-0.5">{errorMessage}</p>
              </div>
            </div>
          )}

          {verificationArtifact && <VerificationArtifactCard artifact={verificationArtifact} />}
        </section>
      )}

      <TestCredentialsCard />
    </div>
  );
}
