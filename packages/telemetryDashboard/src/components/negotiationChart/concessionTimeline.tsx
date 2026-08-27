import React from "react";
import { GitCommit } from "lucide-react";
import { negotiationTurnNumbers } from "@/constants/dashboardConstants";
import { formatPaiseToInr } from "@/lib/currencyFormatter";
import { BidTurnCompletedPayload } from "@/types/telemetryEventTypes";

export interface ConcessionTimelineProps {
  readonly turns: ReadonlyArray<BidTurnPayloadLike>;
  readonly latestTurn?: BidTurnPayloadLike | null;
}

type BidTurnPayloadLike = Pick<
  BidTurnCompletedPayload,
  "turnNumber" | "buyerBidPaise" | "sellerAskPaise" | "status"
>;

export function ConcessionTimeline({ turns }: ConcessionTimelineProps): React.JSX.Element {
  return (
    <div className="mt-3 flex-1">
      <div className="flex items-center justify-between text-xs text-textSecondary pb-1">
        <span>Turn Bargaining Convergence Progression</span>
        <span>Max N=5 Turns</span>
      </div>
      <div className="space-y-1.5 pt-1">
        {negotiationTurnNumbers.map((turnNum) => {
          const turnData = turns.find((t) => t.turnNumber === turnNum);
          const isFinished = Boolean(turnData);
          return (
            <div
              key={turnNum}
              className={`flex items-center justify-between rounded px-2.5 py-1.5 text-xs font-mono transition ${isFinished ? "border border-borderSubtle bg-surfaceContainer text-textPrimary" : "border border-borderSubtle/40 bg-surfaceContainer/40 text-textMuted"}`}
            >
              <div className="flex items-center gap-2">
                <GitCommit className={`h-3 w-3 ${isFinished ? "text-accentPrimary" : "text-textMuted"}`} />
                <span>Turn #{turnNum}</span>
              </div>
              {turnData ? (
                <div className="flex items-center gap-3">
                  <span className="text-statusInfo">{formatPaiseToInr(turnData.buyerBidPaise)}</span>
                  <span className="text-textMuted">&harr;</span>
                  <span className="text-accentPrimary">{formatPaiseToInr(turnData.sellerAskPaise)}</span>
                  <span className="rounded bg-statusSuccess/10 border border-statusSuccess/30 px-1.5 py-0.5 text-[10px] text-statusSuccess font-medium">{turnData.status}</span>
                </div>
              ) : (
                <span className="text-xs text-textMuted">Pending</span>
              )}
            </div>
          );
        })}
      </div>
    </div>
  );
}
