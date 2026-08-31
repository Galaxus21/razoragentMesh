// Parameter validation for the SDK console, shared by the form and the API route.
//
// The route must not trust the browser -- the form and the endpoint are separate entry points
// and the endpoint is callable directly -- so both call the same function here rather than each
// keeping its own idea of what is valid.

import type { SdkMethodDescriptor, SdkParameterField } from "@/types/sdkConsoleTypes";

export interface FieldViolation {
  readonly fieldName: string;
  readonly message: string;
}

export interface ValidationOutcome {
  readonly violations: readonly FieldViolation[];
  readonly values: Readonly<Record<string, string | number>>;
}

function validateNumericField(
  field: SdkParameterField,
  rawValue: string
): { violation?: FieldViolation; value?: number } {
  const parsed = Number(rawValue);
  if (!Number.isFinite(parsed)) {
    return { violation: { fieldName: field.name, message: `${field.label} must be a number` } };
  }
  if (!Number.isInteger(parsed)) {
    return { violation: { fieldName: field.name, message: `${field.label} must be a whole number` } };
  }
  if (field.minimum !== undefined && parsed < field.minimum) {
    return {
      violation: { fieldName: field.name, message: `${field.label} must be at least ${field.minimum}` },
    };
  }
  if (field.maximum !== undefined && parsed > field.maximum) {
    return {
      violation: { fieldName: field.name, message: `${field.label} must be at most ${field.maximum}` },
    };
  }
  return { value: parsed };
}

export function validateSdkParameters(
  method: SdkMethodDescriptor,
  rawParameters: Readonly<Record<string, string>>
): ValidationOutcome {
  const violations: FieldViolation[] = [];
  const values: Record<string, string | number> = {};

  for (const field of method.parameters) {
    const rawValue = (rawParameters[field.name] ?? "").trim();

    if (rawValue.length === 0) {
      if (field.isRequired) {
        violations.push({ fieldName: field.name, message: `${field.label} is required` });
      }
      // An omitted optional parameter is left out entirely rather than sent as an empty
      // string, so the SDK applies its own default instead of querying for "".
      continue;
    }

    if (field.kind === "number") {
      const { violation, value } = validateNumericField(field, rawValue);
      if (violation) {
        violations.push(violation);
      } else if (value !== undefined) {
        values[field.name] = value;
      }
      continue;
    }

    values[field.name] = rawValue;
  }

  return { violations, values };
}

export function buildDefaultParameterValues(
  method: SdkMethodDescriptor
): Record<string, string> {
  const defaults: Record<string, string> = {};
  for (const field of method.parameters) {
    defaults[field.name] = field.defaultValue;
  }
  return defaults;
}
