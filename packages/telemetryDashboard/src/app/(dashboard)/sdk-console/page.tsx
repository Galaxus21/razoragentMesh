"use client";

import React, { useMemo, useState } from "react";
import { AlertTriangle, MousePointerClick, Terminal } from "lucide-react";
import { InvocationResultPanel } from "@/components/sdkConsole/invocationResultPanel";
import { MethodPicker } from "@/components/sdkConsole/methodPicker";
import { ParameterForm } from "@/components/sdkConsole/parameterForm";
import { panelClass, stepperWidthClass } from "@/constants/playgroundConstants";
import { sdkMethodCatalog, sdkMethodsById } from "@/constants/sdkConsoleCatalog";
import { useSdkInvocation } from "@/hooks/useSdkInvocation";
import { buildDefaultParameterValues } from "@/lib/sdkParameterValidation";

const pageTitle = "SDK Console";
const pageDescription =
  "Call the buyer SDK yourself with your own arguments. The server runs the real RazorAgentClient against the live mesh and hands back the request it sent, the response it got, and the code that would reproduce it.";
const firstMethodId = sdkMethodCatalog[0]?.methodId ?? "";

export default function SdkConsolePage(): React.JSX.Element {
  const invocation = useSdkInvocation();
  const [selectedMethodId, setSelectedMethodId] = useState<string>(firstMethodId);
  const [parameterValues, setParameterValues] = useState<Record<string, string>>(() =>
    buildDefaultParameterValues(sdkMethodsById[firstMethodId])
  );

  const selectedMethod = useMemo(
    () => sdkMethodsById[selectedMethodId] ?? sdkMethodCatalog[0],
    [selectedMethodId]
  );

  const handleSelectMethod = (methodId: string) => {
    setSelectedMethodId(methodId);
    // Each method has its own arguments, so carrying the previous form's values across would
    // leave stale fields behind rather than a form matching the signature on screen.
    setParameterValues(buildDefaultParameterValues(sdkMethodsById[methodId]));
    invocation.reset();
  };

  return (
    <div className="mx-auto max-w-7xl space-y-4">
      <header>
        <h2 className="text-headline-sm text-textPrimary">{pageTitle}</h2>
        <p className="mt-1 max-w-3xl text-body-sm text-textSecondary">{pageDescription}</p>
      </header>

      {invocation.errorMessage && (
        <div className="flex items-start gap-2 rounded-xl border border-statusError/30 bg-statusError/5 p-4">
          <AlertTriangle className="mt-0.5 h-4 w-4 shrink-0 text-statusError" />
          <div>
            <p className="text-body-md font-semibold text-textPrimary">The call could not run</p>
            <p className="mt-1 text-body-sm text-textSecondary">{invocation.errorMessage}</p>
            <p className="mt-1.5 text-[11px] text-textMuted">
              The mesh services must be running: <code className="font-mono">docker compose up</code>
            </p>
          </div>
        </div>
      )}

      <div className="flex flex-col gap-4 lg:flex-row">
        <section className={`${panelClass} ${stepperWidthClass} space-y-4 p-3`}>
          <div>
            <div className="mb-2 flex items-center gap-1.5 px-1">
              <Terminal className="h-3.5 w-3.5 text-accentPrimary" />
              <span className="text-label-caps uppercase text-textMuted">SDK methods</span>
            </div>
            <MethodPicker
              methods={sdkMethodCatalog}
              selectedMethodId={selectedMethod.methodId}
              onSelect={handleSelectMethod}
            />
          </div>

          <div className="border-t border-borderSubtle px-1 pt-3">
            <p className="mb-3 text-body-sm leading-relaxed text-textSecondary">
              {selectedMethod.summary}
            </p>
            <ParameterForm
              method={selectedMethod}
              values={parameterValues}
              violations={invocation.violations}
              isRunning={invocation.isRunning}
              onChange={(fieldName, value) =>
                setParameterValues((previous) => ({ ...previous, [fieldName]: value }))
              }
              onSubmit={() => void invocation.invoke(selectedMethod.methodId, parameterValues)}
            />
            <p className="mt-3 text-[11px] leading-relaxed text-textMuted">
              Implemented by{" "}
              <code className="font-mono break-all">{selectedMethod.implementedBy}</code>
            </p>
          </div>
        </section>

        <section className={`${panelClass} min-w-0 flex-1 p-5`}>
          {invocation.result ? (
            <InvocationResultPanel result={invocation.result} />
          ) : (
            <div className="flex h-full min-h-[280px] flex-col items-center justify-center gap-2 text-center">
              <MousePointerClick className="h-5 w-5 text-textMuted" />
              <p className="text-body-md text-textSecondary">
                {invocation.isRunning ? "Calling the mesh..." : "No call yet"}
              </p>
              <p className="max-w-sm text-body-sm text-textMuted">
                Pick a method, adjust the arguments and press Send. Nothing here is canned: the
                response is whatever the mesh returns, including its refusals.
              </p>
            </div>
          )}
        </section>
      </div>
    </div>
  );
}
