// Constants for the settlement page -- the one screen where a human finishes what an agent began.
//
// Trimmed down from the old checkout page's constants. The catalog listing, the fallback SKU
// table and the order-creation response shape are all gone: this page never creates an order and
// never lets anyone choose a product. It pays an order that a buyer agent already opened, and an
// order id it cannot find is an error rather than an invitation to make a new one.

import type { SettlementInvoice } from "@/types/telemetryEventTypes";

/** GET /api/v1/checkout/config, proxied through the dashboard. */
export interface CheckoutConfig {
  readonly keyId: string | null;
  readonly credentialsPresent: boolean;
}

/** What the client proves to itself after Razorpay returns and the engine re-checks the HMAC. */
export interface VerificationArtifact {
  readonly verified: boolean;
  readonly orderId: string;
  readonly paymentId: string;
  readonly signature: string;
}

/**
 * An order a buyer agent opened and cannot pay.
 *
 * `amountPaise` travels WITH the order id rather than being re-derived from a SKU price. The
 * agent's amount is the settled total after negotiation, volume tiers, promotions, shipping and
 * statutory tax; recomputing it from a catalog row would produce a different number and pay a
 * different order than the one the mandate chain points at.
 */
export interface PayableAgentOrder {
  readonly razorpayOrderId: string;
  readonly amountPaise: number;
  readonly paymentId: string | null;
  readonly sessionId: string | null;
  readonly capturedAtMs: number | null;
  /**
   * Null for an order reached by deep link, because the link carries only an id and an amount.
   * The invoice lives on the PAYMENT_CAPTURED event, so it is present for any order still in
   * the stream and absent once the stream is cleared.
   */
  readonly invoice: SettlementInvoice | null;
}

export const scriptSrcRazorpayCheckout = "https://checkout.razorpay.com/v1/checkout.js";

export function formatPaiseToInr(paise: number): string {
  return (paise / 100).toLocaleString("en-IN", {
    style: "currency",
    currency: "INR",
    minimumFractionDigits: 2,
  });
}

// Razorpay's published test instruments. Test mode only -- these move no real money, and there
// are no live credentials anywhere in this package.
export const testCardNumber = "4100 2800 0000 1007";
export const testCardExpiry = "12/26";
export const testCardCvv = "123";
export const testUpiId = "test@razorpay";
