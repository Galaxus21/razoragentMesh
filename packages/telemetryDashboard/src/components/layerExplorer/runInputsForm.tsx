"use client";

import React from "react";
import { RotateCcw } from "lucide-react";
import {
  runParameterFields,
  type RunParameterFieldDescriptor,
} from "@/constants/runParameterFields";
import { panelClass } from "@/constants/playgroundConstants";

const cardTitle = "Run inputs";
const cardCaption =
  "Sent verbatim to the live services. Edit any value to change what the packages actually receive — there is no mock path behind this form.";
const resetLabel = "Reset to defaults";

const inputBaseClass =
  "w-full rounded-md border bg-bgBase px-2.5 py-1.5 font-mono text-body-sm text-textPrimary outline-none transition-colors focus:border-accentPrimary";
const inputValidClass = "border-borderSubtle";
const inputInvalidClass = "border-statusError";
const optionalPlaceholder = "none";

export interface RunInputsFormProps {
  readonly values: Readonly<Record<string, string>>;
  readonly errors: Readonly<Record<string, string>>;
  readonly changedCount: number;
  readonly isDisabled: boolean;
  readonly onChange: (fieldName: string, value: string) => void;
  readonly onReset: () => void;
}

function FieldRow({
  field,
  value,
  error,
  isDisabled,
  onChange,
}: {
  readonly field: RunParameterFieldDescriptor;
  readonly value: string;
  readonly error: string | undefined;
  readonly isDisabled: boolean;
  readonly onChange: (fieldName: string, value: string) => void;
}): React.JSX.Element {
  const inputId = `runParameter-${field.name}`;
  return (
    <div>
      <label htmlFor={inputId} className="block text-label-sm font-medium text-textSecondary">
        {field.label}
        {!field.isRequired && <span className="ml-1 text-textMuted">(optional)</span>}
      </label>
      <input
        id={inputId}
        name={field.name}
        value={value}
        disabled={isDisabled}
        placeholder={field.isRequired ? undefined : optionalPlaceholder}
        aria-invalid={error !== undefined}
        aria-describedby={error !== undefined ? `${inputId}-error` : undefined}
        onChange={(event) => onChange(field.name, event.target.value)}
        className={`mt-1 ${inputBaseClass} ${error === undefined ? inputValidClass : inputInvalidClass} disabled:cursor-not-allowed disabled:text-textMuted`}
      />
      {error === undefined ? (
        <p className="mt-1 text-[11px] leading-snug text-textMuted">{field.helpText}</p>
      ) : (
        <p id={`${inputId}-error`} className="mt-1 text-[11px] font-medium text-statusError">
          {error}
        </p>
      )}
    </div>
  );
}

export function RunInputsForm({
  values,
  errors,
  changedCount,
  isDisabled,
  onChange,
  onReset,
}: RunInputsFormProps): React.JSX.Element {
  return (
    <section className={`${panelClass} p-4`}>
      <h3 className="text-label-caps uppercase text-textMuted">{cardTitle}</h3>
      <p className="mt-1.5 text-[11px] leading-snug text-textSecondary">{cardCaption}</p>

      <div className="mt-3 space-y-3">
        {runParameterFields.map((field) => (
          <FieldRow
            key={field.name}
            field={field}
            value={values[field.name] ?? ""}
            error={errors[field.name]}
            isDisabled={isDisabled}
            onChange={onChange}
          />
        ))}
      </div>

      <div className="mt-4 flex items-center justify-between border-t border-borderSubtle pt-3">
        <button
          type="button"
          onClick={onReset}
          disabled={isDisabled || changedCount === 0}
          className="inline-flex items-center gap-1.5 rounded-md border border-borderSubtle px-2.5 py-1.5 text-label-sm font-semibold text-textSecondary transition-colors hover:bg-bgSurfaceHover hover:text-textPrimary disabled:cursor-not-allowed disabled:text-textMuted"
        >
          <RotateCcw className="h-3.5 w-3.5" />
          {resetLabel}
        </button>
        <span className="font-mono text-[11px] text-textMuted">overridden: {changedCount}</span>
      </div>
    </section>
  );
}
