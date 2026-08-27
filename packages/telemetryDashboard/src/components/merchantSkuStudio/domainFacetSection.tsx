"use client";

import React from "react";
import { Sparkles } from "lucide-react";
import { facetTabOptions } from "@/constants/merchantCatalogConstants";
import {
  ApparelFacetFormData,
  DomainFacetType,
  FmcgFacetFormData,
  FormValidationErrors,
  JewelryFacetFormData,
  PharmaFacetFormData,
} from "@/types/merchantCatalogTypes";
import { ApparelFacetFields } from "./apparelFacetFields";
import { FmcgFacetFields } from "./fmcgFacetFields";
import { JewelryFacetFields } from "./jewelryFacetFields";
import { PharmaFacetFields } from "./pharmaFacetFields";

export interface DomainFacetSectionProps {
  readonly selectedFacet: DomainFacetType;
  readonly jewelryFacet: JewelryFacetFormData;
  readonly apparelFacet: ApparelFacetFormData;
  readonly pharmaFacet: PharmaFacetFormData;
  readonly fmcgFacet: FmcgFacetFormData;
  readonly errors: FormValidationErrors;
  readonly onSelectFacet: (facet: DomainFacetType) => void;
  readonly onUpdateJewelry: <K extends keyof JewelryFacetFormData>(
    field: K,
    value: JewelryFacetFormData[K]
  ) => void;
  readonly onUpdateApparel: <K extends keyof ApparelFacetFormData>(
    field: K,
    value: ApparelFacetFormData[K]
  ) => void;
  readonly onUpdatePharma: <K extends keyof PharmaFacetFormData>(
    field: K,
    value: PharmaFacetFormData[K]
  ) => void;
  readonly onUpdateFmcg: <K extends keyof FmcgFacetFormData>(
    field: K,
    value: FmcgFacetFormData[K]
  ) => void;
}

export function DomainFacetSection(props: DomainFacetSectionProps): React.JSX.Element {
  const { selectedFacet, jewelryFacet, apparelFacet, pharmaFacet, fmcgFacet, errors, onSelectFacet } = props;

  return (
    <div className="rounded-lg border border-borderSubtle bg-bgSurface p-5 space-y-4">
      <div className="flex flex-col sm:flex-row sm:items-center justify-between border-b border-borderSubtle pb-3 gap-3">
        <div className="flex items-center gap-2">
          <Sparkles className="h-4 w-4 text-statusInfo" />
          <h2 className="text-sm font-semibold text-textPrimary">Industry Domain Facets</h2>
        </div>
        <div className="flex flex-wrap gap-1 rounded-md bg-surfaceContainer p-1 border border-borderSubtle">
          {facetTabOptions.map((tab) => (
            <button key={tab.type} type="button" onClick={() => onSelectFacet(tab.type)} className={`rounded px-2.5 py-1 text-xs font-medium transition ${selectedFacet === tab.type ? "bg-accentPrimary text-white shadow-sm" : "text-textSecondary hover:text-textPrimary hover:bg-bgSurfaceHover"}`}>
              {tab.label}
            </button>
          ))}
        </div>
      </div>
      {selectedFacet === "none" && (
        <div className="rounded-lg border border-dashed border-borderSubtle p-4 text-xs text-textMuted">
          Standard generic SKU. No specialized domain vertical attributes attached.
        </div>
      )}
      {selectedFacet === "jewelry" && <JewelryFacetFields jewelryFacet={jewelryFacet} errors={errors} onUpdateJewelry={props.onUpdateJewelry} />}
      {selectedFacet === "apparel" && <ApparelFacetFields apparelFacet={apparelFacet} onUpdateApparel={props.onUpdateApparel} />}
      {selectedFacet === "pharma" && <PharmaFacetFields pharmaFacet={pharmaFacet} errors={errors} onUpdatePharma={props.onUpdatePharma} />}
      {selectedFacet === "fmcg" && <FmcgFacetFields fmcgFacet={fmcgFacet} errors={errors} onUpdateFmcg={props.onUpdateFmcg} />}
    </div>
  );
}
