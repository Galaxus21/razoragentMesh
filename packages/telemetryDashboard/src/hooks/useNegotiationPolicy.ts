"use client";

// State for the Studio's Negotiation Policy panel.
//
// Kept out of useMerchantCatalogForm because a policy is not part of a listing: it belongs to the
// merchant, applies to every SKU they publish, and is saved independently of any publish. Folding
// it into the catalog form would have tied the merchant's opt-in to the act of publishing a
// product, so switching negotiation off would have required editing a SKU.

import { useCallback, useEffect, useState } from "react";
import {
  buildNegotiationPolicyPayload,
  defaultNegotiationPolicyForm,
  NegotiationPolicyFormData,
  NegotiationPolicyPayload,
  policyPayloadToFormData,
  PolicyValidationErrors,
  validateNegotiationPolicy,
} from "@/lib/negotiationPolicyValidator";

// Server-side proxy; see src/app/api/mesh/policy/route.ts for why the browser cannot call the
// merchant API directly.
export const meshPolicyProxyEndpoint = "/api/mesh/policy";

export interface PolicySaveResult {
  readonly ok: boolean;
  readonly message: string;
}

export interface UseNegotiationPolicyReturn {
  readonly policy: NegotiationPolicyFormData;
  readonly errors: PolicyValidationErrors;
  readonly isSaving: boolean;
  readonly saveResult: PolicySaveResult | null;
  readonly handleUpdatePolicy: (patch: Partial<NegotiationPolicyFormData>) => void;
  readonly handleSavePolicy: () => Promise<void>;
}

async function _readDetail(response: Response): Promise<string> {
  try {
    const body = (await response.json()) as { detail?: unknown };
    return typeof body.detail === "string" ? body.detail : JSON.stringify(body);
  } catch {
    return response.statusText;
  }
}

/**
 * @param merchantDidFromListing the DID typed into the SKU form, adopted while the merchant has
 * not typed one here. The two are almost always the same, and making the merchant retype their
 * own DID to switch negotiation on is how a panel goes unused.
 */
export function useNegotiationPolicy(
  merchantDidFromListing: string
): UseNegotiationPolicyReturn {
  const [policy, setPolicy] = useState<NegotiationPolicyFormData>(defaultNegotiationPolicyForm);
  const [errors, setErrors] = useState<PolicyValidationErrors>({});
  const [isSaving, setIsSaving] = useState(false);
  const [saveResult, setSaveResult] = useState<PolicySaveResult | null>(null);
  // Preserved across saves so an edit does not reset the merchant's original opt-in date.
  const [createdAtTimestamp, setCreatedAtTimestamp] = useState(0);
  const [hasTypedDid, setHasTypedDid] = useState(false);

  useEffect(() => {
    if (!hasTypedDid) {
      setPolicy((current) => ({ ...current, merchantDid: merchantDidFromListing }));
    }
  }, [merchantDidFromListing, hasTypedDid]);

  // Loads whatever the merchant already has, so the panel opens showing their real state rather
  // than the defaults. A 404 is the normal answer for a merchant who has never configured one.
  useEffect(() => {
    const did = policy.merchantDid.trim();
    if (did.length === 0) {
      return;
    }
    let cancelled = false;
    void (async () => {
      try {
        const response = await fetch(
          `${meshPolicyProxyEndpoint}?merchantDid=${encodeURIComponent(did)}`
        );
        if (!response.ok || cancelled) {
          return;
        }
        const existing = (await response.json()) as NegotiationPolicyPayload;
        if (cancelled || typeof existing?.merchantDid !== "string") {
          return;
        }
        setCreatedAtTimestamp(existing.createdAtTimestamp ?? 0);
        setPolicy(policyPayloadToFormData(existing));
      } catch {
        // The panel is usable without a prefill; a save will report its own failure.
      }
    })();
    return () => {
      cancelled = true;
    };
    // Only re-fetch when the merchant identity changes, not on every keystroke elsewhere.
    // eslint-disable-next-line react-hooks/exhaustive-deps
  }, [policy.merchantDid]);

  const handleUpdatePolicy = useCallback((patch: Partial<NegotiationPolicyFormData>): void => {
    if (patch.merchantDid !== undefined) {
      setHasTypedDid(true);
    }
    setPolicy((current) => ({ ...current, ...patch }));
    setSaveResult(null);
    setErrors((current) => {
      const remaining: Record<string, string> = { ...current };
      for (const key of Object.keys(patch)) {
        delete remaining[key];
      }
      return remaining;
    });
  }, []);

  const handleSavePolicy = useCallback(async (): Promise<void> => {
    const validation = validateNegotiationPolicy(policy);
    setErrors(validation.errors);
    if (!validation.isValid) {
      setSaveResult({ ok: false, message: "Fix the highlighted fields and save again." });
      return;
    }

    setIsSaving(true);
    setSaveResult(null);
    try {
      const payload = buildNegotiationPolicyPayload(policy, createdAtTimestamp);
      const response = await fetch(meshPolicyProxyEndpoint, {
        method: "PUT",
        headers: { "Content-Type": "application/json" },
        body: JSON.stringify(payload),
      });
      if (!response.ok) {
        setSaveResult({ ok: false, message: `Mesh refused the policy: ${await _readDetail(response)}` });
        return;
      }
      const saved = (await response.json()) as NegotiationPolicyPayload;
      setCreatedAtTimestamp(saved.createdAtTimestamp ?? createdAtTimestamp);
      setSaveResult({
        ok: true,
        message: saved.negotiationEnabled
          ? "Saved. Buyer agents may now negotiate on this merchant's SKUs."
          : "Saved. Negotiation is off — agents will be told this merchant's price is firm.",
      });
    } catch (error: unknown) {
      const detail = error instanceof Error ? error.message : String(error);
      setSaveResult({ ok: false, message: `Could not reach the mesh: ${detail}` });
    } finally {
      setIsSaving(false);
    }
  }, [policy, createdAtTimestamp]);

  return { policy, errors, isSaving, saveResult, handleUpdatePolicy, handleSavePolicy };
}
