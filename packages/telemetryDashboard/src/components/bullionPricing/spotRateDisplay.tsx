import React from "react";
import { TrendingUp } from "lucide-react";
import {
  metalPurityChoices,
  oracleFeedOptions,
} from "@/constants/merchantCatalogConstants";
import {
  BullionPricingFormData,
  FormValidationErrors,
  OracleFeedSymbol,
} from "@/types/merchantCatalogTypes";

export interface SpotRateDisplayProps {
  readonly bullionPricing: BullionPricingFormData;
  readonly errors: FormValidationErrors;
  readonly onUpdateBullion: <K extends keyof BullionPricingFormData>(
    field: K,
    value: BullionPricingFormData[K]
  ) => void;
}

export function SpotRateDisplay({ bullionPricing, errors, onUpdateBullion }: SpotRateDisplayProps): React.JSX.Element {
  const handleOracleChange = (symbol: OracleFeedSymbol): void => {
    const selected = oracleFeedOptions.find((o) => o.symbol === symbol);
    onUpdateBullion("oracleFeedSymbol", symbol);
    if (selected) onUpdateBullion("purityMultiplier", selected.defaultPurity);
  };

  return (
    <div className="space-y-4">
      <div className="rounded-lg bg-statusWarning/10 border border-statusWarning/30 p-3 text-xs text-statusWarning flex items-start gap-2">
        <TrendingUp className="h-4 w-4 mt-0.5 shrink-0 text-statusWarning" />
        <div>
          <p className="font-semibold">Live MCX Commodity Feed Integration Active</p>
          <p className="text-xs text-statusWarning/90">Formula: Base Unit Price = (Net Weight × Spot Price Per Gram × Purity Multiplier) + Making Charges + Stone Charges.</p>
        </div>
      </div>
      <div className="grid grid-cols-1 md:grid-cols-3 gap-4">
        <div>
          <label htmlFor="oracleFeedSymbol" className="block text-xs font-medium text-textSecondary mb-1">MCX Commodity Oracle Feed</label>
          <select id="oracleFeedSymbol" value={bullionPricing.oracleFeedSymbol} onChange={(e) => handleOracleChange(e.target.value as OracleFeedSymbol)} className="w-full rounded-md border border-borderSubtle bg-surfaceContainer px-3 py-2 text-xs text-textPrimary focus:border-accentPrimary focus:outline-none focus:ring-1 focus:ring-accentPrimary">
            {oracleFeedOptions.map((feed) => (<option key={feed.symbol} value={feed.symbol}>{feed.label}</option>))}
          </select>
        </div>
        <div>
          <label htmlFor="purityMultiplier" className="block text-xs font-medium text-textSecondary mb-1">Purity Multiplier</label>
          <select id="purityMultiplier" value={bullionPricing.purityMultiplier} onChange={(e) => onUpdateBullion("purityMultiplier", parseFloat(e.target.value))} className="w-full rounded-md border border-borderSubtle bg-surfaceContainer px-3 py-2 text-xs text-textPrimary focus:border-accentPrimary focus:outline-none focus:ring-1 focus:ring-accentPrimary">
            {metalPurityChoices.map((choice) => (<option key={choice.carat} value={choice.multiplier}>{choice.label} ({choice.multiplier})</option>))}
            <option value={0.999}>Silver 999 Fine (0.999)</option>
          </select>
        </div>
        <div>
          <label htmlFor="netWeightGrams" className="block text-xs font-medium text-textSecondary mb-1">Net Weight (Grams) <span className="text-statusError">*</span></label>
          <input id="netWeightGrams" type="number" step="0.01" min="0.01" value={bullionPricing.netWeightGrams} onChange={(e) => onUpdateBullion("netWeightGrams", parseFloat(e.target.value || "0"))} placeholder="e.g. 5.50" className={`w-full rounded-md border px-3 py-2 text-xs font-mono text-textPrimary bg-surfaceContainer focus:outline-none focus:ring-1 focus:ring-accentPrimary ${errors.bullionNetWeight ? "border-statusError" : "border-borderSubtle focus:border-accentPrimary"}`} />
          {errors.bullionNetWeight && <p className="mt-1 text-xs text-statusError">{errors.bullionNetWeight}</p>}
        </div>
      </div>
    </div>
  );
}
