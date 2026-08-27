"use client";

import React from "react";
import { ArrowDownRight, Plus, Tag, Trash2 } from "lucide-react";
import { maxDiscountBps, minVolumeQuantity } from "@/constants/merchantCatalogConstants";
import { FormValidationErrors, VolumeTierInput } from "@/types/merchantCatalogTypes";

export interface VolumeTierBuilderProps {
  readonly volumeTiers: ReadonlyArray<VolumeTierInput>;
  readonly errors: FormValidationErrors;
  readonly onAddTier: () => void;
  readonly onRemoveTier: (index: number) => void;
  readonly onUpdateTier: (index: number, updated: VolumeTierInput) => void;
}

export function VolumeTierBuilder({
  volumeTiers,
  errors,
  onAddTier,
  onRemoveTier,
  onUpdateTier,
}: VolumeTierBuilderProps): React.JSX.Element {
  return (
    <div className="rounded-lg border border-borderSubtle bg-bgSurface p-5 space-y-4">
      <div className="flex items-center justify-between border-b border-borderSubtle pb-3">
        <div className="flex items-center gap-2">
          <Tag className="h-4 w-4 text-accentPrimary" />
          <h2 className="text-sm font-semibold text-textPrimary">Dynamic Volume Tier Discounts</h2>
        </div>
        <button
          type="button"
          onClick={onAddTier}
          className="flex items-center gap-1.5 rounded-md border border-accentPrimary/30 bg-accentSubtle px-3 py-1 text-xs font-medium text-accentPrimary transition hover:bg-accentPrimary hover:text-white"
        >
          <Plus className="h-3.5 w-3.5" />
          <span>Add Volume Tier</span>
        </button>
      </div>

      {volumeTiers.length === 0 ? (
        <div className="rounded-lg border border-dashed border-borderSubtle p-6 text-center text-xs text-textMuted">
          <p>No volume tiers configured. Standard base unit price applies to all purchase quantities.</p>
          <button
            type="button"
            onClick={onAddTier}
            className="mt-2 text-xs text-accentPrimary hover:underline"
          >
            Click here to add the first volume tier (e.g. 5% off for 10+ units)
          </button>
        </div>
      ) : (
        <div className="space-y-2">
          <div className="grid grid-cols-12 gap-3 px-3 py-1 font-mono text-xs uppercase tracking-wider text-textSecondary">
            <span className="col-span-1">Tier</span>
            <span className="col-span-4">Min Quantity (Units)</span>
            <span className="col-span-4">Discount (Basis Points)</span>
            <span className="col-span-2 text-right">Effective %</span>
            <span className="col-span-1 text-right">Action</span>
          </div>

          {volumeTiers.map((tier, index) => {
            const effectivePercent = (tier.discountBps / 100).toFixed(2);
            const qtyError = errors[`volumeTier_${index}_qty`];
            const bpsError = errors[`volumeTier_${index}_bps`];

            return (
              <div
                key={index}
                className="grid grid-cols-12 items-center gap-3 rounded-md border border-borderSubtle bg-surfaceContainer px-3 py-2 text-xs"
              >
                <div className="col-span-1 font-mono text-textSecondary">#{index + 1}</div>

                <div className="col-span-4">
                  <input
                    type="number"
                    min={minVolumeQuantity}
                    value={tier.minQuantity}
                    onChange={(e) =>
                      onUpdateTier(index, {
                        ...tier,
                        minQuantity: Math.max(1, parseInt(e.target.value || "1", 10)),
                      })
                    }
                    className="w-full rounded border border-borderSubtle bg-bgSurface px-2 py-1 font-mono text-xs text-textPrimary focus:border-accentPrimary focus:outline-none focus:ring-1 focus:ring-accentPrimary"
                  />
                  {qtyError && <p className="mt-0.5 text-xs text-statusError">{qtyError}</p>}
                </div>

                <div className="col-span-4">
                  <div className="relative">
                    <input
                      type="number"
                      min={0}
                      max={maxDiscountBps}
                      value={tier.discountBps}
                      onChange={(e) =>
                        onUpdateTier(index, {
                          ...tier,
                          discountBps: Math.min(
                            maxDiscountBps,
                            Math.max(0, parseInt(e.target.value || "0", 10))
                          ),
                        })
                      }
                      className="w-full rounded border border-borderSubtle bg-bgSurface px-2 py-1 font-mono text-xs text-textPrimary focus:border-accentPrimary focus:outline-none focus:ring-1 focus:ring-accentPrimary"
                    />
                    <span className="absolute right-2 top-1 text-[10px] text-textMuted">BPS</span>
                  </div>
                  {bpsError && <p className="mt-0.5 text-xs text-statusError">{bpsError}</p>}
                </div>

                <div className="col-span-2 flex items-center justify-end gap-1 font-mono text-statusSuccess font-medium">
                  <ArrowDownRight className="h-3 w-3" />
                  <span>{effectivePercent}%</span>
                </div>

                <div className="col-span-1 flex justify-end">
                  <button
                    type="button"
                    onClick={() => onRemoveTier(index)}
                    title="Remove Tier"
                    className="rounded p-1 text-textMuted hover:bg-statusError/10 hover:text-statusError transition"
                  >
                    <Trash2 className="h-3.5 w-3.5" />
                  </button>
                </div>
              </div>
            );
          })}
        </div>
      )}
    </div>
  );
}
