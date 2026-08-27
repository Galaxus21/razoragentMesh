import React from "react";
import { FormValidationErrors, MerchantCatalogFormData } from "@/types/merchantCatalogTypes";

export interface InventoryFieldGroupProps {
  readonly availableStock: number;
  readonly originPincode: string;
  readonly minimumOrderQuantity: number;
  readonly errors: FormValidationErrors;
  readonly onChangeField: <K extends keyof MerchantCatalogFormData>(
    field: K,
    value: MerchantCatalogFormData[K]
  ) => void;
}

export function InventoryFieldGroup({
  availableStock,
  originPincode,
  minimumOrderQuantity,
  errors,
  onChangeField,
}: InventoryFieldGroupProps): React.JSX.Element {
  return (
    <div className="grid grid-cols-1 md:grid-cols-3 gap-4">
      <div>
        <label htmlFor="availableStock" className="block text-xs font-medium text-textSecondary mb-1">Stock Inventory <span className="text-statusError">*</span></label>
        <input id="availableStock" type="number" min={0} value={availableStock} onChange={(e) => onChangeField("availableStock", Math.max(0, parseInt(e.target.value || "0", 10)))} className={`w-full rounded-md border px-3 py-2 text-xs font-mono text-textPrimary bg-surfaceContainer focus:outline-none focus:ring-1 focus:ring-accentPrimary ${errors.availableStock ? "border-statusError" : "border-borderSubtle focus:border-accentPrimary"}`} />
        {errors.availableStock && <p className="mt-1 text-xs text-statusError">{errors.availableStock}</p>}
      </div>
      <div>
        <label htmlFor="originPincode" className="block text-xs font-medium text-textSecondary mb-1">Origin Pincode <span className="text-statusError">*</span></label>
        <input id="originPincode" type="text" maxLength={6} value={originPincode} onChange={(e) => onChangeField("originPincode", e.target.value)} placeholder="560001" className={`w-full rounded-md border px-3 py-2 text-xs font-mono text-textPrimary bg-surfaceContainer focus:outline-none focus:ring-1 focus:ring-accentPrimary ${errors.originPincode ? "border-statusError" : "border-borderSubtle focus:border-accentPrimary"}`} />
        {errors.originPincode && <p className="mt-1 text-xs text-statusError">{errors.originPincode}</p>}
      </div>
      <div>
        <label htmlFor="minimumOrderQuantity" className="block text-xs font-medium text-textSecondary mb-1">Minimum Order Qty</label>
        <input id="minimumOrderQuantity" type="number" min={1} value={minimumOrderQuantity} onChange={(e) => onChangeField("minimumOrderQuantity", Math.max(1, parseInt(e.target.value || "1", 10)))} className="w-full rounded-md border border-borderSubtle bg-surfaceContainer px-3 py-2 font-mono text-xs text-textPrimary focus:border-accentPrimary focus:outline-none focus:ring-1 focus:ring-accentPrimary" />
      </div>
    </div>
  );
}
