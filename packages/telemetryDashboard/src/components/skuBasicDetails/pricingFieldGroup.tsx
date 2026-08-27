import React from "react";
import { convertInrToPaise, formatPaiseToInr } from "@/lib/merchantCatalogValidator";
import { FormValidationErrors, MerchantCatalogFormData } from "@/types/merchantCatalogTypes";

export interface PricingFieldGroupProps {
  readonly basePriceInr: number | string;
  readonly errors: FormValidationErrors;
  readonly onChangeField: <K extends keyof MerchantCatalogFormData>(
    field: K,
    value: MerchantCatalogFormData[K]
  ) => void;
}

export function PricingFieldGroup({
  basePriceInr,
  errors,
  onChangeField,
}: PricingFieldGroupProps): React.JSX.Element {
  const convertedPaise = convertInrToPaise(basePriceInr);

  return (
    <div>
      <div className="flex items-center justify-between mb-1">
        <label htmlFor="basePriceInr" className="block text-xs font-medium text-textSecondary">
          Base Price (INR) <span className="text-statusError">*</span>
        </label>
        <span className="font-mono text-xs text-statusInfo">
          {convertedPaise.toLocaleString("en-IN")} paise
        </span>
      </div>
      <div className="relative">
        <input
          id="basePriceInr"
          type="text"
          value={basePriceInr}
          onChange={(e) => onChangeField("basePriceInr", e.target.value)}
          placeholder="e.g. 4200.00"
          className={`w-full rounded-md border px-3 py-2 pl-7 font-mono text-xs text-textPrimary bg-surfaceContainer placeholder:text-textMuted focus:outline-none focus:ring-1 focus:ring-accentPrimary ${errors.basePriceInr ? "border-statusError" : "border-borderSubtle focus:border-accentPrimary"}`}
        />
        <span className="absolute left-2.5 top-2 text-xs text-textMuted">₹</span>
      </div>
      <p className="mt-1 text-xs text-textMuted">Formatted: {formatPaiseToInr(convertedPaise)}</p>
      {errors.basePriceInr && <p className="mt-0.5 text-xs text-statusError">{errors.basePriceInr}</p>}
    </div>
  );
}
