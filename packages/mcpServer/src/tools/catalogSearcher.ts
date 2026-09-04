// Tool 4: search_catalog -- natural-language product discovery.
//
// Why this exists: the mesh had no discovery primitive. An agent could quote a SKU id someone
// had already handed it, but nothing could answer "find me an office chair", so a third-party
// agent could not start a purchase on its own. This is the entry point to every other tool.
//
// The ranking runs in merchantApi, which owns the embedding model and the Qdrant client; this
// package is TypeScript and has no embedder. The tool forwards and preserves the honesty
// fields, so an agent is told when a ranking is not actually semantic.

import {
  resolveMerchantApiUrl,
  catalogSearchPath,
  catalogSearchTimeoutMs,
  degradedEmbeddingMode
} from "../constants/catalogSearchConstants.js";
import { catalogSearchRequestSchema } from "../schemas/catalogSearchSchema.js";
import { defaultCatalogStore, CatalogStore } from "../catalog/catalogStore.js";
import { resolveNextPromotion } from "../catalog/promotionResolver.js";
import { millisPerSecond } from "../constants/protocolConstants.js";

interface UpstreamSearchResponse {
  readonly results?: ReadonlyArray<Record<string, unknown>>;
  readonly resultCount?: number;
  readonly embeddingMode?: string;
  readonly rankingQuality?: string;
  readonly indexAvailable?: boolean;
}

/**
 * Ranks catalog entries against a plain-language description.
 *
 * A failure is thrown rather than returned as an empty list: "nothing matched" and "search is
 * down" are different answers, and an agent told the former would conclude the product does
 * not exist and give up.
 */
export async function searchCatalog(
  rawArguments: unknown,
  catalogStore: CatalogStore = defaultCatalogStore,
  currentTimeUnix: number = Math.floor(Date.now() / millisPerSecond)
): Promise<Record<string, unknown>> {
  const { queryText, limit } = catalogSearchRequestSchema.parse(rawArguments);
  const url = `${resolveMerchantApiUrl()}${catalogSearchPath}`;

  let response: Response;
  try {
    response = await fetch(url, {
      method: "POST",
      headers: { "Content-Type": "application/json" },
      body: JSON.stringify({ queryText, limit }),
      signal: AbortSignal.timeout(catalogSearchTimeoutMs)
    });
  } catch (error: unknown) {
    const detail = error instanceof Error ? error.message : String(error);
    throw new Error(`Catalog search is unavailable at ${url}: ${detail}`);
  }

  if (!response.ok) {
    throw new Error(`Catalog search failed with HTTP ${response.status}`);
  }

  const body = (await response.json()) as UpstreamSearchResponse;
  const embeddingMode = body.embeddingMode ?? degradedEmbeddingMode;

  return {
    query_text: queryText,
    results: _withScheduledSales(body.results ?? [], catalogStore, currentTimeUnix),
    result_count: body.resultCount ?? (body.results?.length ?? 0),
    // Passed through deliberately. An agent choosing what to buy should know when the ranking
    // came from a character hash rather than a language model, because in that mode the order
    // carries no meaning and picking the top hit is not a reasoned choice.
    embedding_mode: embeddingMode,
    ranking_quality: body.rankingQuality ?? "",
    index_available: body.indexAvailable ?? false
  };
}

/**
 * Attaches each hit's soonest scheduled sale, in the field name browse_catalog already uses.
 *
 * Measured, an agent shown a sale on the SKU it buys relays it: `execute_settlement` puts that on
 * the receipt and the receipt is the part agents repeat verbatim. The case the receipt cannot
 * reach is the one that actually happens -- the agent is shown a sale on SKU A, buys SKU B, and
 * never mentions A, because by then nothing it can see says A is about to get cheaper. A sale is
 * a property of the result, so it travels with the result, including the results the agent
 * rejects (AUDIT_ARCHIVE item 48).
 *
 * The ranking comes from merchantApi, which reads Redis and Qdrant; the promotions come from the
 * in-process CatalogStore, which is what get_live_sku_quote will price against. A hit the store
 * does not know is passed through untouched rather than dropped: search ranks a wider index than
 * this process holds, and hiding a result because it has no local sale would be worse than
 * saying nothing about its sales.
 */
function _withScheduledSales(
  results: ReadonlyArray<Record<string, unknown>>,
  catalogStore: CatalogStore,
  currentTimeUnix: number
): ReadonlyArray<Record<string, unknown>> {
  return results.map((hit) => {
    const skuId = hit.skuId;
    if (typeof skuId !== "string" || skuId.length === 0) {
      return hit;
    }
    const sku = catalogStore.getSku(skuId);
    const nextPromotion = sku ? resolveNextPromotion(sku, currentTimeUnix) : undefined;
    return nextPromotion === undefined ? hit : { ...hit, next_promotion: nextPromotion };
  });
}
