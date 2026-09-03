"use client";

import React, { useEffect, useMemo, useState } from "react";
import { MousePointerClick, Radio, Users } from "lucide-react";
import { PackagePipeline } from "@/components/layerExplorer/packagePipeline";
import { PackagesTouchedStrip } from "@/components/layerExplorer/packagesTouchedStrip";
import { StepDetailPanel } from "@/components/playground/stepDetailPanel";
import {
  liveAgentPageDescription,
  liveAgentPageTitle,
  noSelectionBody,
  noSelectionHeading,
  noSessionsBody,
  noSessionsHeading,
  sessionIdDisplayLength,
  sessionLabelPrefix,
  stdioSessionPrefix
} from "@/constants/liveAgentConstants";
import { panelClass } from "@/constants/playgroundConstants";
import { useSseStream } from "@/hooks/useSseStream";
import { buildLiveAgentSessions, type LiveAgentSession } from "@/lib/liveAgentSteps";

function shortSessionId(sessionId: string): string {
  // A stdio server names its single session `stdio-<uuid>`; keeping the prefix distinguishes an
  // agent that spawned the server itself from one that connected over HTTP.
  if (sessionId.startsWith(stdioSessionPrefix)) {
    return sessionId.slice(0, stdioSessionPrefix.length + 1 + sessionIdDisplayLength);
  }
  return sessionId.slice(0, sessionIdDisplayLength);
}

function SessionCard({
  session,
  isSelected,
  onSelect
}: {
  readonly session: LiveAgentSession;
  readonly isSelected: boolean;
  readonly onSelect: () => void;
}): React.JSX.Element {
  return (
    <button
      type="button"
      onClick={onSelect}
      className={`w-full rounded-lg border p-3 text-left transition-colors ${
        isSelected
          ? "border-accentPrimary/50 bg-accentPrimary/5"
          : "border-borderSubtle hover:border-borderStrong"
      }`}
    >
      <div className="flex items-center justify-between gap-2">
        <span className="font-mono text-label-sm text-textPrimary">
          {sessionLabelPrefix} {shortSessionId(session.sessionId)}
        </span>
        <span className="text-[11px] text-textMuted">
          {session.steps.length} {session.steps.length === 1 ? "stage" : "stages"}
        </span>
      </div>
      {session.callerAgentId && (
        <p className="mt-1 truncate font-mono text-[11px] text-textMuted">{session.callerAgentId}</p>
      )}
      {session.refusalCount > 0 && (
        <span className="mt-1.5 inline-block rounded-full border border-accentPrimary/30 bg-accentPrimary/10 px-2 py-0.5 text-[11px] font-semibold text-accentPrimary">
          {session.refusalCount} refused — protocol worked
        </span>
      )}
    </button>
  );
}

export default function LiveAgentPage(): React.JSX.Element {
  const stream = useSseStream();
  const [selectedSessionId, setSelectedSessionId] = useState<string | null>(null);
  const [selectedStepId, setSelectedStepId] = useState<string | null>(null);
  const [isFollowingRun, setIsFollowingRun] = useState<boolean>(true);

  const sessions = useMemo(() => buildLiveAgentSessions(stream.events), [stream.events]);

  // Follow the most recent session until the reader picks one, so a purchase that starts while
  // this page is open appears without any interaction.
  const activeSessionId = selectedSessionId ?? sessions[0]?.sessionId ?? null;
  const activeSession = sessions.find((session) => session.sessionId === activeSessionId) ?? null;

  const latestStepId = activeSession?.steps[activeSession.steps.length - 1]?.stepId ?? null;
  useEffect(() => {
    if (isFollowingRun && latestStepId) {
      setSelectedStepId(latestStepId);
    }
  }, [isFollowingRun, latestStepId]);

  const selectedStep = useMemo(
    () => activeSession?.steps.find((step) => step.stepId === selectedStepId) ?? null,
    [activeSession, selectedStepId]
  );

  return (
    <div className="mx-auto max-w-[1600px] space-y-4">
      <header className="flex flex-wrap items-start justify-between gap-3">
        <div>
          <h2 className="text-headline-sm text-textPrimary">{liveAgentPageTitle}</h2>
          <p className="mt-1 max-w-3xl text-body-sm text-textSecondary">
            {liveAgentPageDescription}
          </p>
        </div>
        <span className="inline-flex items-center gap-1.5 rounded-full border border-borderSubtle px-2.5 py-1 text-label-sm text-textSecondary">
          <Radio className="h-3.5 w-3.5 text-accentPrimary" />
          {stream.streamMode}
        </span>
      </header>

      <div className="flex flex-col gap-4 xl:flex-row">
        <aside className={`${panelClass} w-full shrink-0 p-4 xl:w-[300px]`}>
          <div className="mb-2 flex items-center gap-1.5 px-1">
            <Users className="h-3.5 w-3.5 text-accentPrimary" />
            <span className="text-label-sm font-semibold text-textPrimary">Agent sessions</span>
          </div>
          {sessions.length === 0 ? (
            <p className="px-1 py-4 text-body-sm text-textMuted">
              Waiting for an agent to call a tool…
            </p>
          ) : (
            <div className="space-y-2">
              {sessions.map((session) => (
                <SessionCard
                  key={session.sessionId}
                  session={session}
                  isSelected={session.sessionId === activeSessionId}
                  onSelect={() => {
                    setSelectedSessionId(session.sessionId);
                    setIsFollowingRun(true);
                  }}
                />
              ))}
            </div>
          )}
        </aside>

        <section className={`${panelClass} min-w-0 flex-1 p-4`}>
          {activeSession ? (
            <>
              <PackagesTouchedStrip steps={activeSession.steps} />
              <div className="mt-4">
                <PackagePipeline
                  steps={activeSession.steps}
                  totalSteps={activeSession.steps.length}
                  selectedStepId={selectedStepId}
                  onSelectStep={(stepId) => {
                    setIsFollowingRun(false);
                    setSelectedStepId(stepId);
                  }}
                />
              </div>
            </>
          ) : (
            <div className="flex h-full min-h-[240px] flex-col items-center justify-center gap-2 text-center">
              <Radio className="h-5 w-5 text-textMuted" />
              <p className="text-body-md text-textSecondary">{noSessionsHeading}</p>
              <p className="max-w-md text-body-sm text-textMuted">{noSessionsBody}</p>
            </div>
          )}
        </section>

        <section className={`${panelClass} w-full shrink-0 p-4 xl:w-[420px]`}>
          {selectedStep ? (
            <StepDetailPanel step={selectedStep} />
          ) : (
            <div className="flex h-full min-h-[240px] flex-col items-center justify-center gap-2 text-center">
              <MousePointerClick className="h-5 w-5 text-textMuted" />
              <p className="text-body-md text-textSecondary">{noSelectionHeading}</p>
              <p className="max-w-sm text-body-sm text-textMuted">{noSelectionBody}</p>
            </div>
          )}
        </section>
      </div>
    </div>
  );
}
