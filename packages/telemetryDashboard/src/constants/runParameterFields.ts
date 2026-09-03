// The buyer-side inputs a visitor may override before a run.
//
// These are the nine fields of RunParameters, and nothing here invents a default: the prefilled
// values are `defaultRunParameters` itself, so the form always opens showing exactly what the
// driver would have sent on its own. Editing a field changes what the live services receive --
// there is no mock path behind this form.
//
// Numeric bounds are imported from the SDK console catalog rather than restated, so the console
// and this form cannot drift into disagreeing about what the mesh accepts.

import {
  maximumLockTtlSeconds,
  maximumQuantity,
  maximumWeightGrams,
  minimumLockTtlSeconds,
  minimumQuantity,
  minimumWeightGrams,
} from "./sdkConsoleCatalog";
import { defaultRunParameters, type RunParameters } from "@/server/protocolDriver/driverConfig";

export type RunParameterKind = "string" | "number";

export interface RunParameterFieldDescriptor {
  readonly name: keyof RunParameters;
  readonly label: string;
  readonly kind: RunParameterKind;
  readonly isRequired: boolean;
  readonly helpText: string;
  readonly minimum?: number;
  readonly maximum?: number;
  readonly exactDigits?: number;
}

// A paise field must stay a positive integer: the arithmetic enclave works in integer paise and
// rejects a fractional or negative ceiling outright, so catching it here explains the problem
// instead of surfacing it as an opaque HTTP 422.
export const minimumPaise = 1;
export const pincodeDigits = 6;
export const stateCodeDigits = 2;

export const runParameterFields: readonly RunParameterFieldDescriptor[] = [
  {
    name: "skuId",
    label: "SKU id",
    kind: "string",
    isRequired: true,
    helpText: "A SKU in the merchant catalog. An unknown id comes back as HTTP 404 from the quote tool.",
  },
  {
    name: "quantity",
    label: "Quantity",
    kind: "number",
    isRequired: true,
    helpText: "Units to price. Locks are real reservations, so the catalog can be exhausted.",
    minimum: minimumQuantity,
    maximum: maximumQuantity,
  },
  {
    name: "deliveryPincode",
    label: "Delivery pincode",
    kind: "string",
    isRequired: true,
    helpText: "Decides whether the statutory split is CGST+SGST or IGST.",
    exactDigits: pincodeDigits,
  },
  {
    name: "deliveryStateCode",
    label: "Delivery state code",
    kind: "string",
    isRequired: true,
    helpText: "GST state code. 29 is Karnataka, matching the merchant origin.",
    exactDigits: stateCodeDigits,
  },
  {
    name: "promoCode",
    label: "Promo code",
    kind: "string",
    isRequired: false,
    helpText: "Optional. An unrecognised code is ignored by the merchant rather than rejected.",
  },
  {
    name: "maxBudgetPaise",
    label: "Max budget (paise)",
    kind: "number",
    isRequired: true,
    helpText: "The ceiling the user delegates in the Intent Mandate. Lower it to trip the budget gate.",
    minimum: minimumPaise,
  },
  {
    name: "singleTransactionLimitPaise",
    label: "Single transaction limit (paise)",
    kind: "number",
    isRequired: true,
    helpText: "Per-payment ceiling inside the delegated budget.",
    minimum: minimumPaise,
  },
  {
    name: "packageWeightGrams",
    label: "Package weight (grams)",
    kind: "number",
    isRequired: true,
    helpText: "Used by the shipping SLA tool to pick a courier tier.",
    minimum: minimumWeightGrams,
    maximum: maximumWeightGrams,
  },
  {
    name: "lockTtlSeconds",
    label: "Lock TTL (seconds)",
    kind: "number",
    isRequired: true,
    helpText: "How long the fenced inventory reservation is held before it expires.",
    minimum: minimumLockTtlSeconds,
    maximum: maximumLockTtlSeconds,
  },
];

// Prefill values, as strings, taken straight from the driver's own defaults.
export function buildDefaultFormValues(): Record<string, string> {
  const values: Record<string, string> = {};
  for (const field of runParameterFields) {
    const defaultValue = defaultRunParameters[field.name];
    values[field.name] = defaultValue === undefined ? "" : String(defaultValue);
  }
  return values;
}
