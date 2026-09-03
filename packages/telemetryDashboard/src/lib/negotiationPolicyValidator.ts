// Builds and checks the merchant's negotiation policy before it is sent to the merchant API.
//
// Why this exists: negotiation is opt-in per merchant, and the switch lives in a single Redis
// key (`mesh:merchant:policy:{did}`) that nothing in the dashboard could write. A merchant could
// publish a SKU from the Studio and had no way to say whether agents were allowed to bargain
// over it, or how far. Until this panel, every merchant was permanently non-negotiable.
//
// NegotiationPolicy (merchantApi/src/schemas/policySchema.py) is extra="forbid" and frozen, so
// the payload has to carry exactly its field set -- a stray key is a 422 the merchant sees as an
// opaque save failure. The bounds below mirror that model's Field() constraints rather than
// being invented here.

export type PolicyValidationErrors = Readonly<Record<string, string>>;

export interface NegotiationPolicyFormData {
  readonly merchantDid: string;
  readonly negotiationEnabled: boolean;
  readonly marginFloorBps: number;
  readonly minimumOrderQuantity: number;
  readonly autoAcceptSpreadInr: string;
  readonly maxNegotiationTurns: number;
}

export interface NegotiationPolicyPayload {
  readonly merchantDid: string;
  readonly negotiationEnabled: boolean;
  readonly marginFloorBps: number;
  readonly minimumOrderQuantity: number;
  readonly autoAcceptSpreadPaise: number;
  readonly maxNegotiationTurns: number;
  readonly createdAtTimestamp: number;
  readonly updatedAtTimestamp: number;
}

export interface PolicyValidationResult {
  readonly isValid: boolean;
  readonly errors: PolicyValidationErrors;
}

/** Mirrors NegotiationPolicy's Field() bounds. Divergence here shows up as a 422, not a hint. */
export const minMarginFloorBps = 0;
export const maxMarginFloorBps = 10_000;
export const minPolicyOrderQuantity = 1;
export const minPolicyNegotiationTurns = 1;
export const maxPolicyNegotiationTurns = 10;
export const paisePerRupee = 100;
export const merchantDidPattern = /^did:agent:[a-z0-9_\-.:]+$/;

/**
 * The gateway's own turn ceiling. A merchant may configure up to 10, but the protocol's escrow
 * and turn accounting are sized for 5 and the gateway takes the smaller of the two -- so a
 * merchant who sets 8 needs to be told that 5 is what they will get, not left to discover it.
 */
export const gatewayMaxNegotiationTurns = 5;

export const defaultNegotiationPolicyForm: NegotiationPolicyFormData = {
  merchantDid: "",
  // Off. A merchant who opens this panel and saves without touching anything has not agreed to
  // let agents bargain over their inventory.
  negotiationEnabled: false,
  marginFloorBps: 1000,
  minimumOrderQuantity: 1,
  autoAcceptSpreadInr: "0",
  maxNegotiationTurns: gatewayMaxNegotiationTurns,
};

/** Rupees as typed to integer paise, or null when the text is not a usable amount. */
export function convertInrTextToPaise(value: string): number | null {
  const trimmed = value.trim();
  if (trimmed.length === 0) {
    return null;
  }
  if (!/^\d+(\.\d{1,2})?$/.test(trimmed)) {
    return null;
  }
  return Math.round(Number(trimmed) * paisePerRupee);
}

/** The floor in paise for a given list price, matching the gateway's integer arithmetic. */
export function previewFloorPricePaise(listPricePaise: number, marginFloorBps: number): number {
  if (listPricePaise <= 0) {
    return 0;
  }
  const bounded = Math.max(minMarginFloorBps, Math.min(marginFloorBps, maxMarginFloorBps));
  return Math.floor((listPricePaise * (maxMarginFloorBps - bounded)) / maxMarginFloorBps);
}

export function validateNegotiationPolicy(
  formData: NegotiationPolicyFormData
): PolicyValidationResult {
  const errors: Record<string, string> = {};

  const did = formData.merchantDid.trim();
  if (did.length === 0) {
    errors.merchantDid = "A merchant DID is required — the policy is stored under it.";
  } else if (!merchantDidPattern.test(did)) {
    errors.merchantDid = "Must look like did:agent:your_merchant_id.";
  }

  if (
    !Number.isInteger(formData.marginFloorBps) ||
    formData.marginFloorBps < minMarginFloorBps ||
    formData.marginFloorBps > maxMarginFloorBps
  ) {
    errors.marginFloorBps = `Must be a whole number between ${minMarginFloorBps} and ${maxMarginFloorBps} basis points.`;
  }

  if (
    !Number.isInteger(formData.minimumOrderQuantity) ||
    formData.minimumOrderQuantity < minPolicyOrderQuantity
  ) {
    errors.minimumOrderQuantity = "Must be at least 1.";
  }

  if (
    !Number.isInteger(formData.maxNegotiationTurns) ||
    formData.maxNegotiationTurns < minPolicyNegotiationTurns ||
    formData.maxNegotiationTurns > maxPolicyNegotiationTurns
  ) {
    errors.maxNegotiationTurns = `Must be between ${minPolicyNegotiationTurns} and ${maxPolicyNegotiationTurns}.`;
  }

  if (convertInrTextToPaise(formData.autoAcceptSpreadInr) === null) {
    errors.autoAcceptSpreadInr = "Enter an amount in rupees, e.g. 0 or 25.50.";
  }

  return { isValid: Object.keys(errors).length === 0, errors };
}

/**
 * The exact field set NegotiationPolicy declares, no more and no less.
 *
 * `createdAtTimestamp` is sent as 0 when unknown: the route treats a non-positive value as "this
 * is new" and stamps it, so the panel does not have to fetch before it can save.
 */
export function buildNegotiationPolicyPayload(
  formData: NegotiationPolicyFormData,
  createdAtTimestamp = 0
): NegotiationPolicyPayload {
  const nowSeconds = Math.floor(Date.now() / 1000);
  return {
    merchantDid: formData.merchantDid.trim(),
    negotiationEnabled: formData.negotiationEnabled,
    marginFloorBps: formData.marginFloorBps,
    minimumOrderQuantity: formData.minimumOrderQuantity,
    autoAcceptSpreadPaise: convertInrTextToPaise(formData.autoAcceptSpreadInr) ?? 0,
    maxNegotiationTurns: formData.maxNegotiationTurns,
    createdAtTimestamp,
    updatedAtTimestamp: nowSeconds,
  };
}

/** Turns a policy the merchant API returned back into form state. */
export function policyPayloadToFormData(
  payload: NegotiationPolicyPayload
): NegotiationPolicyFormData {
  return {
    merchantDid: payload.merchantDid,
    negotiationEnabled: payload.negotiationEnabled,
    marginFloorBps: payload.marginFloorBps,
    minimumOrderQuantity: payload.minimumOrderQuantity,
    autoAcceptSpreadInr: (payload.autoAcceptSpreadPaise / paisePerRupee).toFixed(2),
    maxNegotiationTurns: payload.maxNegotiationTurns,
  };
}
