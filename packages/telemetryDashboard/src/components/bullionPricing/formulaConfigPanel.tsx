import React from "react";
import { makingChargesTypeOptions } from "@/constants/merchantCatalogConstants";
import { BullionPricingFormData, MakingChargesType } from "@/types/merchantCatalogTypes";

export interface FormulaConfigPanelProps {
  readonly bullionPricing: BullionPricingFormData;
  readonly onUpdateBullion: <K extends keyof BullionPricingFormData>(
    field: K,
    value: BullionPricingFormData[K]
  ) => void;
}

export function FormulaConfigPanel({
  bullionPricing,
  onUpdateBullion,
}: FormulaConfigPanelProps): React.JSX.Element {
  return (
    <div className="grid grid-cols-1 md:grid-cols-4 gap-4">
      <div>
        <label htmlFor="makingChargesType" className="block text-xs font-medium text-textSecondary mb-1">Making Charges Structure</label>
        <select id="makingChargesType" value={bullionPricing.makingChargesType} onChange={(e) => onUpdateBullion("makingChargesType", e.target.value as MakingChargesType)} className="w-full rounded-md border border-borderSubtle bg-surfaceContainer px-3 py-2 text-xs text-textPrimary focus:border-accentPrimary focus:outline-none focus:ring-1 focus:ring-accentPrimary">
          {makingChargesTypeOptions.map((opt) => (<option key={opt.value} value={opt.value}>{opt.label}</option>))}
        </select>
      </div>
      <div>
        <label htmlFor="makingChargesInr" className="block text-xs font-medium text-textSecondary mb-1">Making Charges (INR)</label>
        <input id="makingChargesInr" type="text" value={bullionPricing.makingChargesInr} onChange={(e) => onUpdateBullion("makingChargesInr", e.target.value)} placeholder="e.g. 3500.00" className="w-full rounded-md border border-borderSubtle bg-surfaceContainer px-3 py-2 font-mono text-xs text-textPrimary focus:border-accentPrimary focus:outline-none focus:ring-1 focus:ring-accentPrimary" />
      </div>
      <div>
        <label htmlFor="stoneChargesInr" className="block text-xs font-medium text-textSecondary mb-1">Studded Stone Value (INR)</label>
        <input id="stoneChargesInr" type="text" value={bullionPricing.stoneChargesInr} onChange={(e) => onUpdateBullion("stoneChargesInr", e.target.value)} placeholder="0.00" className="w-full rounded-md border border-borderSubtle bg-surfaceContainer px-3 py-2 font-mono text-xs text-textPrimary focus:border-accentPrimary focus:outline-none focus:ring-1 focus:ring-accentPrimary" />
      </div>
      <div>
        <label htmlFor="maxQuoteTtlSeconds" className="block text-xs font-medium text-textSecondary mb-1">Quote TTL (Seconds)</label>
        <input id="maxQuoteTtlSeconds" type="number" min={10} max={300} value={bullionPricing.maxQuoteTtlSeconds} onChange={(e) => onUpdateBullion("maxQuoteTtlSeconds", parseInt(e.target.value || "60", 10))} className="w-full rounded-md border border-borderSubtle bg-surfaceContainer px-3 py-2 font-mono text-xs text-textPrimary focus:border-accentPrimary focus:outline-none focus:ring-1 focus:ring-accentPrimary" />
      </div>
    </div>
  );
}
