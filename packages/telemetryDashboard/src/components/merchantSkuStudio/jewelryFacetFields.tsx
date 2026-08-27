import React from "react";
import { Award } from "lucide-react";
import { metalPurityChoices } from "@/constants/merchantCatalogConstants";
import {
  FormValidationErrors,
  JewelryFacetFormData,
  JewelryPurityCarat,
} from "@/types/merchantCatalogTypes";

export interface JewelryFacetFieldsProps {
  readonly jewelryFacet: JewelryFacetFormData;
  readonly errors: FormValidationErrors;
  readonly onUpdateJewelry: <K extends keyof JewelryFacetFormData>(
    field: K,
    value: JewelryFacetFormData[K]
  ) => void;
}

export function JewelryFacetFields({
  jewelryFacet,
  errors,
  onUpdateJewelry,
}: JewelryFacetFieldsProps): React.JSX.Element {
  return (
    <div className="space-y-4 pt-1">
      <div className="flex items-center gap-2 text-xs font-medium text-statusWarning">
        <Award className="h-3.5 w-3.5" />
        <span>Precious Jewelry & Hallmarking Credentials</span>
      </div>
      <div className="grid grid-cols-1 md:grid-cols-3 gap-4">
        <div>
          <label htmlFor="purityCarat" className="block text-xs font-medium text-textSecondary mb-1">Gold Carat Purity</label>
          <select id="purityCarat" value={jewelryFacet.purityCarat} onChange={(e) => onUpdateJewelry("purityCarat", parseInt(e.target.value, 10) as JewelryPurityCarat)} className="w-full rounded-md border border-borderSubtle bg-surfaceContainer px-3 py-2 text-xs text-textPrimary focus:border-accentPrimary focus:outline-none focus:ring-1 focus:ring-accentPrimary">
            {metalPurityChoices.map((c) => (<option key={c.carat} value={c.carat}>{c.label}</option>))}
          </select>
        </div>
        <div>
          <label htmlFor="grossWeightGrams" className="block text-xs font-medium text-textSecondary mb-1">Gross Weight (Grams) <span className="text-statusError">*</span></label>
          <input id="grossWeightGrams" type="number" step="0.01" min="0.01" value={jewelryFacet.grossWeightGrams} onChange={(e) => onUpdateJewelry("grossWeightGrams", parseFloat(e.target.value || "0"))} placeholder="5.80" className={`w-full rounded-md border px-3 py-2 text-xs font-mono text-textPrimary bg-surfaceContainer focus:outline-none focus:ring-1 focus:ring-accentPrimary ${errors.jewelryGrossWeight ? "border-statusError" : "border-borderSubtle focus:border-accentPrimary"}`} />
          {errors.jewelryGrossWeight && <p className="mt-1 text-xs text-statusError">{errors.jewelryGrossWeight}</p>}
        </div>
        <div>
          <label htmlFor="hallmarkNumber" className="block text-xs font-medium text-textSecondary mb-1">BIS Hallmark UID / Certificate <span className="text-statusError">*</span></label>
          <input id="hallmarkNumber" type="text" value={jewelryFacet.hallmarkNumber} onChange={(e) => onUpdateJewelry("hallmarkNumber", e.target.value)} placeholder="BIS-HM-KA-2026-001" className={`w-full rounded-md border px-3 py-2 text-xs font-mono text-textPrimary bg-surfaceContainer focus:outline-none focus:ring-1 focus:ring-accentPrimary ${errors.jewelryHallmark ? "border-statusError" : "border-borderSubtle focus:border-accentPrimary"}`} />
          {errors.jewelryHallmark && <p className="mt-1 text-xs text-statusError">{errors.jewelryHallmark}</p>}
        </div>
      </div>
    </div>
  );
}
