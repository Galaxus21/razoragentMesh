import React from "react";

export interface FormHeaderProps {
  readonly title?: string;
  readonly subtitle?: string;
}

// The "Layer 1 Merchant API" badge that used to sit beside the title is gone, along with the
// store glyph in its tinted square. Neither was for the person using this screen: someone
// publishing a SKU is picking a tax rate and a price, and where the write lands in the protocol
// stack changes nothing they do here. The architecture is still on the Overview page, where a
// reader has actually come to ask about it.
export function FormHeader({
  title = "Merchant SKU Studio",
  subtitle = "Author a SKU and publish it to the live catalog: price, GST rate, volume tiers, spot-linked bullion formulas and the per-industry fields agents search on.",
}: FormHeaderProps): React.JSX.Element {
  return (
    <div className="rounded-lg border border-borderSubtle bg-bgSurface p-5">
      <h1 className="font-headline text-lg font-semibold text-textPrimary">{title}</h1>
      <p className="mt-1 max-w-3xl text-xs leading-relaxed text-textSecondary">{subtitle}</p>
    </div>
  );
}
