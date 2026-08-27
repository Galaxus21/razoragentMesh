import React from "react";
import { Utensils } from "lucide-react";
import { FmcgFacetFormData, FormValidationErrors } from "@/types/merchantCatalogTypes";

export interface FmcgFacetFieldsProps {
  readonly fmcgFacet: FmcgFacetFormData;
  readonly errors: FormValidationErrors;
  readonly onUpdateFmcg: <K extends keyof FmcgFacetFormData>(
    field: K,
    value: FmcgFacetFormData[K]
  ) => void;
}

export function FmcgFacetFields({
  fmcgFacet,
  errors,
  onUpdateFmcg,
}: FmcgFacetFieldsProps): React.JSX.Element {
  const handleAllergens = (e: React.ChangeEvent<HTMLInputElement>): void => {
    onUpdateFmcg("allergens", e.target.value.split(",").map((s) => s.trim()));
  };

  return (
    <div className="space-y-4 pt-1">
      <div className="flex items-center gap-2 text-xs font-medium text-statusSuccess">
        <Utensils className="h-3.5 w-3.5" />
        <span>Nutritional, Shelf-Life & FSSAI Compliance</span>
      </div>
      <div className="grid grid-cols-1 md:grid-cols-4 gap-4">
        <div>
          <label htmlFor="fmcgAllergens" className="block text-xs font-medium text-textSecondary mb-1">Declared Allergens</label>
          <input id="fmcgAllergens" type="text" value={fmcgFacet.allergens.join(", ")} onChange={handleAllergens} placeholder="e.g. Peanuts, Gluten" className="w-full rounded-md border border-borderSubtle bg-surfaceContainer px-3 py-2 text-xs text-textPrimary focus:border-accentPrimary focus:outline-none focus:ring-1 focus:ring-accentPrimary" />
        </div>
        <div>
          <label htmlFor="shelfLifeDays" className="block text-xs font-medium text-textSecondary mb-1">Shelf Life (Days) <span className="text-statusError">*</span></label>
          <input id="shelfLifeDays" type="number" min={1} value={fmcgFacet.shelfLifeDays} onChange={(e) => onUpdateFmcg("shelfLifeDays", parseInt(e.target.value || "1", 10))} className={`w-full rounded-md border px-3 py-2 text-xs font-mono text-textPrimary bg-surfaceContainer focus:outline-none focus:ring-1 focus:ring-accentPrimary ${errors.fmcgShelfLife ? "border-statusError" : "border-borderSubtle focus:border-accentPrimary"}`} />
          {errors.fmcgShelfLife && <p className="mt-1 text-xs text-statusError">{errors.fmcgShelfLife}</p>}
        </div>
        <div>
          <label htmlFor="fssaiNumber" className="block text-xs font-medium text-textSecondary mb-1">FSSAI 14-digit License</label>
          <input id="fssaiNumber" type="text" maxLength={14} value={fmcgFacet.fssaiNumber} onChange={(e) => onUpdateFmcg("fssaiNumber", e.target.value)} placeholder="10012011000123" className={`w-full rounded-md border px-3 py-2 text-xs font-mono text-textPrimary bg-surfaceContainer focus:outline-none focus:ring-1 focus:ring-accentPrimary ${errors.fmcgFssai ? "border-statusError" : "border-borderSubtle focus:border-accentPrimary"}`} />
          {errors.fmcgFssai && <p className="mt-1 text-xs text-statusError">{errors.fmcgFssai}</p>}
        </div>
        <div className="flex items-center pt-5">
          <label className="flex items-center gap-2 cursor-pointer">
            <input type="checkbox" checked={fmcgFacet.isVeg} onChange={(e) => onUpdateFmcg("isVeg", e.target.checked)} className="h-4 w-4 rounded border-borderSubtle bg-surfaceContainer text-accentPrimary focus:ring-accentPrimary" />
            <span className="text-xs text-textSecondary">100% Vegetarian (Green Dot)</span>
          </label>
        </div>
      </div>
    </div>
  );
}
