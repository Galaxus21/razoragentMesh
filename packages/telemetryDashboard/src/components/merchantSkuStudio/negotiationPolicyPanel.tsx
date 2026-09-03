"use client";

// The merchant's negotiation opt-in, and the band they will negotiate inside.
//
// Why this exists: there is no merchant-side agent in this mesh. The merchant is represented in a
// negotiation entirely by this policy -- the gateway reads it to decide whether to hold a bid at
// all and how low the seller's ask may go. Before this panel, that policy could only be written
// by PUTting raw JSON at the merchant API, so in practice no merchant had one, and the gateway
// took the seller's price from the BUYER's request body instead.
//
// The switch defaults to off and saving it off is a real choice a merchant can make. Everything
// below the switch describes how they negotiate; the switch itself decides whether they do.

import React from "react";
import { Handshake, Loader2, Save } from "lucide-react";
import {
  buildNegotiationPolicyPayload,
  gatewayMaxNegotiationTurns,
  maxMarginFloorBps,
  maxPolicyNegotiationTurns,
  minMarginFloorBps,
  minPolicyNegotiationTurns,
  NegotiationPolicyFormData,
  PolicyValidationErrors,
  previewFloorPricePaise,
} from "@/lib/negotiationPolicyValidator";

export interface NegotiationPolicyPanelProps {
  readonly policy: NegotiationPolicyFormData;
  readonly errors: PolicyValidationErrors;
  readonly isSaving: boolean;
  readonly saveResult: { readonly ok: boolean; readonly message: string } | null;
  /** The list price of the SKU being edited, used only to show what the floor works out to. */
  readonly previewListPricePaise: number;
  readonly onUpdatePolicy: (patch: Partial<NegotiationPolicyFormData>) => void;
  readonly onSavePolicy: () => void;
}

function formatInr(paise: number): string {
  return `₹${(paise / 100).toLocaleString("en-IN", { minimumFractionDigits: 2, maximumFractionDigits: 2 })}`;
}

