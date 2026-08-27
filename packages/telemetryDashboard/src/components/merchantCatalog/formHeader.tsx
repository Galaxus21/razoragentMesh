import React from "react";
import { Store } from "lucide-react";

export interface FormHeaderProps {
  readonly title?: string;
  readonly subtitle?: string;
  readonly layerBadge?: string;
}

export function FormHeader({
  title = "Merchant SKU Studio",
  subtitle = "Interactive SKU Authoring: Configure volume tiers, spot-linked bullion formulas, and vertical domain facets for agent discovery.",
  layerBadge = "Layer 4 Merchant API",
}: FormHeaderProps): React.JSX.Element {
  return (
    <div className="rounded-lg border border-borderSubtle bg-bgSurface p-5">
      <div className="flex items-center gap-3">
        <div className="flex h-10 w-10 items-center justify-center rounded-lg bg-accentSubtle border border-accentPrimary/30 text-accentPrimary">
          <Store className="h-5 w-5 text-accentPrimary" />
        </div>
        <div>
          <div className="flex items-center gap-2">
            <h1 className="text-lg font-bold text-textPrimary font-headline">{title}</h1>
            <span className="rounded bg-accentSubtle border border-accentPrimary/30 px-2 py-0.5 font-mono text-xs text-accentPrimary">
              {layerBadge}
            </span>
          </div>
          <p className="text-xs text-textSecondary">{subtitle}</p>
        </div>
      </div>
    </div>
  );
}
