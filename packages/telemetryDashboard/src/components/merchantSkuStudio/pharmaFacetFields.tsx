import React from "react";
import { Pill } from "lucide-react";
import { FormValidationErrors, PharmaFacetFormData } from "@/types/merchantCatalogTypes";

export interface PharmaFacetFieldsProps {
  readonly pharmaFacet: PharmaFacetFormData;
  readonly errors: FormValidationErrors;
  readonly onUpdatePharma: <K extends keyof PharmaFacetFormData>(
    field: K,
    value: PharmaFacetFormData[K]
  ) => void;
}

export function PharmaFacetFields({
  pharmaFacet,
  errors,
  onUpdatePharma,
}: PharmaFacetFieldsProps): React.JSX.Element {
  return (
    <div className="space-y-4 pt-1">
      <div className="flex items-center gap-2 text-xs font-medium text-statusError">
        <Pill className="h-3.5 w-3.5" />
        <span>Active Molecule & Regulatory Schedule</span>
      </div>
      <div className="grid grid-cols-1 md:grid-cols-4 gap-4">
        <div>
          <label htmlFor="activeSalt" className="block text-xs font-medium text-textSecondary mb-1">Active Salt <span className="text-statusError">*</span></label>
          <input id="activeSalt" type="text" value={pharmaFacet.activeSalt} onChange={(e) => onUpdatePharma("activeSalt", e.target.value)} placeholder="Paracetamol IP" className={`w-full rounded-md border px-3 py-2 text-xs text-textPrimary bg-surfaceContainer focus:outline-none focus:ring-1 focus:ring-accentPrimary ${errors.pharmaSalt ? "border-statusError" : "border-borderSubtle focus:border-accentPrimary"}`} />
          {errors.pharmaSalt && <p className="mt-1 text-xs text-statusError">{errors.pharmaSalt}</p>}
        </div>
        <div>
          <label htmlFor="dosageMg" className="block text-xs font-medium text-textSecondary mb-1">Dosage (mg)</label>
          <input id="dosageMg" type="number" min={0} value={pharmaFacet.dosageMg} onChange={(e) => onUpdatePharma("dosageMg", parseInt(e.target.value || "0", 10))} className="w-full rounded-md border border-borderSubtle bg-surfaceContainer px-3 py-2 font-mono text-xs text-textPrimary focus:border-accentPrimary focus:outline-none focus:ring-1 focus:ring-accentPrimary" />
        </div>
        <div>
          <label htmlFor="pharmaSchedule" className="block text-xs font-medium text-textSecondary mb-1">Schedule</label>
          <select id="pharmaSchedule" value={pharmaFacet.schedule} onChange={(e) => onUpdatePharma("schedule", e.target.value)} className="w-full rounded-md border border-borderSubtle bg-surfaceContainer px-3 py-2 text-xs text-textPrimary focus:border-accentPrimary focus:outline-none focus:ring-1 focus:ring-accentPrimary">
            <option value="OTC">OTC (Over the Counter)</option>
            <option value="Schedule H">Schedule H (Prescription)</option>
            <option value="Schedule X">Schedule X (Strict Narcotic)</option>
          </select>
        </div>
        <div className="flex items-center pt-5">
          <label className="flex items-center gap-2 cursor-pointer">
            <input type="checkbox" checked={pharmaFacet.prescriptionRequired} onChange={(e) => onUpdatePharma("prescriptionRequired", e.target.checked)} className="h-4 w-4 rounded border-borderSubtle bg-surfaceContainer text-accentPrimary focus:ring-accentPrimary" />
            <span className="text-xs text-textSecondary">Requires Doctor Prescription (Rx)</span>
          </label>
        </div>
      </div>
    </div>
  );
}
