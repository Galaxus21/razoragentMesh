import React from "react";
import { TrendingDown } from "lucide-react";
import { formatPaiseToInr } from "@/lib/currencyFormatter";
import { BidTurnCompletedPayload } from "@/types/telemetryEventTypes";

export interface ChartTooltipProps {
  readonly latestTurn: BidTurnCompletedPayload | null;
}

export function ChartTooltip({ latestTurn }: ChartTooltipProps): React.JSX.Element {
  return (
    <div className="mt-3 flex items-center justify-around rounded-md border border-borderSubtle bg-surfaceContainer p-2.5 text-xs">
      <div className="text-center">
        <span className="text-xs text-statusInfo font-semibold uppercase">Buyer Bid (Bt)</span>
        <p className="font-mono text-sm font-bold text-textPrimary">
          {latestTurn ? formatPaiseToInr(latestTurn.buyerBidPaise) : "—"}
        </p>
      </div>
      <div className="flex flex-col items-center">
        <TrendingDown className="h-3.5 w-3.5 text-textMuted" />
        <span className="font-mono text-xs text-textMuted">
          Spread: {latestTurn ? formatPaiseToInr(latestTurn.spreadPaise) : "—"}
        </span>
      </div>
      <div className="text-center">
        <span className="text-xs text-accentPrimary font-semibold uppercase">Seller Ask (St)</span>
        <p className="font-mono text-sm font-bold text-textPrimary">
          {latestTurn ? formatPaiseToInr(latestTurn.sellerAskPaise) : "—"}
        </p>
      </div>
    </div>
  );
}
