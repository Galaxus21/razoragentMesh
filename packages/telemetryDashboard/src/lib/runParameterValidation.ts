// Turns the edited form values into the RunParameters override the driver receives.
//
// Two rules govern everything here. First, only fields the visitor actually changed are sent, so
// an untouched form produces an empty override and the run is byte-for-byte the default run.
// Second, validation refuses only what is plainly malformed -- a non-numeric quantity, a pincode
// that is not six digits. Whether SKU-CHAIR-999 exists is the merchant's call, not this file's,
// so an unknown-but-well-formed value is passed through and allowed to fail against the real
// service where the reader can see the actual refusal.

import {
  runParameterFields,
  type RunParameterFieldDescriptor,
} from "@/constants/runParameterFields";
import { defaultRunParameters, type RunParameters } from "@/server/protocolDriver/driverConfig";

export interface ParameterValidationResult {
  readonly overrides: Partial<RunParameters>;
  readonly errors: Readonly<Record<string, string>>;
  readonly changedFieldNames: readonly string[];
}

export const requiredMessage = "required";
export const notANumberMessage = "must be a number";
export const notAnIntegerMessage = "must be a whole number";

export function buildRangeMessage(field: RunParameterFieldDescriptor): string {
  if (field.minimum !== undefined && field.maximum !== undefined) {
    return `must be between ${field.minimum} and ${field.maximum}`;
  }
  if (field.minimum !== undefined) {
    return `must be at least ${field.minimum}`;
  }
  return `must be at most ${field.maximum}`;
}

export function buildDigitsMessage(field: RunParameterFieldDescriptor): string {
  return `must be exactly ${field.exactDigits} digits`;
}

function validateNumeric(
  field: RunParameterFieldDescriptor,
  raw: string
): { value?: number; error?: string } {
  const parsed = Number(raw);
  if (!Number.isFinite(parsed)) {
    return { error: notANumberMessage };
  }
  if (!Number.isInteger(parsed)) {
    return { error: notAnIntegerMessage };
  }
  const belowMinimum = field.minimum !== undefined && parsed < field.minimum;
  const aboveMaximum = field.maximum !== undefined && parsed > field.maximum;
  if (belowMinimum || aboveMaximum) {
    return { error: buildRangeMessage(field) };
  }
  return { value: parsed };
}

function validateText(
  field: RunParameterFieldDescriptor,
  raw: string
): { value?: string; error?: string } {
  if (field.exactDigits !== undefined) {
    const isDigitsOnly = /^\d+$/.test(raw);
    if (!isDigitsOnly || raw.length !== field.exactDigits) {
      return { error: buildDigitsMessage(field) };
    }
  }
  return { value: raw };
}

function readDefaultAsString(name: keyof RunParameters): string {
  const defaultValue = defaultRunParameters[name];
  return defaultValue === undefined ? "" : String(defaultValue);
}

function validateSingleField(
  field: RunParameterFieldDescriptor,
  raw: string
): { value?: string | number; error?: string } {
  if (raw === "") {
    return field.isRequired ? { error: requiredMessage } : { value: "" };
  }
  return field.kind === "number" ? validateNumeric(field, raw) : validateText(field, raw);
}

// Only changed-and-valid fields reach `overrides`. A field the visitor edited back to its
// default is not an override, which is why `changedFieldNames` is compared against the default
// string rather than against a dirty flag the form would have to maintain.
export function validateRunParameters(
  formValues: Readonly<Record<string, string>>
): ParameterValidationResult {
  const overrides: Record<string, string | number> = {};
  const errors: Record<string, string> = {};
  const changedFieldNames: string[] = [];

  for (const field of runParameterFields) {
    const raw = (formValues[field.name] ?? "").trim();
    const isChanged = raw !== readDefaultAsString(field.name);
    const { value, error } = validateSingleField(field, raw);

    if (error !== undefined) {
      errors[field.name] = error;
      continue;
    }
    if (!isChanged) {
      continue;
    }
    changedFieldNames.push(field.name);
    // An emptied optional field is a deliberate clear, so it is sent as an empty string rather
    // than omitted -- omitting it would silently restore the default.
    if (value !== undefined) {
      overrides[field.name] = value;
    }
  }

  return {
    overrides: overrides as Partial<RunParameters>,
    errors,
    changedFieldNames,
  };
}

export function hasValidationErrors(result: ParameterValidationResult): boolean {
  return Object.keys(result.errors).length > 0;
}
