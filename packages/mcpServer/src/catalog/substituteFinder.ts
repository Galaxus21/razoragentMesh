// Thin client for Layer 1 MCP tool integration with out-of-stock vector substitute healing (/api/v1/catalog/heal-oos).
//
// INVARIANT: This function NEVER throws.
// Turning a stock refusal into a network or serialization error would replace a correct
// business refusal with an unexpected 500. It returns null on timeout, non-2xx, bad JSON,
// healed: false, or any network failure. When null is returned, the caller preserves the
// pre-existing clean refusal.

import {
  resolveMerchantApiUrl,
  catalogHealPath,
  catalogHealTimeoutMs
} from "../constants/catalogSearchConstants.js";

export interface SubstituteRecommendation {
  readonly substituteSkuId: string;
  readonly title: string;
  readonly unitPricePaise: number;
  readonly cosineScore: number | null;
  readonly embeddingMode: "model" | "hash" | string;
}

interface UpstreamHealResponse {
  readonly healed?: boolean;
  readonly failedSkuId?: string;
  readonly substituteSkuId?: string;
  readonly substitutePayload?: Record<string, unknown>;
  readonly cosineScore?: number;
  readonly embeddingMode?: string;
  readonly reason?: string;
}

export async function findSubstituteForOutOfStock(
  failedSkuId: string,
  requestedQuantity: number
): Promise<SubstituteRecommendation | null> {
  const url = `${resolveMerchantApiUrl()}${catalogHealPath}`;

  try {
    const response = await fetch(url, {
      method: "POST",
      headers: { "Content-Type": "application/json" },
      body: JSON.stringify({ failedSkuId, requestedQuantity }),
      signal: AbortSignal.timeout(catalogHealTimeoutMs)
    });

    if (!response.ok) {
      return null;
    }

    const body = (await response.json()) as UpstreamHealResponse;
    if (!body || body.healed !== true || !body.substituteSkuId) {
      return null;
    }

    const payload = body.substitutePayload ?? {};
    const title = typeof payload.title === "string" ? payload.title : body.substituteSkuId;
    const baseUnitPricePaise =
      typeof payload.baseUnitPricePaise === "number"
        ? payload.baseUnitPricePaise
        : typeof payload.pricePaise === "number"
          ? payload.pricePaise
          : 0;

    return {
      substituteSkuId: body.substituteSkuId,
      title,
      unitPricePaise: baseUnitPricePaise,
      cosineScore: typeof body.cosineScore === "number" ? body.cosineScore : null,
      embeddingMode: body.embeddingMode ?? "hash"
    };
  } catch {
    return null;
  }
}