export function NegotiationPolicyPanel({
  policy,
  errors,
  isSaving,
  saveResult,
  previewListPricePaise,
  onUpdatePolicy,
  onSavePolicy,
}: NegotiationPolicyPanelProps): React.JSX.Element {
  const floorPaise = previewFloorPricePaise(previewListPricePaise, policy.marginFloorBps);
  const effectiveTurns = Math.min(policy.maxNegotiationTurns, gatewayMaxNegotiationTurns);

  return (
    <div className="rounded-lg border border-borderSubtle bg-bgSurface p-5 space-y-4">
      <div className="flex items-center justify-between border-b border-borderSubtle pb-3">
        <div className="flex items-center gap-2">
          <Handshake className="h-4 w-4 text-accentPrimary" />
          <h2 className="text-sm font-semibold text-textPrimary">Negotiation Policy</h2>
        </div>
        <button
          type="button"
          onClick={onSavePolicy}
          disabled={isSaving}
          className="flex items-center gap-1.5 rounded-md border border-accentPrimary/30 bg-accentSubtle px-3 py-1 text-xs font-medium text-accentPrimary transition hover:bg-accentPrimary hover:text-white disabled:opacity-50"
        >
          {isSaving ? (
            <Loader2 className="h-3.5 w-3.5 animate-spin" />
          ) : (
            <Save className="h-3.5 w-3.5" />
          )}
          <span>{isSaving ? "Saving…" : "Save Policy"}</span>
        </button>
      </div>

      <label className="flex cursor-pointer items-start gap-3 rounded-md border border-borderSubtle bg-surfaceContainer px-3 py-3">
        <input
          type="checkbox"
          checked={policy.negotiationEnabled}
          onChange={(e) => onUpdatePolicy({ negotiationEnabled: e.target.checked })}
          className="mt-0.5 h-4 w-4 accent-accentPrimary"
        />
        <span className="text-xs">
          <span className="block font-semibold text-textPrimary">
            Allow buyer agents to negotiate on my SKUs
          </span>
          <span className="mt-0.5 block text-textMuted">
            {policy.negotiationEnabled
              ? "Agents may open an x402-INR negotiation. They never see your floor — they only learn whether their bid cleared it."
              : "Off. negotiate_price answers DECLINED for your SKUs and agents buy at your listed price."}
          </span>
        </span>
      </label>

      <div className="grid grid-cols-12 gap-3 text-xs">
        <div className="col-span-12">
          <label className="mb-1 block font-mono uppercase tracking-wider text-textSecondary">
            Merchant DID
          </label>
          <input
            type="text"
            value={policy.merchantDid}
            onChange={(e) => onUpdatePolicy({ merchantDid: e.target.value })}
            placeholder="did:mesh:merchant_razoragent_demo_01"
            className="w-full rounded border border-borderSubtle bg-bgSurface px-2 py-1 font-mono text-xs text-textPrimary focus:border-accentPrimary focus:outline-none focus:ring-1 focus:ring-accentPrimary"
          />
          {errors.merchantDid && (
            <p className="mt-0.5 text-xs text-statusError">{errors.merchantDid}</p>
          )}
        </div>

        <div className="col-span-4">
          <label className="mb-1 block font-mono uppercase tracking-wider text-textSecondary">
            Margin Floor (BPS)
          </label>
          <input
            type="number"
            min={minMarginFloorBps}
            max={maxMarginFloorBps}
            value={policy.marginFloorBps}
            onChange={(e) =>
              onUpdatePolicy({ marginFloorBps: Math.max(0, parseInt(e.target.value || "0", 10)) })
            }
            className="w-full rounded border border-borderSubtle bg-bgSurface px-2 py-1 font-mono text-xs text-textPrimary focus:border-accentPrimary focus:outline-none focus:ring-1 focus:ring-accentPrimary"
          />
          {errors.marginFloorBps && (
            <p className="mt-0.5 text-xs text-statusError">{errors.marginFloorBps}</p>
          )}
        </div>

        <div className="col-span-4">
          <label className="mb-1 block font-mono uppercase tracking-wider text-textSecondary">
            Min Order Qty
          </label>
          <input
            type="number"
            min={1}
            value={policy.minimumOrderQuantity}
            onChange={(e) =>
              onUpdatePolicy({
                minimumOrderQuantity: Math.max(1, parseInt(e.target.value || "1", 10)),
              })
            }
            className="w-full rounded border border-borderSubtle bg-bgSurface px-2 py-1 font-mono text-xs text-textPrimary focus:border-accentPrimary focus:outline-none focus:ring-1 focus:ring-accentPrimary"
          />
          {errors.minimumOrderQuantity && (
            <p className="mt-0.5 text-xs text-statusError">{errors.minimumOrderQuantity}</p>
          )}
        </div>

        <div className="col-span-4">
          <label className="mb-1 block font-mono uppercase tracking-wider text-textSecondary">
            Max Turns
          </label>
          <input
            type="number"
            min={minPolicyNegotiationTurns}
            max={maxPolicyNegotiationTurns}
            value={policy.maxNegotiationTurns}
            onChange={(e) =>
              onUpdatePolicy({
                maxNegotiationTurns: Math.max(1, parseInt(e.target.value || "1", 10)),
              })
            }
            className="w-full rounded border border-borderSubtle bg-bgSurface px-2 py-1 font-mono text-xs text-textPrimary focus:border-accentPrimary focus:outline-none focus:ring-1 focus:ring-accentPrimary"
          />
          {errors.maxNegotiationTurns && (
            <p className="mt-0.5 text-xs text-statusError">{errors.maxNegotiationTurns}</p>
          )}
          {policy.maxNegotiationTurns > gatewayMaxNegotiationTurns && (
            <p className="mt-0.5 text-[10px] text-textMuted">
              The gateway caps a negotiation at {gatewayMaxNegotiationTurns}; you will get{" "}
              {effectiveTurns}.
            </p>
          )}
        </div>

        <div className="col-span-6">
          <label className="mb-1 block font-mono uppercase tracking-wider text-textSecondary">
            Auto-Accept Spread (₹)
          </label>
          <input
            type="text"
            inputMode="decimal"
            value={policy.autoAcceptSpreadInr}
            onChange={(e) => onUpdatePolicy({ autoAcceptSpreadInr: e.target.value })}
            placeholder="0.00"
            className="w-full rounded border border-borderSubtle bg-bgSurface px-2 py-1 font-mono text-xs text-textPrimary focus:border-accentPrimary focus:outline-none focus:ring-1 focus:ring-accentPrimary"
          />
          {errors.autoAcceptSpreadInr && (
            <p className="mt-0.5 text-xs text-statusError">{errors.autoAcceptSpreadInr}</p>
          )}
        </div>
      </div>

      {policy.negotiationEnabled && previewListPricePaise > 0 && (
        <p className="rounded border border-borderSubtle bg-surfaceContainer px-3 py-2 font-mono text-[10px] text-statusSuccess">
          At the {formatInr(previewListPricePaise)} list price above, you will never sell below{" "}
          {formatInr(floorPaise)} per unit.
        </p>
      )}

      {saveResult && (
        <p
          className={`text-xs ${saveResult.ok ? "text-statusSuccess" : "text-statusError"}`}
          role="status"
        >
          {saveResult.message}
        </p>
      )}
    </div>
  );
}
