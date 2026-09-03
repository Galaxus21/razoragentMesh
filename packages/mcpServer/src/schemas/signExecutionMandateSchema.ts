// Wire schema for sign_execution_mandate. See establishDelegationSchema.ts for why the mandate
// tools' schemas live here rather than inline beside their tools.

import { z } from "zod";
import { mandateHashHexLength } from "../constants/mandateToolConstants.js";
import { currencyInr } from "../constants/protocolConstants.js";

export const signExecutionMandateRequestSchema = z.object({
  delegation_id: z.string().min(1),
  cart_mandate_hash: z.string().length(mandateHashHexLength).optional()
});

export type SignExecutionMandateRequest = z.infer<typeof signExecutionMandateRequestSchema>;

/**
 * The response carries a common core plus fields that depend on the delegation's key custody:
 * agent_held returns bytes to sign and no signature, mesh_demo_custodial returns a complete
 * signed mandate.
 *
 * Modelled as ONE object with the mode-specific fields optional rather than as a discriminated
 * union, because the documentation reference generator reads members via
 * `checker.getPropertiesOfType`, which on a union returns only the properties common to every
 * branch -- a union here would silently record the shared core and drop every field that
 * actually distinguishes the two custody modes.
 */
export const signExecutionMandateResponseSchema = z.object({
  execution_id: z.string().min(1),
  buyer_agent_did: z.string().min(1),
  intent_mandate_hash: z.string().length(mandateHashHexLength),
  cart_mandate_hash: z.string().length(mandateHashHexLength),
  // Taken from the stored cart, never from the caller: createSignedExecutionMandate signs
  // whatever integer it is handed, so a caller-supplied amount would hash-chain correctly and
  // only the settlement budget gate would catch it.
  settlement_amount_paise: z.number().int().positive(),
  currency: z.literal(currencyInr),
  upi_circle_token: z.string().min(1),
  nonce: z.string().min(1),
  timestamp: z.number().int().positive(),
  signing_window_seconds: z.number().int().positive(),
  settle_before_timestamp: z.number().int().positive(),
  unsigned_payload: z.record(z.unknown()),

  // agent_held only: the exact bytes to sign, and no signature.
  signing_payload_canonical_json: z.string().optional(),
  signing_digest_sha256: z.string().optional(),
  signing_instructions: z.string().optional(),

  // Null in agent_held mode, 128 lowercase hex in mesh_demo_custodial mode.
  agent_signature: z.string().nullable(),

  // mesh_demo_custodial only.
  execution_mandate: z.record(z.unknown()).optional(),
  signed_by: z.string().optional(),
  custody_disclosure: z.string().optional()
});

export type SignExecutionMandateResponse = z.infer<typeof signExecutionMandateResponseSchema>;
