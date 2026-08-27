import React from "react";
import { Hash } from "lucide-react";
import {
  gstRateOptions,
  HsnPresetOption,
  hsnPresetOptions,
} from "@/constants/merchantCatalogConstants";
import { FormValidationErrors, MerchantCatalogFormData } from "@/types/merchantCatalogTypes";

export interface TaxConfigFieldGroupProps {
  readonly hsnCode: string;
  readonly gstRatePercent: number;
  readonly errors: FormValidationErrors;
  readonly onChangeField: <K extends keyof MerchantCatalogFormData>(
    field: K,
    value: MerchantCatalogFormData[K]
  ) => void;
  readonly onHsnPresetSelect: (preset: HsnPresetOption) => void;
}

export function TaxConfigFieldGroup({
  hsnCode,
  gstRatePercent,
  errors,
  onChangeField,
  onHsnPresetSelect,
}: TaxConfigFieldGroupProps): React.JSX.Element {
  const handlePresetChange = (e: React.ChangeEvent<HTMLSelectElement>): void => {
    const selected = hsnPresetOptions.find((p) => p.hsn === e.target.value);
    if (selected) onHsnPresetSelect(selected);
  };

  return (
    <div className="grid grid-cols-1 md:grid-cols-3 gap-4">
      <div>
        <label htmlFor="hsnCode" className="block text-xs font-medium text-textSecondary mb-1">HSN Code (4-8 digits) <span className="text-statusError">*</span></label>
        <div className="relative">
          <input id="hsnCode" type="text" value={hsnCode} onChange={(e) => onChangeField("hsnCode", e.target.value)} placeholder="e.g. 71131910" maxLength={8} className={`w-full rounded-md border px-3 py-2 font-mono text-xs text-textPrimary bg-surfaceContainer focus:outline-none focus:ring-1 focus:ring-accentPrimary ${errors.hsnCode ? "border-statusError" : "border-borderSubtle focus:border-accentPrimary"}`} />
          <Hash className="absolute right-2.5 top-2.5 h-3.5 w-3.5 text-textMuted" />
        </div>
        {errors.hsnCode && <p className="mt-1 text-xs text-statusError">{errors.hsnCode}</p>}
      </div>
      <div>
        <label htmlFor="hsnPreset" className="block text-xs font-medium text-textSecondary mb-1">Statutory HSN Presets</label>
        <select id="hsnPreset" defaultValue="" onChange={handlePresetChange} className="w-full rounded-md border border-borderSubtle bg-surfaceContainer px-3 py-2 text-xs text-textPrimary focus:border-accentPrimary focus:outline-none focus:ring-1 focus:ring-accentPrimary">
          <option value="" disabled>Select HSN Preset Template...</option>
          {hsnPresetOptions.map((preset) => (
            <option key={preset.hsn} value={preset.hsn}>{preset.hsn} — {preset.description} ({preset.gstRate}% GST)</option>
          ))}
        </select>
      </div>
      <div>
        <label htmlFor="gstRatePercent" className="block text-xs font-medium text-textSecondary mb-1">GST Tax Rate (%)</label>
        <select id="gstRatePercent" value={gstRatePercent} onChange={(e) => onChangeField("gstRatePercent", Number(e.target.value))} className="w-full rounded-md border border-borderSubtle bg-surfaceContainer px-3 py-2 text-xs text-textPrimary focus:border-accentPrimary focus:outline-none focus:ring-1 focus:ring-accentPrimary">
          {gstRateOptions.map((rate) => (<option key={rate} value={rate}>{rate}% GST</option>))}
        </select>
      </div>
    </div>
  );
}
