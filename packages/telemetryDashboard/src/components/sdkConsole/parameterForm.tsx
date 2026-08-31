"use client";

import React from "react";
import { AlertTriangle, Play } from "lucide-react";
import type { FieldViolation } from "@/lib/sdkParameterValidation";
import type { SdkMethodDescriptor } from "@/types/sdkConsoleTypes";

export interface ParameterFormProps {
  readonly method: SdkMethodDescriptor;
  readonly values: Readonly<Record<string, string>>;
  readonly violations: readonly FieldViolation[];
  readonly isRunning: boolean;
  readonly onChange: (fieldName: string, value: string) => void;
  readonly onSubmit: () => void;
}

const optionalLabel = "optional";

function findViolation(
  violations: readonly FieldViolation[],
  fieldName: string
): FieldViolation | undefined {
  return violations.find((violation) => violation.fieldName === fieldName);
}

export function ParameterForm({
  method,
  values,
  violations,
  isRunning,
  onChange,
  onSubmit,
}: ParameterFormProps): React.JSX.Element {
  return (
    <form
      onSubmit={(event) => {
        event.preventDefault();
        onSubmit();
      }}
      className="space-y-3"
    >
      {method.sideEffectWarning && (
        <div className="flex items-start gap-2 rounded-lg border border-statusWarning/30 bg-statusWarning/5 p-3">
          <AlertTriangle className="mt-0.5 h-3.5 w-3.5 shrink-0 text-statusWarning" />
          <p className="text-body-sm text-textSecondary">{method.sideEffectWarning}</p>
        </div>
      )}

      {method.parameters.map((field) => {
        const violation = findViolation(violations, field.name);
        return (
          <div key={field.name}>
            <label
              htmlFor={`sdk-param-${field.name}`}
              className="flex items-baseline justify-between gap-2"
            >
              <span className="font-mono text-body-sm text-textPrimary">{field.name}</span>
              {!field.isRequired && (
                <span className="text-[10px] uppercase tracking-wide text-textMuted">
                  {optionalLabel}
                </span>
              )}
            </label>
            <input
              id={`sdk-param-${field.name}`}
              type={field.kind === "number" ? "number" : "text"}
              value={values[field.name] ?? ""}
              onChange={(event) => onChange(field.name, event.target.value)}
              {...(field.minimum !== undefined ? { min: field.minimum } : {})}
              {...(field.maximum !== undefined ? { max: field.maximum } : {})}
              className={`mt-1 w-full rounded-md border bg-bgBase px-2.5 py-1.5 font-mono text-body-sm text-textPrimary outline-none transition-colors focus:border-accentPrimary ${
                violation ? "border-statusError" : "border-borderSubtle"
              }`}
            />
            <p
              className={`mt-1 text-[11px] leading-snug ${
                violation ? "text-statusError" : "text-textMuted"
              }`}
            >
              {violation ? violation.message : field.helpText}
            </p>
          </div>
        );
      })}

      <button
        type="submit"
        disabled={isRunning}
        className={`inline-flex w-full items-center justify-center gap-1.5 rounded-md border px-3 py-2 text-label-sm font-semibold transition-colors ${
          isRunning
            ? "cursor-not-allowed border-borderSubtle bg-surfaceContainer text-textMuted"
            : "cursor-pointer border-accentPrimary/30 bg-accentPrimary/10 text-accentPrimary hover:bg-accentPrimary/20"
        }`}
      >
        <Play className="h-3.5 w-3.5" />
        {isRunning ? "Calling..." : "Send"}
      </button>
    </form>
  );
}
