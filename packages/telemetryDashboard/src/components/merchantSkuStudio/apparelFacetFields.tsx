import React from "react";
import { Feather } from "lucide-react";
import { apparelGenderOptions } from "@/constants/merchantCatalogConstants";
import { ApparelFacetFormData, ApparelGender } from "@/types/merchantCatalogTypes";

export interface ApparelFacetFieldsProps {
  readonly apparelFacet: ApparelFacetFormData;
  readonly onUpdateApparel: <K extends keyof ApparelFacetFormData>(
    field: K,
    value: ApparelFacetFormData[K]
  ) => void;
}

export function ApparelFacetFields({ apparelFacet, onUpdateApparel }: ApparelFacetFieldsProps): React.JSX.Element {
  return (
    <div className="space-y-4 pt-1">
      <div className="flex items-center gap-2 text-xs font-medium text-accentPrimary">
        <Feather className="h-3.5 w-3.5" />
        <span>Fashion, Sizing & Textile Specifications</span>
      </div>
      <div className="grid grid-cols-1 md:grid-cols-5 gap-4">
        <div>
          <label htmlFor="apparelSize" className="block text-xs font-medium text-textSecondary mb-1">Size</label>
          <input id="apparelSize" type="text" value={apparelFacet.size} onChange={(e) => onUpdateApparel("size", e.target.value)} placeholder="e.g. L, XL, 32" className="w-full rounded-md border border-borderSubtle bg-surfaceContainer px-3 py-2 text-xs text-textPrimary focus:border-accentPrimary focus:outline-none focus:ring-1 focus:ring-accentPrimary" />
        </div>
        <div>
          <label htmlFor="apparelColor" className="block text-xs font-medium text-textSecondary mb-1">Color</label>
          <input id="apparelColor" type="text" value={apparelFacet.color} onChange={(e) => onUpdateApparel("color", e.target.value)} placeholder="e.g. Navy Blue" className="w-full rounded-md border border-borderSubtle bg-surfaceContainer px-3 py-2 text-xs text-textPrimary focus:border-accentPrimary focus:outline-none focus:ring-1 focus:ring-accentPrimary" />
        </div>
        <div>
          <label htmlFor="apparelFabric" className="block text-xs font-medium text-textSecondary mb-1">Fabric</label>
          <input id="apparelFabric" type="text" value={apparelFacet.fabric.join(", ")} onChange={(e) => onUpdateApparel("fabric", e.target.value.split(",").map((s) => s.trim()))} placeholder="e.g. Cotton, Linen" className="w-full rounded-md border border-borderSubtle bg-surfaceContainer px-3 py-2 text-xs text-textPrimary focus:border-accentPrimary focus:outline-none focus:ring-1 focus:ring-accentPrimary" />
        </div>
        <div>
          <label htmlFor="apparelFit" className="block text-xs font-medium text-textSecondary mb-1">Fit Type</label>
          <input id="apparelFit" type="text" value={apparelFacet.fitType} onChange={(e) => onUpdateApparel("fitType", e.target.value)} placeholder="Regular, Slim" className="w-full rounded-md border border-borderSubtle bg-surfaceContainer px-3 py-2 text-xs text-textPrimary focus:border-accentPrimary focus:outline-none focus:ring-1 focus:ring-accentPrimary" />
        </div>
        <div>
          <label htmlFor="apparelGender" className="block text-xs font-medium text-textSecondary mb-1">Gender</label>
          <select id="apparelGender" value={apparelFacet.gender} onChange={(e) => onUpdateApparel("gender", e.target.value as ApparelGender)} className="w-full rounded-md border border-borderSubtle bg-surfaceContainer px-3 py-2 text-xs text-textPrimary focus:border-accentPrimary focus:outline-none focus:ring-1 focus:ring-accentPrimary">
            {apparelGenderOptions.map((opt) => (<option key={opt.value} value={opt.value}>{opt.label}</option>))}
          </select>
        </div>
      </div>
    </div>
  );
}
