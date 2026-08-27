"use client";

import React from "react";
import { Coins } from "lucide-react";
import { BullionPricingFormData, FormValidationErrors } from "@/types/merchantCatalogTypes";
import { FormulaConfigPanel } from "../bullionPricing/formulaConfigPanel";
import { SpotRateDisplay } from "../bullionPricing/spotRateDisplay";

export interface BullionPricingSectionProps {
  readonly bullionPricing: BullionPricingFormData;
  readonly errors: FormValidationErrors;
  readonly onUpdateBullion: <K extends keyof BullionPricingFormData>(
    field: K,
    value: BullionPricingFormData[K]
  ) => void;
}

export function BullionPricingSection({
  bullionPricing,
  errors,
  onUpdateBullion,
}: BullionPricingSectionProps): React.JSX.Element {
  return (
    <div className="rounded-lg border border-borderSubtle bg-bgSurface p-5 space-y-4">
      <div className="flex items-center justify-between border-b border-borderSubtle pb-3">
        <div className="flex items-center gap-2">
          <Coins className="h-4 w-4 text-statusWarning" />
          <h2 className="text-sm font-semibold text-textPrimary">Spot-Linked Bullion Pricing Formula</h2>
        </div>
        <label className="flex items-center gap-2 cursor-pointer">
          <span className="text-xs text-textSecondary">Enable Bullion Dynamic Pricing</span>
          <input
            type="checkbox"
            checked={bullionPricing.enabled}
            onChange={(e) => onUpdateBullion("enabled", e.target.checked)}
            className="h-4 w-4 rounded border-borderSubtle bg-surfaceContainer text-accentPrimary focus:ring-accentPrimary"
          />
        </label>
      </div>

      {bullionPricing.enabled ? (
        <div className="space-y-4 pt-1">
          <SpotRateDisplay bullionPricing={bullionPricing} errors={errors} onUpdateBullion={onUpdateBullion} />
          <FormulaConfigPanel bullionPricing={bullionPricing} onUpdateBullion={onUpdateBullion} />
        </div>
      ) : (
        <div className="rounded-lg border border-dashed border-borderSubtle p-4 text-xs text-textMuted">
          Spot-linked pricing disabled. Product will be priced statically using the fixed Base Unit Price above.
        </div>
      )}
    </div>
  );
}
