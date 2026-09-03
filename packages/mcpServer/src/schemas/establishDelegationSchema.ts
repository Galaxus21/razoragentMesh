// Wire schema for establish_agent_delegation.
//
// Lives here rather than beside the tool so that the documentation reference generator can see
// it: packages/telemetryDashboard/scripts/generateSdkReference.ts reads this package's
// schemas/index.ts and pairs every exported `<Name>Request` alias with `<Name>Response`. A
// schema declared inline in a tool file is invisible to that pass, so doc snippets naming its
// fields were never checked against the real thing.

import { z } from "zod";
import {
  custodyModes,
  defaultDelegationValiditySeconds,
  maxDelegationValiditySeconds,
  minDelegationValiditySeconds,
  signatureHexLength,
  strictAgentDidRegex
} from "../constants/mandateToolConstants.js";

export const establishDelegationRequestSchema = z.object({
  key_custody: z.enum(custodyModes),
  buyer_agent_id: z.string().regex(strictAgentDidRegex).optional(),
  proof_signature: z.string().length(signatureHexLength).optional(),
  proof_nonce: z.string().min(1).optional(),
  proof_timestamp: z.number().int().positive().optional(),
  max_budget_paise: z.number().int().positive(),
  single_transaction_limit_paise: z.number().int().positive(),
  authorized_categories: z.array(z.string()).default([]),
  validity_seconds: z
    .number()
    .int()
    .min(minDelegationValiditySeconds)
    .max(maxDelegationValiditySeconds)
    .default(defaultDelegationValiditySeconds)
});

export type EstablishDelegationRequest = z.infer<typeof establishDelegationRequestSchema>;

export const establishDelegationResponseSchema = z.object({
  delegation_id: z.string().min(1),
  // The complete signed IntentMandate, returned so the agent can re-verify the delegation it
  // was granted. Its shape is owned by the buyer SDK, not by this package.
  intent_mandate: z.record(z.unknown()),
  user_did: z.string().min(1),
  delegated_agent_did: z.string().min(1),
  valid_until_timestamp: z.number().int().positive(),
  max_budget_paise: z.number().int().positive(),
  single_transaction_limit_paise: z.number().int().positive(),
  key_custody: z.enum(custodyModes),
  custody_disclosure: z.string().min(1),
  // Present ONLY in mesh_demo_custodial mode, and deliberately so: a custodial demo that hands
  // back the key it holds cannot be mistaken for a security boundary.
  buyer_private_key_hex: z.string().optional(),
  category_enforcement: z.string().min(1),
  category_enforcement_note: z.string().min(1),
  session_store: z.string().min(1)
});

export type EstablishDelegationResponse = z.infer<typeof establishDelegationResponseSchema>;
